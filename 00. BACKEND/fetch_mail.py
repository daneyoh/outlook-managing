# ============================================================
#  Outlook 메일 수집 스크립트 (Microsoft Graph + 디바이스 코드 로그인)
#
#  [수동 실행]  python fetch_mail.py
#     - 처음 한 번은 화면에 뜨는 코드로 로그인해야 합니다.
#     - 로그인하면 토큰이 token_cache.bin 에 저장되어,
#       이후에는 다시 로그인하지 않아도 됩니다.
#
#  [자동 실행]  python fetch_mail.py --auto
#     - 작업 스케줄러용. 저장된 토큰만 사용하고,
#       토큰이 없으면 로그인 창을 띄우지 않고 조용히 종료합니다.
#
#  결과는 mailbox.json 에 누적되며 중복은 자동 제거됩니다.
# ============================================================

import json
import os
import re
import sys
from datetime import datetime

import msal
import requests

import config
import paths

# user_config.json 우선 로드 — 배포 환경에서 사용자 설정이 config.py를 override.
# Phase 1.5.2: 로더 단일화 — build_dashboard._load_user_config 을 단일 소스로 사용해
# 경로(paths.USER_CONFIG_FILE) · 우선순위(user_config.json > config.py)를 통일한다.
# build_dashboard 는 leaf 성격(paths/config/state_io 만 의존)이라 top-level import 해도
# 순환이 생기지 않는다. on-disk 포맷은 불변.
def _load_user_cfg_early():
    try:
        import build_dashboard
        return build_dashboard._load_user_config()
    except Exception:
        return {}

for _k, _v in _load_user_cfg_early().items():
    setattr(config, _k, _v)

_FETCH_FULL_BODY = getattr(config, "FETCH_FULL_BODY", False)
_BODY_MAX_CHARS  = getattr(config, "BODY_MAX_CHARS", 10000)

GRAPH = "https://graph.microsoft.com/v1.0"
AUTHORITY = f"https://login.microsoftonline.com/{config.TENANT_ID}"

# Phase 1.5.1: 경로 상수는 paths.py 단일 소스에서 가져온다 (기존 이름 유지).
# 주의: 이 모듈의 DB_DIR 은 <ROOT>/02. DB/MAIL_db (app.DB_DIR 과 의미가 다르므로
#       paths.MAIL_DB_DIR 로 alias 한다). DB_BASE 는 <ROOT>/02. DB.
HERE = paths.HERE
ROOT = paths.ROOT                                # 프로젝트 루트 (backend의 부모)
DB_BASE = paths.DB_DIR
DB_DIR = paths.MAIL_DB_DIR                        # 가져온 메일 저장 폴더
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(os.path.join(DB_BASE, "logs"), exist_ok=True)
STATE_DIR = paths.STATE_DIR
os.makedirs(STATE_DIR, exist_ok=True)
CACHE_FILE = paths.CACHE_FILE
MY_GROUPS_FILE = paths.MY_GROUPS_FILE
JSON_FILE = paths.MAIL_JSON_FILE
LOG_FILE = paths.LOG_FILE


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache.deserialize(f.read())
    return cache


def save_cache(cache):
    if cache.has_state_changed:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(cache.serialize())


def get_token(auto=False):
    """저장된 토큰을 우선 사용하고, 없으면(수동 모드일 때만) 로그인한다."""
    cache = load_cache()
    app = msal.PublicClientApplication(
        config.CLIENT_ID, authority=AUTHORITY, token_cache=cache
    )

    # 1) 캐시된 계정으로 조용히 갱신 시도
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(config.SCOPES, account=accounts[0])
        if result and "access_token" in result:
            save_cache(cache)
            return result["access_token"]

    # 2) 자동 모드인데 토큰이 없으면 → 로그인 창 띄우지 않고 종료
    if auto:
        log("저장된 로그인 정보가 없습니다. 먼저 'python fetch_mail.py'로 한 번 로그인하세요.")
        return None

    # 3) 수동 모드 → 디바이스 코드 로그인
    flow = app.initiate_device_flow(scopes=config.SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"디바이스 코드 발급 실패: {json.dumps(flow, ensure_ascii=False)}")
    print("\n" + "=" * 60)
    print(flow["message"])
    print("=" * 60 + "\n")
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(
            f"로그인 실패: {result.get('error')} - {result.get('error_description')}"
        )
    save_cache(cache)
    return result["access_token"]


def fetch_my_groups(token):
    """로그인 사용자가 속한 그룹들의 메일 주소 목록을 /me/memberOf 로 조회.
    - 성공: 주소 list 반환(그룹 아닌 항목·메일 없는 항목은 제외)
    - 권한 없음(401/403)·실패: None 반환 → 기존 캐시 유지, 앱은 수동 MY_GROUPS 로 동작.
    ※ Azure 앱에 GroupMember.Read.All(위임) 권한 + 관리자 동의가 필요하다."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH}/me/memberOf"
    params = {"$select": "mail,displayName", "$top": 100}
    addrs = []
    try:
        while url:
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code in (401, 403):
                log(f"그룹 조회 권한 없음(status {resp.status_code}). "
                    "Azure 앱에 GroupMember.Read.All 추가 후 관리자 동의가 필요합니다.")
                return None
            resp.raise_for_status()
            data = resp.json()
            for it in data.get("value", []):
                mail = (it.get("mail") or "").strip()
                if mail:                       # 그룹만 mail 을 가짐(디렉터리 역할 등은 없음)
                    addrs.append(mail)
            url = data.get("@odata.nextLink")
            params = None                      # nextLink 에 쿼리가 이미 포함됨
        return addrs
    except requests.RequestException as e:
        log(f"그룹 조회 실패: {e}")
        return None


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# 자동회신(부재중 안내 등) 제목 판정 — 이런 메일은 DB(mailbox.json)에 저장하지 않는다.
_AUTO_REPLY_RE = re.compile(
    r"^\s*(?:자동\s*회신|자동응답|부재중(?:\s*안내)?"
    r"|Automatic\s*reply|Auto[- ]?Reply|Out\s*of\s*[Oo]ffice)\s*[:\-]",
    re.IGNORECASE,
)


def is_auto_reply(subject):
    return bool(_AUTO_REPLY_RE.match(subject or ""))


_SELECT_FIELDS = (
    "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
    "sentDateTime,bodyPreview,isRead,hasAttachments,importance,webLink"
    + (",body" if _FETCH_FULL_BODY else "")
)

# Immutable ID 요청: 메일이 폴더 이동/규칙 처리돼도 id·webLink(딥링크)가 안 깨지게 한다.
# 메시지 id·폴더 id·webLink 모두 불변 ID로 반환되므로 모든 관련 요청에 일관 적용해야 한다.
_PREFER_IMMUTABLE = {"Prefer": 'IdType="ImmutableId"'}


def fetch_folder(token, folder, count):
    headers = {"Authorization": f"Bearer {token}", **_PREFER_IMMUTABLE}
    url = f"{GRAPH}/me/mailFolders/{folder}/messages"
    params = {
        "$top": count,
        "$select": _SELECT_FIELDS,
        "$orderby": "receivedDateTime desc",
    }
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json().get("value", [])


def _get_folder_id(token, well_known_name):
    """정크메일 등 well-known 폴더 ID 조회. 실패 시 빈 문자열 반환."""
    try:
        headers = {"Authorization": f"Bearer {token}", **_PREFER_IMMUTABLE}
        r = requests.get(f"{GRAPH}/me/mailFolders/{well_known_name}",
                         headers=headers, params={"$select": "id"}, timeout=10)
        if r.ok:
            return r.json().get("id", "")
    except Exception:
        pass
    return ""


def fetch_all_received(token, count):
    """받은메일함 + 모든 하위폴더에서 수신 메일 수집.
    /me/messages 는 전체 폴더를 통합 검색하므로 하위폴더 이동 메일도 포함됨.
    정크메일(junkemail)·지운편지함(deleteditems)은 제외."""
    headers = {"Authorization": f"Bearer {token}", **_PREFER_IMMUTABLE}

    # 제외할 폴더 ID 사전 조회
    exclude_ids = set(filter(None, [
        _get_folder_id(token, "junkemail"),
        _get_folder_id(token, "deleteditems"),
    ]))

    url = f"{GRAPH}/me/messages"
    params = {
        "$top": count,
        "$select": _SELECT_FIELDS + ",parentFolderId",
        "$orderby": "receivedDateTime desc",
        "$filter": "isDraft eq false",
    }
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    msgs = resp.json().get("value", [])

    # 정크/지운편지함 제외
    if exclude_ids:
        msgs = [m for m in msgs if m.get("parentFolderId") not in exclude_ids]

    # 보낸메일(sentitems에서 별도 수집)은 제외 — 중복 방지
    my_email = getattr(config, "MY_EMAIL", "").lower()
    if my_email:
        msgs = [m for m in msgs
                if (m.get("from") or {}).get("emailAddress", {}).get("address", "").lower() != my_email]

    # 자동회신(부재중 안내 등)은 DB에 저장하지 않음
    msgs = [m for m in msgs if not is_auto_reply(m.get("subject", ""))]
    return msgs


def normalize(msg, box):
    sender = (msg.get("from") or {}).get("emailAddress", {})
    recipients = "; ".join(
        r.get("emailAddress", {}).get("address", "")
        for r in (msg.get("toRecipients") or [])
    )
    cc = "; ".join(
        r.get("emailAddress", {}).get("address", "")
        for r in (msg.get("ccRecipients") or [])
    )
    row = {
        "id": msg.get("id"),
        "구분": box,
        "날짜": msg.get("receivedDateTime") or msg.get("sentDateTime") or "",
        "보낸사람": sender.get("address", ""),
        "받는사람": recipients,
        "참조": cc,
        "제목": msg.get("subject", ""),
        "본문요약": strip_html(msg.get("bodyPreview", "")),
        "읽음": msg.get("isRead", ""),
        "첨부": msg.get("hasAttachments", ""),
        "중요도": msg.get("importance", ""),
        "링크": msg.get("webLink", ""),
    }
    if _FETCH_FULL_BODY:
        body_html = (msg.get("body") or {}).get("content", "")
        try:
            body_plain = strip_html(body_html)
        except Exception:
            body_plain = re.sub(r"<[^>]+>", "", body_html)
        row["본문전체"] = body_plain[:_BODY_MAX_CHARS]
    return row


def load_existing():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return {row["id"]: row for row in data if row.get("id")}
            except json.JSONDecodeError:
                return {}
    return {}


def _fetch_folder_ids(token, well_known_name, page_size=500):
    """폴더 내 메시지 ID 전체 페이지 수집."""
    headers = {"Authorization": f"Bearer {token}", **_PREFER_IMMUTABLE}
    folder_id = _get_folder_id(token, well_known_name)
    if not folder_id:
        return set()
    ids = set()
    url = f"{GRAPH}/me/mailFolders/{folder_id}/messages"
    params = {"$top": page_size, "$select": "id"}
    while url:
        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            break
        for m in data.get("value", []):
            if m.get("id"):
                ids.add(m["id"])
        url = data.get("@odata.nextLink")
        params = {}  # nextLink에는 파라미터 불필요
    return ids


def clean_junk_from_store(token):
    """mailbox.json에서 정크메일·지운편지함 메시지를 Graph API 조회 후 제거."""
    import state_io
    log("정크/지운편지함 ID 조회 중...")
    junk_ids = _fetch_folder_ids(token, "junkemail")
    deleted_ids = _fetch_folder_ids(token, "deleteditems")
    remove_ids = junk_ids | deleted_ids
    if not remove_ids:
        log("제거할 정크/지운 메일 없음.")
        return 0

    store = load_existing()
    before = len(store)
    store = {k: v for k, v in store.items() if k not in remove_ids}
    removed = before - len(store)

    if removed > 0:
        rows = sorted(store.values(), key=lambda r: r.get("날짜", ""), reverse=True)
        with state_io.lock(JSON_FILE):
            state_io.write_json(JSON_FILE, rows)
        log(f"정크/지운 메일 {removed}건 mailbox.json에서 제거 완료.")
    else:
        log("mailbox.json에 정크/지운 메일 없음.")
    return removed


def clean_auto_reply_from_store():
    """mailbox.json에 이미 저장된 자동회신(부재중 안내 등) 메일 제거."""
    import state_io
    store = load_existing()
    before = len(store)
    store = {k: v for k, v in store.items() if not is_auto_reply(v.get("제목", ""))}
    removed = before - len(store)

    if removed > 0:
        rows = sorted(store.values(), key=lambda r: r.get("날짜", ""), reverse=True)
        with state_io.lock(JSON_FILE):
            state_io.write_json(JSON_FILE, rows)
        log(f"자동회신 메일 {removed}건 mailbox.json에서 제거 완료.")
    return removed


def main(auto=None):
    if auto is None:
        auto = "--auto" in sys.argv

    if "여기에" in config.CLIENT_ID or "여기에" in config.TENANT_ID:
        log("먼저 config.py 에 CLIENT_ID 와 TENANT_ID 를 입력하세요.")
        return {"ok": False, "auth_required": False, "new": 0, "msg": "config 미설정"}

    token = get_token(auto=auto)
    if token is None:
        return {"ok": False, "auth_required": True, "new": 0, "msg": "인증 필요"}

    # 내가 속한 그룹 주소 자동 조회 → 캐시 (권한 없으면 조용히 건너뜀, 기존 캐시 유지)
    try:
        import state_io
        groups = fetch_my_groups(token)
        if groups is not None:
            with state_io.lock(MY_GROUPS_FILE):
                state_io.write_json(MY_GROUPS_FILE, groups)
            log(f"소속 그룹 {len(groups)}개 조회/저장.")
    except Exception as e:
        log(f"그룹 조회 중 오류(무시): {e}")

    clean_junk_from_store(token)
    clean_auto_reply_from_store()
    inbox = fetch_all_received(token, config.MAX_EMAILS)
    sent = fetch_folder(token, "sentitems", config.MAX_EMAILS)

    # 기존 데이터에 새 메일 병합 (id 기준 중복 제거)
    store = load_existing()

    # 자연키: 같은 메일을 식별하는 안정적 키 (id 타입이 legacy↔immutable로 바뀌어도 불변).
    # Immutable ID 전환 시 같은 메일이 두 id로 중복 저장되는 것을 막는다.
    def _nat_key(r):
        return (r.get("제목", ""), r.get("날짜", ""), r.get("보낸사람", ""))

    before_keys = {_nat_key(r) for r in store.values()}

    fetched_ids = set()
    for m in inbox:
        row = normalize(m, "받은메일")
        store[row["id"]] = row
        fetched_ids.add(row["id"])
    for m in sent:
        row = normalize(m, "보낸메일")
        store[row["id"]] = row
        fetched_ids.add(row["id"])

    # 자연키 기준 합치기: 같은 메일이 여러 id로 들어가면 이번에 수집된(immutable) 항목을
    # 우선 보존하고 나머지(과거 legacy id)는 버린다. 둘 다 미수집이면 최신 날짜 우선.
    by_key = {}
    for rid, row in store.items():
        k = _nat_key(row)
        cur = by_key.get(k)
        if cur is None:
            by_key[k] = (rid, row)
            continue
        cur_id, cur_row = cur
        cur_fresh = cur_id in fetched_ids
        new_fresh = rid in fetched_ids
        if new_fresh and not cur_fresh:
            by_key[k] = (rid, row)
        elif new_fresh == cur_fresh and row.get("날짜", "") > cur_row.get("날짜", ""):
            by_key[k] = (rid, row)

    store = {rid: row for rid, row in by_key.values()}
    new_count = len([k for k in by_key if k not in before_keys])

    rows = sorted(store.values(), key=lambda r: r.get("날짜", ""), reverse=True)

    # JSON 저장 (분석용) — 원자적 쓰기
    import state_io
    with state_io.lock(JSON_FILE):
        state_io.write_json(JSON_FILE, rows)

    log(f"수집 완료: 받은 {len(inbox)} / 보낸 {len(sent)}건 조회, "
        f"신규 {new_count}건 추가, 누적 총 {len(rows)}건.")

    # 대시보드 갱신 (있을 때만)
    try:
        import build_dashboard
        build_dashboard.main()
    except Exception:
        pass

    return {"ok": True, "auth_required": False, "new": new_count, "msg": f"신규 {new_count}건 추가"}


if __name__ == "__main__":
    result = main()
    if result and not result.get("ok") and result.get("auth_required"):
        log("인증이 필요합니다. 자동 모드가 아닌 경우 다시 로그인을 시도합니다.")
        main(auto=False)
