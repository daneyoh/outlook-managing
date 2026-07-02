# ============================================================
#  대시보드 생성기
#  mailbox.json 을 읽어 dashboard.html 을 생성한다.
#  - 요약: 건수/기간/주요 상대/미읽음 등
#  - TO DO: 받은 메일 중 처리 필요(요청·검토·확인·회신·마감 등) 후보
#  - 진행상황: 제목(스레드) 기준으로 묶어 최근 흐름/상태 표시
#  - 전체메일: 검색·필터 가능한 표
#  수집(fetch)할 때마다 자동으로 다시 생성된다.
# ============================================================

import html
import json
import os
import re
import state_io
import config as _cfg
import paths
from collections import defaultdict
from datetime import datetime, timedelta

# Phase 1.5.1: 경로 상수는 paths.py 단일 소스에서 가져온다 (기존 이름 유지).
HERE = paths.HERE
ROOT = paths.ROOT                                  # 프로젝트 루트 (backend의 부모)
JSON_FILE = paths.MAIL_JSON_FILE
OUT_FILE = paths.DASHBOARD_OUT_FILE
# 프로젝트 분류 규칙 파일 (사용자가 직접 편집 — {"프로젝트명": ["키워드", ...], ...})
PROJECTS_FILE = paths.PROJECTS_FILE
ARCHIVE_FILE = paths.ARCHIVE_FILE
MAX_AGE_DAYS = getattr(_cfg, "MAX_AGE_DAYS", 90)
ARCHIVE_MAX_AGE_DAYS = getattr(_cfg, "ARCHIVE_MAX_AGE_DAYS", 365)

# ------------------------------------------------------------------
# Phase 1.5.2: 신원(identity) 필드는 import 시점에 얼려두던 상수 대신 매 호출
# 시점에 LIVE 로 해석하는 accessor 로 제공한다. 설정 화면(user_config.json) 저장이
# 앱 재시작 없이 즉시 반영되게 하기 위함이다.
#
# 설정 우선순위(단일 문서화 규칙): user_config.json 이 config.py 를 override 한다.
#   - _resolve_cfg(key, default) 가 매 호출마다 user_config.json 을 먼저 보고,
#     없으면 config.py(_cfg) 값을 쓴다.
#   - app.py / fetch_mail.py 가 import 시점에 setattr(config, ...) 로 user_config 를
#     이미 덮어써 두었더라도, 이 accessor 는 파일을 다시 읽어 최신 값을 반영하므로
#     어느 로더가 먼저 돌았는지와 무관하게 동일한 결과를 준다.
def _load_user_config():
    """user_config.json 을 dict 로 읽는다. 없거나 깨졌으면 빈 dict.
    on-disk 포맷은 변경하지 않는다 — 읽기 타이밍/우선순위만 통일한다."""
    try:
        with open(paths.USER_CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _resolve_cfg(key, default):
    """설정값을 LIVE 로 해석한다: user_config.json > config.py > default."""
    uc = _load_user_config()
    if key in uc and uc[key] is not None:
        return uc[key]
    return getattr(_cfg, key, default)


def get_my_email():
    """내 이메일 주소 (LIVE). 설정 화면 저장이 재시작 없이 반영된다."""
    return _resolve_cfg("MY_EMAIL", "") or ""


def get_my_name():
    """내 이름 (LIVE)."""
    return _resolve_cfg("MY_NAME", "") or ""


def get_internal_domain():
    """사내(내부) 도메인 (LIVE) — 내부/외부 메일 구분에 사용.
    명시 설정(INTERNAL_DOMAIN)이 없으면 내 이메일 주소의 도메인 부분에서
    자동으로 도출한다 (기존 build_dashboard.py:34-35 or-fallback 그대로 재현).
    fallback 의 내부 MY_EMAIL 참조도 LIVE accessor(get_my_email)를 호출한다."""
    explicit = (_resolve_cfg("INTERNAL_DOMAIN", "") or "").lower()
    if explicit:
        return explicit
    my_email = get_my_email()
    return my_email.split("@")[-1].lower() if "@" in my_email else ""


# 자동 조회한 소속 그룹 주소 캐시 (fetch_mail 이 /me/memberOf 로 채움)
# fetch_mail.MY_GROUPS_FILE 와 동일 파일 (paths.MY_GROUPS_FILE).
AUTO_GROUPS_FILE = paths.MY_GROUPS_FILE


def _load_auto_groups():
    """fetch_mail 이 저장한 자동 조회 그룹 주소 목록. 없으면 빈 리스트."""
    try:
        with open(AUTO_GROUPS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError, json.JSONDecodeError):
        return []


def _my_group_addrs():
    """내가 소속된 그룹(배포 리스트) 주소 목록(소문자, 중복 제거).
    (1) 수동 설정 config.MY_GROUPS (list 또는 콤마/세미콜론/개행 문자열)
    (2) 자동 조회 캐시(widget_my_groups.json) 를 합친다.
    런타임 설정 변경(user_config)도 반영되도록 매번 새로 읽는다."""
    raw = getattr(_cfg, "MY_GROUPS", None) or []
    if isinstance(raw, str):
        raw = re.split(r"[;,\n]", raw)
    combined = list(raw) + _load_auto_groups()
    out, seen = [], set()
    for a in combined:
        s = str(a).strip().lower()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _is_to_me(to_field):
    """받는사람(To) 문자열에 내 이메일 또는 내 소속 그룹 주소가 있으면 True.
    그룹으로 온 메일도 '나에게 온 것'으로 취급하기 위함."""
    tf = (to_field or "").lower()
    my_email = get_my_email()
    if my_email and my_email.lower() in tf:
        return True
    return any(g in tf for g in _my_group_addrs())

# 처리 필요(액션) 신호 키워드
ACTION_KEYWORDS = [
    "요청", "부탁", "검토", "확인", "회신", "답장", "회답", "마감", "기한",
    "까지", "제출", "전달", "공유", "승인", "결재", "피드백", "수정", "보완",
    "필요", "협조", "문의", "답변", "리뷰", "asap", "please", "review",
    "request", "deadline", "urgent", "확인부탁", "회신바랍니다",
]


def load():
    if not os.path.exists(JSON_FILE):
        return []
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def load_active():
    """mailbox.json만 읽기."""
    try:
        with open(JSON_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def load_archived():
    """mailbox_archive.json 읽기 (없으면 빈 리스트)."""
    try:
        if not os.path.exists(ARCHIVE_FILE):
            return []
        with open(ARCHIVE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def norm_subject(s):
    s = s or ""
    # Re:, RE:, FW:, Fwd:, 회신:, 답장: 등 접두어 제거 (반복)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"^\s*(re|fw|fwd|회신|답장|전달)\s*:\s*", "", s, flags=re.IGNORECASE)
    return s.strip()


def fmt_date(s):
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return s[:16].replace("T", " ")


def has_action(row):
    text = (row.get("제목", "") + " " + row.get("본문요약", "")).lower()
    return any(k.lower() in text for k in ACTION_KEYWORDS)


# 마감일 cue: 이 단어가 근처에 있을 때만 날짜를 마감으로 인정 (오탐 방지)
_DEADLINE_CUE = ("까지", "마감", "기한", "deadline", "by ", "due")
# YYYY-MM-DD (명시적 — cue 없어도 인정)
_RE_YMD = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")
# M/D, M-D, M.D  (cue 필요)
_RE_MD = re.compile(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})(?!\d)")
# M월 D일 (cue 필요)
_RE_KMD = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
# N일까지 / N일 내 (cue 내장 — "까지"/"이내")
_RE_NDAYS = re.compile(r"(\d{1,3})\s*일\s*(?:까지|이내|내)")


def _mk_deadline(year, month, day):
    """(year, month, day) → ISO 문자열. 6개월 이상 과거면 다음 해로 롤. 잘못된 날짜는 None."""
    try:
        d = datetime(year, month, day).date()
    except ValueError:
        return None
    today = datetime.now().date()
    if (today - d).days > 183:
        try:
            d = datetime(year + 1, month, day).date()
        except ValueError:
            return None
    return d.isoformat()


def parse_deadline(text):
    """제목+본문요약에서 마감일을 보수적으로 추출해 ISO 날짜(YYYY-MM-DD) 또는 None 반환.
    - YYYY-MM-DD 는 cue 없이 인정.
    - M/D, M-D, M월 D일 은 '까지/마감/기한/deadline/due' cue 가 텍스트에 있을 때만 인정.
    - N일까지/N일이내 는 오늘 + N일.
    """
    if not text:
        return None
    t = str(text)
    low = t.lower()
    now = datetime.now()

    m = _RE_YMD.search(t)
    if m:
        return _mk_deadline(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    has_cue = any(c in low for c in _DEADLINE_CUE)

    m = _RE_NDAYS.search(t)
    if m:
        return (now + timedelta(days=int(m.group(1)))).date().isoformat()

    if has_cue:
        m = _RE_KMD.search(t)
        if m:
            return _mk_deadline(now.year, int(m.group(1)), int(m.group(2)))
        m = _RE_MD.search(t)
        if m:
            mon, day = int(m.group(1)), int(m.group(2))
            if 1 <= mon <= 12 and 1 <= day <= 31:
                return _mk_deadline(now.year, mon, day)
    return None


def _deadline_days(iso):
    """ISO 날짜 → 오늘로부터 남은 일수(D-N). 지났으면 음수. None 이면 None."""
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso).date()
    except ValueError:
        return None
    return (d - datetime.now().date()).days


def _parse_dt(s):
    """ISO 문자열을 naive datetime 으로. 실패 시 None. (tz 제거해 now()와 비교)"""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except ValueError:
        return None


def load_project_rules():
    """프로젝트 분류 규칙을 읽는다. 없으면 빈 dict로 파일을 생성(사용자 편집용)."""
    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            rules = json.load(f)
            if isinstance(rules, dict):
                return rules
            return {}
    except FileNotFoundError:
        try:
            os.makedirs(os.path.dirname(PROJECTS_FILE), exist_ok=True)
            state_io.write_json(PROJECTS_FILE, {})
        except OSError:
            pass
        return {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


# 제목 앞머리 대괄호 태그: [XYZ] 또는 【XYZ】
_BRACKET_RE = re.compile(r"^\s*[\[【]\s*([^\]】]+?)\s*[\]】]")


def project_of(row, rules):
    """메일 1건의 프로젝트명을 판정한다.
    1) 제목(정규화) 앞 대괄호 태그가 있으면 그 태그 텍스트.
    2) 없으면 rules 항목이 매칭되는 첫 프로젝트명.
       - 레거시 리스트 항목 `[kw, ...]`: 각 kw 를 제목/보낸사람/받는사람 합본에 매칭
         (미이관 파일 하위호환).
       - 정규 dict 항목 `{senders, keywords, subjects}` (Phase 2.1):
         · senders → 보낸사람·받는사람 양쪽에 매칭 (case-insensitive `any(s in ...)`;
           get_card_mails 는 보낸사람만 매칭 — 여기서는 받는사람도 포함).
         · keywords + subjects → 정규화 제목(norm_subject).
         · senders 만 있고 keywords/subjects 가 비어도 발신자만으로 매칭.
    3) 없으면 "기타".
    """
    subj = norm_subject(row.get("제목", ""))
    m = _BRACKET_RE.match(subj)
    if m:
        return m.group(1).strip()
    subj_l = subj.lower()
    sender_l = (row.get("보낸사람", "") or "").lower()
    recip_l = (row.get("받는사람", "") or "").lower()
    # 레거시 리스트 경로 하위호환: 제목/보낸사람/받는사람 합본
    hay = subj_l + " " + sender_l + " " + recip_l
    for name, val in rules.items():
        if isinstance(val, dict):
            senders = [str(s).lower() for s in (val.get("senders") or [])]
            keywords = [str(k).lower() for k in (val.get("keywords") or [])]
            subjects = [str(s).lower() for s in (val.get("subjects") or [])]
            sender_match = any(s and (s in sender_l or s in recip_l)
                               for s in senders)
            subj_match = any(t and t in subj_l
                             for t in (keywords + subjects))
            if sender_match or subj_match:
                return name
        else:
            for kw in (val or []):
                if kw and str(kw).lower() in hay:
                    return name
    return "기타"


def run_archive():
    """
    오래된 스레드 전체를 mailbox_archive.json으로 이동.
    조건: 스레드 모든 메시지 MAX_AGE_DAYS일+ AND 상태파일 참조 없음.
    build_data() 핫패스 밖에서만 호출할 것.
    """
    # 상태 파일들에서 참조 중인 제목 키 수집
    # Phase 1.5.1: app 순환 import 제거 — STATE_DIR 는 paths.py 단일 소스에서.
    state_dir = paths.STATE_DIR

    referenced_keys = set()
    for fname in ["widget_done.json", "widget_excluded.json", "widget_snooze.json",
                  "widget_important.json", "widget_notes.json"]:
        fpath = os.path.join(state_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                referenced_keys.update(data.keys())
        except Exception:
            pass

    cutoff = (datetime.now() - timedelta(days=MAX_AGE_DAYS)).isoformat()
    archive_cutoff = (datetime.now() - timedelta(days=ARCHIVE_MAX_AGE_DAYS)).isoformat()

    rows = load_active()
    threads = defaultdict(list)
    for row in rows:
        key = norm_subject(row.get("제목", ""))
        threads[key].append(row)

    to_archive_keys = set()
    for key, msgs in threads.items():
        if key in referenced_keys:
            continue
        dates = [m.get("날짜", "") for m in msgs]
        dates = [d for d in dates if d]
        if not dates:
            continue
        if max(dates) < cutoff:  # 가장 최근 메시지도 cutoff 이전
            to_archive_keys.add(key)

    if not to_archive_keys:
        return {"archived": 0}

    staying = [r for r in rows if norm_subject(r.get("제목", "")) not in to_archive_keys]
    moving  = [r for r in rows if norm_subject(r.get("제목", "")) in to_archive_keys]

    # 기존 archive 로드 + 병합 + 365일 초과 드롭
    existing_archive = load_archived()
    merged = existing_archive + moving
    merged = [r for r in merged
              if r.get("날짜", "") >= archive_cutoff]

    with state_io.lock(JSON_FILE):
        state_io.write_json(JSON_FILE, staying)
        state_io.write_json(ARCHIVE_FILE, merged)

    return {"archived": len(moving)}


def build_data():
    rows_active = load_active()
    rows_archived = load_archived()
    rows_union = rows_active + rows_archived
    received = [r for r in rows_union if r.get("구분") == "받은메일"]
    sent = [r for r in rows_union if r.get("구분") == "보낸메일"]
    rules = load_project_rules()  # 프로젝트 규칙 1회 로드
    now = datetime.now()

    # TODO: "나에게 온 요청" 수집
    #   - 내부(사내 도메인) 발신자가 나(받는사람)에게 보낸 메일, 또는
    #   - 제목/본문요약에 내 이름(MY_NAME)이 등장하는 메일 (참조/CC 포함 — 가장 놓치기 쉬움)
    # 각 항목에 내부여부/to_me/참조요청 플래그를 달아 프론트 소분류·강조에 사용한다.
    # 단, 내가 이미 회신한 대화(스레드의 최신 메일이 보낸메일)는 TODO에서 제외한다.

    # 스레드(정규화 제목)별 최신 메일 방향 — 내가 마지막에 보냈으면 회신 완료로 본다.
    _latest_date, _latest_dir = {}, {}
    for r in rows_union:
        k = norm_subject(r.get("제목", "")) or r.get("제목", "")
        dt = r.get("날짜", "") or ""
        if k not in _latest_date or dt > _latest_date[k]:
            _latest_date[k] = dt
            _latest_dir[k] = r.get("구분", "")
    replied_threads = {k for k, dirn in _latest_dir.items() if dirn == "보낸메일"}
    # 같은 대화(제목 정규화 기준)는 하나로 묶는다: 가장 최근 메일을 대표로,
    # 미읽음은 그룹 내 하나라도 있으면 유지(놓침 방지), 건수로 묶인 개수를 표시한다.
    todo_groups = {}
    for r in received:
        from_field = (r.get("보낸사람", "") or "").lower()
        to_field = (r.get("받는사람", "") or "").lower()
        body = (r.get("제목", "") or "") + " " + (r.get("본문요약", "") or "")
        _internal_domain = get_internal_domain()
        is_internal = bool(_internal_domain) and _internal_domain in from_field
        to_me = _is_to_me(to_field)   # 내 주소 또는 소속 그룹 주소 수신 포함
        _my_name = get_my_name()
        name_match = bool(_my_name) and _my_name in body
        if not ((is_internal and to_me) or name_match):
            continue
        gkey = norm_subject(r.get("제목", "")) or r.get("제목", "")
        if gkey in replied_threads:   # 내가 이미 회신한 대화 → 제외
            continue
        raw_date = r.get("날짜", "") or ""
        unread = not r.get("읽음", True)
        g = todo_groups.get(gkey)
        if g is None or raw_date > g["_raw"]:
            # 새 그룹 또는 더 최근 메일 → 대표 교체 (미읽음/건수는 아래서 누적)
            dl = parse_deadline(r.get("제목", "") + " " + r.get("본문요약", ""))
            todo_groups[gkey] = {
                "_raw": raw_date,
                "날짜": fmt_date(raw_date),
                "보낸사람": r.get("보낸사람", ""),
                "제목": r.get("제목", ""),
                "요약": r.get("본문요약", "")[:160],
                "미읽음": unread or (g["미읽음"] if g else False),
                "링크": r.get("링크", ""),
                "마감일": dl,
                "마감D": _deadline_days(dl),
                "내부여부": is_internal,
                "to_me": to_me,
                # 참조요청: To 수신자는 내가 아닌데 본문이 날 콕 집은 경우 → 은은한 강조 대상
                "참조요청": (not to_me) and name_match,
                "건수": (g["건수"] if g else 0) + 1,
            }
        else:
            g["건수"] += 1
            if unread:
                g["미읽음"] = True
    todos = list(todo_groups.values())
    for t in todos:
        t.pop("_raw", None)
    todos.sort(key=lambda t: t["날짜"], reverse=True)

    # 진행상황: 스레드(정규화 제목)로 묶기
    threads = defaultdict(list)
    for r in rows_union:
        key = norm_subject(r.get("제목", "")) or "(제목 없음)"
        threads[key].append(r)

    thread_list = []
    for key, msgs in threads.items():
        msgs_sorted = sorted(msgs, key=lambda m: m.get("날짜", ""))
        last = msgs_sorted[-1]
        last_dir = last.get("구분", "")
        unread = any((m.get("구분") == "받은메일" and not m.get("읽음", True))
                     for m in msgs)
        # 내가 To(받는사람)에 있을 때만 내 담당(확인/미회신). 아니면 "참조"로 분류해 제외(CC 등)
        # 내 소속 그룹 주소로 온 경우도 내 담당으로 취급
        to_me = _is_to_me(last.get("받는사람", ""))
        if last_dir == "받은메일" and to_me and unread:
            status = "확인 필요"
        elif last_dir == "받은메일" and to_me:
            status = "회신 대기"
        elif last_dir == "받은메일":
            status = "참조"
        else:
            status = "내가 회신함"
        # 경과일: 마지막 메일 날짜 기준 (회신 대기/확인 필요만 의미 있음)
        elapsed = None
        if status in ("회신 대기", "확인 필요"):
            dt = _parse_dt(last.get("날짜", ""))
            if dt is not None:
                elapsed = (now - dt).days
        # 답장주소: 스레드 내 마지막 받은메일의 보낸사람 (바로 답장 수신자)
        # 요약: 같은(마지막) 받은메일의 본문요약 — 호버 시 본문 미리보기에 사용
        reply_addr = ""
        last_summary = ""
        for m in reversed(msgs_sorted):
            if m.get("구분") == "받은메일":
                reply_addr = m.get("보낸사람", "")
                last_summary = m.get("본문요약", "") or ""
                break
        # 마감일: 제목 + 스레드 내 받은메일 본문요약 전체에서 탐색
        dl_text = key + " " + " ".join(
            m.get("본문요약", "") for m in msgs_sorted
            if m.get("구분") == "받은메일")
        dl = parse_deadline(dl_text)
        thread_list.append({
            "제목": key,
            "건수": len(msgs),
            "최근": fmt_date(last.get("날짜", "")),
            "최근방향": "받음" if last_dir == "받은메일" else "보냄",
            "상태": status,
            "경과일": elapsed,
            "프로젝트": project_of(last, rules),
            "링크": last.get("링크", ""),
            "답장주소": reply_addr,
            "요약": last_summary[:160],
            "마감일": dl,
            "마감D": _deadline_days(dl),
            "_sortkey": last.get("날짜", ""),
        })
    thread_list.sort(key=lambda t: t["_sortkey"], reverse=True)
    for t in thread_list:
        t.pop("_sortkey", None)

    # 프로젝트별 집계: 미회신수(회신 대기) desc, 건수 desc
    proj_map = defaultdict(lambda: {"threads": [], "건수": 0, "미회신수": 0})
    for t in thread_list:
        p = proj_map[t["프로젝트"]]
        p["건수"] += t["건수"]
        if t["상태"] == "회신 대기":
            p["미회신수"] += 1
        p["threads"].append({
            "제목": t["제목"],
            "건수": t["건수"],
            "최근": t["최근"],
            "상태": t["상태"],
            "경과일": t["경과일"],
            "링크": t["링크"],
            "답장주소": t["답장주소"],
            "마감일": t["마감일"],
            "마감D": t["마감D"],
        })
    projects = [{
        "프로젝트": name,
        "건수": v["건수"],
        "미회신수": v["미회신수"],
        "threads": v["threads"],
    } for name, v in proj_map.items()]
    projects.sort(key=lambda p: (p["미회신수"], p["건수"]), reverse=True)

    # 전체 메일 (표) — active only
    table = [{
        "구분": "받음" if r.get("구분") == "받은메일" else "보냄",
        "날짜": fmt_date(r.get("날짜", "")),
        "상대": r.get("보낸사람", "") if r.get("구분") == "받은메일" else r.get("받는사람", ""),
        "제목": r.get("제목", ""),
        "요약": r.get("본문요약", "")[:200],
        "미읽음": not r.get("읽음", True),
        "첨부": bool(r.get("첨부", False)),
        "링크": r.get("링크", ""),
    } for r in rows_active]
    table.sort(key=lambda r: r["날짜"], reverse=True)

    # 요약 통계
    sender_count = defaultdict(int)
    for r in received:
        sender_count[r.get("보낸사람", "")] += 1
    top_senders = sorted(sender_count.items(), key=lambda x: x[1], reverse=True)[:8]

    dates = [r.get("날짜", "")[:10] for r in rows_union if r.get("날짜")]
    summary = {
        "총건수": len(rows_union),
        "받은": len(received),
        "보낸": len(sent),
        "미읽음": sum(1 for r in received if not r.get("읽음", True)),
        "TODO수": len(todos),
        "기간": f"{min(dates)} ~ {max(dates)}" if dates else "-",
        "주요상대": [{"email": e, "n": n} for e, n in top_senders],
        "갱신시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 통계(차트용): 최근 14일 일별 메일량 / 상대별 분포 / 미회신 추세
    day_keys = [(now - timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(13, -1, -1)]  # 오래된→최신
    recv_by_day = defaultdict(int)
    sent_by_day = defaultdict(int)
    for r in rows_union:
        d = (r.get("날짜", "") or "")[:10]
        if r.get("구분") == "받은메일":
            recv_by_day[d] += 1
        else:
            sent_by_day[d] += 1
    daily = [{"날짜": d[5:], "받은": recv_by_day.get(d, 0),
              "보낸": sent_by_day.get(d, 0)} for d in day_keys]

    # 미회신 추세: 회신 대기 스레드에 속한 받은메일을 받은 날짜별로 카운트
    waiting_keys = {t["제목"] for t in thread_list if t["상태"] == "회신 대기"}
    wait_by_day = defaultdict(int)
    for r in received:
        if norm_subject(r.get("제목", "")) in waiting_keys:
            wait_by_day[(r.get("날짜", "") or "")[:10]] += 1
    unreplied_trend = [{"날짜": d[5:], "n": wait_by_day.get(d, 0)}
                       for d in day_keys]

    senders = [{"email": e, "n": n} for e, n in top_senders]

    # 응답속도 분석: 받은메일 → 같은 스레드 내 그 이후 첫 내 발신까지 시간차(시간)
    # 스레드별 내 발신 시각 목록을 미리 모아 이분 비교 대신 순회로 첫 응답 탐색
    sent_dts_by_key = defaultdict(list)
    for s in sent:
        key = norm_subject(s.get("제목", ""))
        dt = _parse_dt(s.get("날짜", ""))
        if dt is not None:
            sent_dts_by_key[key].append(dt)
    for v in sent_dts_by_key.values():
        v.sort()

    all_latencies = []                      # 전체 응답시간(시간 단위)
    latency_by_sender = defaultdict(list)   # 상대별 응답시간
    for r in received:
        key = norm_subject(r.get("제목", ""))
        recv_dt = _parse_dt(r.get("날짜", ""))
        if recv_dt is None:
            continue
        # 받은 시각 이후의 첫 내 발신
        reply_dt = next((d for d in sent_dts_by_key.get(key, []) if d > recv_dt), None)
        if reply_dt is None:
            continue
        hours = (reply_dt - recv_dt).total_seconds() / 3600.0
        if hours < 0:
            continue
        all_latencies.append(hours)
        latency_by_sender[r.get("보낸사람", "")].append(hours)

    overall_avg = (round(sum(all_latencies) / len(all_latencies), 1)
                   if all_latencies else None)
    by_sender = [{
        "email": e,
        "평균h": round(sum(hs) / len(hs), 1),
        "건수": len(hs),
    } for e, hs in latency_by_sender.items()]
    by_sender.sort(key=lambda x: x["건수"], reverse=True)
    response_speed = {"전체평균h": overall_avg, "상대별": by_sender[:8]}

    # 히트맵: 요일(0=월~6=일) × 시간대 4구간, 받은+보낸 전부 카운트
    bucket_labels = ["0-5", "6-11", "12-17", "18-23"]
    wk_labels = ["월", "화", "수", "목", "금", "토", "일"]
    heat = [[0] * 4 for _ in range(7)]
    for r in rows_union:
        dt = _parse_dt(r.get("날짜", ""))
        if dt is None:
            continue
        heat[dt.weekday()][dt.hour // 6] += 1
    heatmap = {
        "buckets": bucket_labels,
        "rows": [{"요일": wk_labels[i], "vals": heat[i]} for i in range(7)],
    }

    stats = {
        "daily": daily,
        "senders": senders,
        "미회신추세": unreplied_trend,
        "응답속도": response_speed,
        "히트맵": heatmap,
    }

    return {"summary": summary, "todos": todos,
            "threads": thread_list, "table": table,
            "projects": projects, "stats": stats}


HTML_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Outlook 메일 대시보드</title>
<style>
  :root{--bg:#f5f6f8;--card:#fff;--line:#e4e6eb;--ink:#1d2129;--sub:#65676b;
        --blue:#1a73e8;--red:#d93025;--green:#1e8e3e;--amber:#f29900;}
  *{box-sizing:border-box}
  body{margin:0;font-family:"Malgun Gothic","맑은 고딕",system-ui,sans-serif;
       background:var(--bg);color:var(--ink);font-size:14px}
  header{background:var(--card);border-bottom:1px solid var(--line);padding:16px 22px}
  h1{margin:0;font-size:18px}
  .upd{color:var(--sub);font-size:12px;margin-top:4px}
  .wrap{max-width:1180px;margin:0 auto;padding:18px 22px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:18px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
  .card .n{font-size:24px;font-weight:700}
  .card .l{color:var(--sub);font-size:12px;margin-top:2px}
  .tabs{display:flex;gap:6px;border-bottom:1px solid var(--line);margin-bottom:14px;flex-wrap:wrap}
  .tab{padding:9px 16px;cursor:pointer;border:1px solid transparent;border-bottom:none;
       border-radius:8px 8px 0 0;color:var(--sub);font-weight:600}
  .tab.on{background:var(--card);border-color:var(--line);color:var(--blue)}
  .panel{display:none}.panel.on{display:block}
  table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  th,td{padding:9px 11px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
  th{background:#fafbfc;font-size:12px;color:var(--sub);position:sticky;top:0}
  tr:last-child td{border-bottom:none}
  .pill{display:inline-block;padding:1px 8px;border-radius:11px;font-size:11px;font-weight:700}
  .p-need{background:#fce8e6;color:var(--red)}
  .p-wait{background:#fef7e0;color:var(--amber)}
  .p-done{background:#e6f4ea;color:var(--green)}
  .p-recv{background:#e8f0fe;color:var(--blue)}
  .p-sent{background:#eef0f2;color:var(--sub)}
  .unread{font-weight:700}
  .dot{color:var(--red);font-weight:700}
  .sub{color:var(--sub);font-size:12px}
  input[type=search]{width:100%;max-width:340px;padding:8px 11px;border:1px solid var(--line);
       border-radius:8px;margin-bottom:10px;font-size:13px}
  a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
  .muted{color:var(--sub);font-size:12px;margin:4px 0 12px}
</style></head>
<body>
<header><h1>Outlook 메일 대시보드</h1><div class="upd" id="upd"></div></header>
<div class="wrap">
  <div class="cards" id="cards"></div>
  <div class="tabs">
    <div class="tab on" data-t="todo">TO DO (<span id="ct"></span>)</div>
    <div class="tab" data-t="thread">진행상황</div>
    <div class="tab" data-t="all">전체 메일</div>
    <div class="tab" data-t="who">주요 상대</div>
  </div>
  <div class="panel on" id="p-todo">
    <div class="muted">받은 메일 중 처리가 필요해 보이는 항목입니다(요청·검토·확인·회신·마감 등 키워드 + 미읽음 우선). 자동 추출이라 참고용입니다.</div>
    <input type="search" id="q-todo" placeholder="TO DO 검색...">
    <div id="todo"></div>
  </div>
  <div class="panel" id="p-thread">
    <div class="muted">같은 제목끼리 묶은 대화 흐름과 상태입니다.</div>
    <input type="search" id="q-thread" placeholder="제목 검색...">
    <div id="thread"></div>
  </div>
  <div class="panel" id="p-all">
    <input type="search" id="q-all" placeholder="전체 메일 검색...">
    <div id="all"></div>
  </div>
  <div class="panel" id="p-who"><div id="who"></div></div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const esc = s => (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const s = D.summary;
document.getElementById('upd').textContent = '마지막 갱신: ' + s.갱신시각 + '  ·  기간 ' + s.기간;
document.getElementById('ct').textContent = s.TODO수;
document.getElementById('cards').innerHTML = [
  ['총 메일', s.총건수],['받은', s.받은],['보낸', s.보낸],
  ['미읽음', s.미읽음],['TO DO', s.TODO수]
].map(c=>`<div class="card"><div class="n">${c[1]}</div><div class="l">${c[0]}</div></div>`).join('');

function link(u){return u?` <a href="${esc(u)}" target="_blank">열기</a>`:''}

function renderTodo(f){
  f=(f||'').toLowerCase();
  const rows=D.todos.filter(t=>!f||(t.제목+t.보낸사람+t.요약).toLowerCase().includes(f));
  document.getElementById('todo').innerHTML = rows.length? '<table><tr><th>상태</th><th>날짜</th><th>보낸사람</th><th>제목 / 요약</th></tr>'+
    rows.map(t=>`<tr>
      <td>${t.미읽음?'<span class="pill p-need">미읽음</span>':'<span class="pill p-wait">확인</span>'}</td>
      <td class="sub">${esc(t.날짜)}</td>
      <td>${esc(t.보낸사람)}</td>
      <td><div class="${t.미읽음?'unread':''}">${esc(t.제목)}${link(t.링크)}</div>
          <div class="sub">${esc(t.요약)}</div></td></tr>`).join('')+'</table>'
    : '<div class="muted">해당 항목이 없습니다.</div>';
}
function renderThread(f){
  f=(f||'').toLowerCase();
  const rows=D.threads.filter(t=>!f||t.제목.toLowerCase().includes(f));
  const cls={'확인 필요':'p-need','회신 대기':'p-wait','내가 회신함':'p-done'};
  document.getElementById('thread').innerHTML='<table><tr><th>상태</th><th>제목</th><th>건수</th><th>최근</th><th>최근 방향</th></tr>'+
    rows.map(t=>`<tr><td><span class="pill ${cls[t.상태]||''}">${t.상태}</span></td>
      <td>${esc(t.제목)}</td><td>${t.건수}</td><td class="sub">${esc(t.최근)}</td>
      <td><span class="pill ${t.최근방향==='받음'?'p-recv':'p-sent'}">${t.최근방향}</span></td></tr>`).join('')+'</table>';
}
function renderAll(f){
  f=(f||'').toLowerCase();
  const rows=D.table.filter(r=>!f||(r.제목+r.상대+r.요약).toLowerCase().includes(f));
  document.getElementById('all').innerHTML='<table><tr><th>구분</th><th>날짜</th><th>상대</th><th>제목 / 요약</th></tr>'+
    rows.slice(0,500).map(r=>`<tr>
      <td><span class="pill ${r.구분==='받음'?'p-recv':'p-sent'}">${r.구분}</span>${r.미읽음?' <span class="dot">●</span>':''}${r.첨부?' 📎':''}</td>
      <td class="sub">${esc(r.날짜)}</td><td>${esc(r.상대)}</td>
      <td><div class="${r.미읽음?'unread':''}">${esc(r.제목)}${link(r.링크)}</div>
          <div class="sub">${esc(r.요약)}</div></td></tr>`).join('')+'</table>'
    + (rows.length>500?'<div class="muted">상위 500건만 표시합니다.</div>':'');
}
document.getElementById('who').innerHTML='<table><tr><th>보낸 사람</th><th>받은 메일 수</th></tr>'+
  s.주요상대.map(w=>`<tr><td>${esc(w.email)}</td><td>${w.n}</td></tr>`).join('')+'</table>';

renderTodo();renderThread();renderAll();
document.getElementById('q-todo').oninput=e=>renderTodo(e.target.value);
document.getElementById('q-thread').oninput=e=>renderThread(e.target.value);
document.getElementById('q-all').oninput=e=>renderAll(e.target.value);
document.querySelectorAll('.tab').forEach(tab=>tab.onclick=()=>{
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('on'));
  tab.classList.add('on');
  document.getElementById('p-'+tab.dataset.t).classList.add('on');
});
</script>
</body></html>
"""


WEEKLY_OUT_FILE = paths.WEEKLY_OUT_FILE

WEEKLY_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>주간 리포트</title>
<style>
  :root{{--bg:#1e2227;--card:#2a2f37;--line:#3a4250;--ink:#e6e8ea;--sub:#8b9099;
        --blue:#69b7ff;--red:#ff6b6b;--amber:#ffb454;}}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:"Malgun Gothic","맑은 고딕",system-ui,sans-serif;
       background:var(--bg);color:var(--ink);font-size:14px}}
  .wrap{{max-width:760px;margin:0 auto;padding:24px 22px}}
  h1{{margin:0 0 4px;font-size:20px}}
  .upd{{color:var(--sub);font-size:12px;margin-bottom:18px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-bottom:22px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}}
  .card .n{{font-size:24px;font-weight:700}}
  .card .l{{color:var(--sub);font-size:12px;margin-top:2px}}
  h2{{font-size:15px;margin:18px 0 8px}}
  table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
  th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)}}
  th{{color:var(--sub);font-size:12px}}
  tr:last-child td{{border-bottom:none}}
  td.num{{text-align:right;font-weight:700}}
</style></head>
<body><div class="wrap">
<h1>주간 리포트</h1>
<div class="upd">{기간}  ·  생성 {생성시각}</div>
<div class="cards">
  <div class="card"><div class="n" style="color:var(--blue)">{받은}</div><div class="l">받은</div></div>
  <div class="card"><div class="n" style="color:var(--sub)">{보낸}</div><div class="l">보낸</div></div>
  <div class="card"><div class="n" style="color:var(--blue)">{내가답한}</div><div class="l">내가 답한</div></div>
  <div class="card"><div class="n" style="color:var(--red)">{미처리}</div><div class="l">미처리(회신대기)</div></div>
  <div class="card"><div class="n" style="color:var(--amber)">{평균회신}</div><div class="l">평균 회신시간</div></div>
</div>
<h2>프로젝트별 건수</h2>
<table><tr><th>프로젝트</th><th>총 건수</th><th>미회신</th></tr>
{프로젝트행}
</table>
</div></body></html>
"""


def build_weekly_report():
    """이번주(최근 7일) 요약을 weekly_report.html 로 생성하고 경로를 반환한다.
    받은/보낸/내가답한/미처리(현재 회신대기)/전체평균 회신시간/프로젝트별 건수.
    """
    rows = load_active() + load_archived()
    data = build_data()
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    recv_n = sent_n = 0
    for r in rows:
        dt = _parse_dt(r.get("날짜", ""))
        if dt is None or dt < week_ago:
            continue
        if r.get("구분") == "받은메일":
            recv_n += 1
        elif r.get("구분") == "보낸메일":
            sent_n += 1

    # 내가 답한: 최근 7일 내 발신 중, 같은 스레드에 그 이전 받은메일이 있는 것
    recv_by_key = defaultdict(list)
    for r in rows:
        if r.get("구분") == "받은메일":
            dt = _parse_dt(r.get("날짜", ""))
            if dt is not None:
                recv_by_key[norm_subject(r.get("제목", ""))].append(dt)
    replied_n = 0
    for s in rows:
        if s.get("구분") != "보낸메일":
            continue
        sdt = _parse_dt(s.get("날짜", ""))
        if sdt is None or sdt < week_ago:
            continue
        key = norm_subject(s.get("제목", ""))
        if any(rd < sdt for rd in recv_by_key.get(key, [])):
            replied_n += 1

    unhandled = sum(1 for t in data["threads"] if t.get("상태") == "회신 대기")
    avg = data["stats"]["응답속도"]["전체평균h"]
    avg_txt = f"{avg}h" if avg is not None else "-"

    proj_rows = "".join(
        f'<tr><td>{html.escape(str(p.get("프로젝트", "")))}</td>'
        f'<td class="num">{p.get("건수", 0)}</td>'
        f'<td class="num">{p.get("미회신수", 0)}</td></tr>'
        for p in data["projects"]
    ) or '<tr><td colspan="3">데이터 없음</td></tr>'

    out = WEEKLY_TEMPLATE.format(
        기간=f"{week_ago.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}",
        생성시각=now.strftime("%Y-%m-%d %H:%M"),
        받은=recv_n, 보낸=sent_n, 내가답한=replied_n,
        미처리=unhandled, 평균회신=avg_txt, 프로젝트행=proj_rows,
    )
    with open(WEEKLY_OUT_FILE, "w", encoding="utf-8") as f:
        f.write(out)
    return WEEKLY_OUT_FILE


def main():
    data = build_data()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = HTML_TEMPLATE.replace("__DATA__", payload)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(out)
    return data["summary"]["총건수"]


def get_card_mails(card, done_keys=None, excluded_keys=None):
    """카드의 senders/keywords와 매칭되는 raw 메일 목록 반환 (done/excluded 필터 적용)."""
    rows = load_active()  # list of mail dicts
    senders = [s.lower() for s in (card.get("senders") or [])]
    keywords = [k.lower() for k in (card.get("keywords") or [])]
    if not senders and not keywords:
        return []

    result = []
    for mail in rows:
        sender = (mail.get("보낸사람") or "").lower()
        subject = (mail.get("제목") or "").lower()
        summary = (mail.get("본문요약") or "").lower()  # raw 메일은 요약을 '본문요약' 키로 보관 (fetch_mail.py:271)
        sender_match = senders and any(s in sender for s in senders)
        keyword_match = keywords and any(k in subject or k in summary for k in keywords)
        if not sender_match and not keyword_match:
            continue
        if done_keys or excluded_keys:
            subj_key = norm_subject(mail.get("제목") or "")
            if done_keys and subj_key in done_keys:
                continue
            if excluded_keys and subj_key in excluded_keys:
                continue
        result.append(mail)

    result.sort(key=lambda m: m.get("날짜") or "", reverse=True)
    return result


def get_card_stage(card):
    """카드의 현재 단계와 다음 단계 D-day 반환.

    반환값::
        {
            "current": {"name": "킥오프", "date": "2026-05-01"} or None,
            "next":    {"name": "설계완료", "date": "2026-06-15", "ddays": -5} or None,
            "all_future": True/False,
        }
    """
    milestones = card.get("milestones") or []

    # ISO 날짜 파싱 가능한 것만 수집, 오름차순 정렬
    valid = []
    for ms in milestones:
        date_str = ms.get("date") or ""
        try:
            datetime.fromisoformat(date_str)
            valid.append(ms)
        except ValueError:
            continue
    valid.sort(key=lambda m: m["date"])

    if not valid:
        return {"current": None, "next": None, "all_future": False}

    today = datetime.now().date()
    current = None
    next_ms = None

    for i, ms in enumerate(valid):
        ms_date = datetime.fromisoformat(ms["date"]).date()
        if ms_date <= today:
            current = ms
            next_ms = valid[i + 1] if i + 1 < len(valid) else None
        else:
            if current is None:
                # 모든 마일스톤이 미래
                next_ms = ms
            break

    all_future = current is None and len(valid) > 0

    result = {
        "current": ({"name": current.get("name"), "date": current["date"]}
                    if current else None),
        "next": None,
        "all_future": all_future,
    }
    if next_ms:
        ddays = _deadline_days(next_ms.get("date"))
        result["next"] = {
            "name": next_ms.get("name"),
            "date": next_ms["date"],
            "ddays": ddays,
        }
    return result


if __name__ == "__main__":
    n = main()
    print(f"대시보드 생성 완료: dashboard.html (총 {n}건)")
