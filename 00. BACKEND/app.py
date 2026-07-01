# ============================================================
#  Outlook 메일 위젯 — pywebview 버전 (always-on-top)
#  - Tkinter UI(widget.py) 를 HTML/CSS/JS(ui.html) 로 교체.
#  - Python 은 데이터/상태 로직만 담당하고, JS 에 Api 객체를 노출한다.
#  - build_dashboard.build_data() 결과를 가공해 get_view() 로 JS 에 전달.
#  - 상태 파일(widget_excluded/snooze/done.json) 의미는 widget.py 와 동일.
#  - 콘솔 없이 띄우려면 start_widget.bat (pythonw app.py) 로 실행.
#
#  CRITICAL: Api 는 창 없이 import/호출 가능해야 한다.
#            webview.create_window/start 는 if __name__=="__main__" 아래에만.
# ============================================================

import json
import os
import re
import sys
import threading
import webbrowser
import urllib.parse
from uuid import uuid4
from datetime import datetime, timedelta

import build_dashboard
import config
import state_io

# OS 토스트 알림 (Windows). 없으면 조용히 비활성화.
try:
    from win11toast import toast as _toast
except Exception:
    _toast = None

if getattr(sys, "frozen", False):
    # PyInstaller 6: _MEIPASS = _internal/ (data files), executable dir = writable root
    _MEIPASS = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    ROOT = os.path.dirname(sys.executable)
    UI_FILE = os.path.join(_MEIPASS, "ui.html")
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.dirname(HERE)
    UI_FILE = os.path.join(ROOT, "01. FRONTEND", "ui.html")

DB_DIR = os.path.join(ROOT, "02. DB")
STATE_DIR = os.path.join(DB_DIR, "state")
JSON_FILE = os.path.join(DB_DIR, "MAIL_db", "mailbox.json")
USER_CONFIG_FILE = os.path.join(STATE_DIR, "user_config.json")

POS_FILE = os.path.join(STATE_DIR, "widget_pos.json")
EXCLUDE_FILE = os.path.join(STATE_DIR, "widget_excluded.json")
SNOOZE_FILE = os.path.join(STATE_DIR, "widget_snooze.json")
DONE_FILE = os.path.join(STATE_DIR, "widget_done.json")
MYTODOS_FILE = os.path.join(STATE_DIR, "widget_mytodos.json")
MEMOS_FILE   = os.path.join(STATE_DIR, "widget_memos.json")
TAGS_FILE    = os.path.join(STATE_DIR, "widget_tags.json")
VIP_FILE = os.path.join(STATE_DIR, "widget_vip.json")
IMPORTANT_FILE = os.path.join(STATE_DIR, "widget_important.json")
NOTES_FILE = os.path.join(STATE_DIR, "widget_notes.json")
DONE_LOG_FILE = os.path.join(STATE_DIR, "widget_done_log.json")
PROJECTS_FILE = os.path.join(STATE_DIR, "widget_projects.json")
PROJECT_CARDS_FILE = os.path.join(STATE_DIR, "widget_project_cards.json")
MAX_AGE_DAYS = getattr(config, "MAX_AGE_DAYS", 90)

WIN_W, WIN_H = 360, 740
SNOOZE_DAYS = getattr(config, "SNOOZE_DEFAULT_DAYS", 3)

# 긴급/마감 강조 키워드 (widget.py 와 동일)
URGENT_KEYWORDS = ["마감", "긴급", "urgent", "asap"]


def _is_urgent(title, summary):
    text = (str(title) + " " + str(summary)).lower()
    return any(k in text for k in URGENT_KEYWORDS)


# 제목 맨 앞 '광고' 머리표 제거: (광고)·[광고]·【광고】 + 분리자 동반 바 '광고'
# (바 '광고'는 뒤에 공백/:/- 가 있을 때만 — "광고팀" 같은 단어 오제거 방지)
_AD_RE = re.compile(r"^\s*(?:[\(\[【]\s*광고\s*[\)\]】]|광고(?=[\s:\-]))\s*[:\-]?\s*")


def _strip_ad(title):
    """제목 앞 '광고' 머리표를 반복 제거. 전체가 광고표뿐이면 원본 유지."""
    s = title or ""
    prev = None
    while prev != s:
        prev = s
        s = _AD_RE.sub("", s)
    s = s.strip()
    return s or (title or "")


# --- 상태 파일 로드/저장 (widget.py 의 의미 그대로 이식) -------------------

def _load_set(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError, json.JSONDecodeError):
        return set()


def _save_set(path, items):
    try:
        state_io.write_json(path, sorted(items))
        return True
    except Exception:
        return False


def _load_snoozed():
    """스누즈: {제목: {"until": ISO만료일, "anchor": 최근}}. 만료(<= 오늘) 항목은 로드시 자동 제거.
    구버전 형식({제목: ISO만료일})도 호환 — 문자열 값을 until 로 보고 anchor 는 None."""
    try:
        with open(SNOOZE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    today = datetime.now().date().isoformat()
    active = {}
    for k, v in raw.items():
        if isinstance(v, str):              # 구버전: until 문자열
            v = {"until": v, "anchor": None}
        if not isinstance(v, dict):
            continue
        until = v.get("until")
        if isinstance(until, str) and until > today:
            active[k] = {"until": until, "anchor": v.get("anchor")}
    if active != raw:
        _save_snoozed(active)
    return active


def _save_snoozed(snoozed):
    try:
        state_io.write_json(SNOOZE_FILE, snoozed)
        return True
    except Exception:
        return False


# --- 숨김(완료/제외) 앵커 dict 로드/저장 (Feature 1: 새 메일 시 자동 해제) ----
#  형식: {제목: anchor최근}. anchor = 숨길 당시 스레드의 최근(최신 메일 시각 문자열).
#  구버전(list) 자동 마이그레이션: 현재 최근을 앵커로 사용 → 더 새 메일 와야 해제.

def _load_anchor_map(path, current_recent):
    """숨김 파일을 {제목: anchor} dict 로 로드. list(구버전)면 current_recent 로 마이그레이션.
    current_recent: {제목: 현재최근} (build_data 기준). 변경 시 파일에 반영."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    migrated = False
    if isinstance(raw, list):
        # 마이그레이션: 현재 최근을 앵커로 (없으면 빈 문자열 → 다음 메일에 해제)
        raw = {k: (current_recent.get(k, "")) for k in raw}
        migrated = True
    elif not isinstance(raw, dict):
        return {}
    if migrated:
        _save_anchor_map(path, raw)
    return raw


def _save_anchor_map(path, amap):
    try:
        state_io.write_json(path, amap)
        return True
    except Exception:
        return False


def _append_done_log(key):
    """완료 이력에 항목 추가. 90일 초과 항목 자동 정리."""
    try:
        with state_io.lock(DONE_LOG_FILE):
            if os.path.exists(DONE_LOG_FILE):
                with open(DONE_LOG_FILE, encoding="utf-8") as f:
                    log = json.load(f)
            else:
                log = []
            ts = datetime.now().isoformat(timespec="seconds")
            log.append({"key": key, "ts": ts})
            cutoff = (datetime.now() - timedelta(days=MAX_AGE_DAYS)).isoformat()
            log = [e for e in log if isinstance(e, dict) and e.get("ts", "") >= cutoff]
            state_io.write_json(DONE_LOG_FILE, log)
    except Exception:
        pass


# --- 수동 TODO 로드/저장 (widget_mytodos.json) ---------------------------

def _load_mytodos():
    """[{"id":str,"text":str,"done":bool}, ...]. 실패 시 빈 리스트."""
    try:
        with open(MYTODOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError, json.JSONDecodeError):
        return []


def _save_mytodos(items):
    try:
        state_io.write_json(MYTODOS_FILE, items)
        return True
    except Exception:
        return False


def _next_todo_id(items):
    """기존 id 중 최대 정수 + 1 (문자열). 없으면 "1"."""
    mx = 0
    for it in items:
        try:
            n = int(it.get("id", 0))
            if n > mx:
                mx = n
        except (TypeError, ValueError):
            pass
    return str(mx + 1)


# --- 메모 로드/저장 (widget_memos.json) ------------------------------------
# 형식: [{"id":str,"text":str,"start":ISO,"deadline":ISO|null}]

def _load_memos():
    try:
        with open(MEMOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError, json.JSONDecodeError):
        return []

def _save_memos(items):
    try:
        state_io.write_json(MEMOS_FILE, items)
        return True
    except Exception:
        return False


def _load_project_cards():
    try:
        if not os.path.exists(PROJECT_CARDS_FILE):
            os.makedirs(os.path.dirname(PROJECT_CARDS_FILE), exist_ok=True)
            state_io.write_json(PROJECT_CARDS_FILE, [])
            return []
        with open(PROJECT_CARDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return []


def _load_tags():
    """widget_tags.json — {norm_subject: ["미읽음"|"TODO"|"미회신", ...]}"""
    try:
        with open(TAGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _next_memo_id(items):
    mx = 0
    for it in items:
        try:
            n = int(it.get("id", 0))
            if n > mx: mx = n
        except (TypeError, ValueError):
            pass
    return str(mx + 1)


# --- VIP 발신자 로드/저장 (widget_vip.json) — 소문자 이메일 리스트 -----------

def _load_vip():
    try:
        with open(VIP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [str(e).lower() for e in data] if isinstance(data, list) else []
    except (OSError, ValueError, json.JSONDecodeError):
        return []


def _save_vip(items):
    try:
        state_io.write_json(VIP_FILE, sorted(set(items)))
        return True
    except Exception:
        return False


# --- 메일별 메모 로드/저장 (widget_notes.json) — {제목: 메모문자열} ---

def _load_notes():
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _save_notes(notes):
    try:
        state_io.write_json(NOTES_FILE, notes)
        return True
    except Exception:
        return False


def _is_vip(sender, vips):
    """발신자 문자열이 VIP 이메일 중 하나를 부분 포함하면 True (대소문자 무시)."""
    if not sender or not vips:
        return False
    s = str(sender).lower()
    return any(v and v in s for v in vips)


def _sort_vip_deadline(items):
    """안정 정렬로 (1) VIP 우선 (2) 마감 있는 항목 임박순 (3) 기존 순서 유지.
    파이썬 sort 는 안정적이므로 마감순 → VIP순 순서로 적용한다."""
    # 마감 있는 항목 임박순(asc) 먼저, 마감 없는 항목은 뒤(기존 순서 유지)
    items = sorted(items, key=lambda t: (t.get("마감D") is None,
                                         t.get("마감D") if t.get("마감D") is not None else 0))
    # VIP 를 맨 위로 (안정 정렬 — 위 마감 순서 보존)
    items = sorted(items, key=lambda t: not t.get("vip"))
    return items


# --- Feature 4: OS 토스트 (백그라운드 스레드 — toast 가 블로킹 가능) ---

def _fire_toast(title, body):
    if _toast is None:
        try:
            import winsound
            winsound.MessageBeep()
        except Exception:
            pass
        return

    def _run():
        try:
            _toast(title, body)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


# --- 프로젝트 규칙 로드/저장 (widget_projects.json) -----------------------

def _save_project_rules(rules):
    try:
        state_io.write_json(build_dashboard.PROJECTS_FILE, rules)
        return True
    except Exception:
        return False


def _prep_view(data):
    """build_data() 결과를 위젯 표시용 구조로 가공한다 (widget.prep_view 이식)."""
    summary = data.get("summary", {})
    todos = data.get("todos", [])
    threads = data.get("threads", [])
    table = data.get("table", [])

    # 미회신: 회신 대기 스레드 중 내부(사내 도메인) 발신자 제외, 경과일 desc 정렬
    _internal_domain = getattr(build_dashboard, "INTERNAL_DOMAIN", "")
    replies = [t for t in threads
               if t.get("상태") == "회신 대기"
               and (not _internal_domain
                    or _internal_domain not in (t.get("답장주소", "") or "").lower())]
    replies.sort(key=lambda t: (t.get("경과일") is None, -(t.get("경과일") or 0)))

    # 긴급/마감: 받은메일 중 키워드 포함
    urgent = []
    for r in table:
        if r.get("구분") != "받음":
            continue
        if _is_urgent(r.get("제목", ""), r.get("요약", "")):
            urgent.append({
                "제목": r.get("제목", ""),
                "보낸사람": r.get("상대", ""),
                "날짜": r.get("날짜", ""),
                "미읽음": r.get("미읽음", False),
                "링크": r.get("링크", ""),
            })

    # TODO 에서 긴급(제목 중복) 제거
    urgent_titles = {u["제목"] for u in urgent}
    rest = [t for t in todos if t.get("제목", "") not in urgent_titles]

    # 미읽음 메일 (table 중 미읽음만, 표는 이미 최신순)
    unread = [{"제목": r.get("제목", ""), "상대": r.get("상대", ""),
               "날짜": r.get("날짜", ""), "링크": r.get("링크", "")}
              for r in table if r.get("미읽음")]

    return {
        "counts": {
            "미읽음": summary.get("미읽음", 0),
            "TODO": summary.get("TODO수", 0),
            "미회신": len(replies),
        },
        "urgent": urgent,
        "replies": replies,
        "todos": rest,
        "unread": unread,
        "projects": data.get("projects", []),
        "stats": data.get("stats", {}),
        "갱신시각": summary.get("갱신시각", ""),
    }


class Api:
    """window.pywebview.api.<name> 로 JS 에서 호출되는 메서드 모음."""

    def __init__(self):
        self._window = None
        self._last_view = None  # 마지막 성공 뷰 (오류/빈 데이터 시 유지)
        # 토스트 알림용 세션 추적 (첫 get_view 는 기준선만, 알림 무음)
        self._seen_replies = None   # set(회신대기 제목) — None=첫 호출
        self._seen_aged = set()     # 14일+ 경과 제목 집합

    def set_window(self, window):
        self._window = window

    # --- 단일 데이터 소스 ---
    def get_view(self):
        """build_data() → 상태 필터 적용 → JSON-ready dict. JS 가 로드/2분마다 호출."""
        try:
            data = build_dashboard.build_data()
        except Exception:
            return self._last_view or self._empty_view()
        if data.get("summary", {}).get("총건수", 0) <= 0:
            return self._last_view or self._empty_view()

        # 제목 앞 '광고' 머리표 제거 (표시·상태키 일관 위해 데이터 진입 시 일괄)
        for _k in ("todos", "threads", "table"):
            for _r in data.get(_k, []):
                _r["제목"] = _strip_ad(_r.get("제목", ""))
        for _p in data.get("projects", []):
            for _t in _p.get("threads", []):
                _t["제목"] = _strip_ad(_t.get("제목", ""))

        view = _prep_view(data)

        # 전체 메일(참조 포함). done/exclude/snooze 필터 미적용 — 풀 아카이브.
        full_table = data.get("table", [])

        # 현재 최근(최신 메일 시각) 맵 — Feature 1 자동 해제 비교 기준
        current_recent = {t.get("제목"): (t.get("최근") or "")
                          for t in data.get("threads", [])}

        # 숨김 파일 로드 (dict 앵커, 구버전 list 자동 마이그레이션)
        excluded = _load_anchor_map(EXCLUDE_FILE, current_recent)
        done = _load_anchor_map(DONE_FILE, current_recent)
        snoozed = _load_snoozed()

        # --- Feature 1: 새 메일 도착 시 자동 해제 ---
        #  스레드의 현재 최근 > 저장 앵커 → 새 활동 → 숨김 해제(파일에서 제거).
        def _release(amap):
            cleaned, changed = {}, False
            for k, anchor in amap.items():
                cur = current_recent.get(k)
                if cur is not None and (anchor or "") and cur > anchor:
                    changed = True            # 새 메일 → drop (자동 해제)
                    continue
                cleaned[k] = anchor
            return cleaned, changed

        excluded, ex_ch = _release(excluded)
        done, dn_ch = _release(done)
        if ex_ch:
            _save_anchor_map(EXCLUDE_FILE, excluded)
        if dn_ch:
            _save_anchor_map(DONE_FILE, done)

        # 스누즈 자동 해제: 현재 최근이 스누즈 당시 앵커보다 새로우면 조기 해제
        sn_ch = False
        for k in list(snoozed.keys()):
            anchor = snoozed[k].get("anchor")
            cur = current_recent.get(k)
            if cur is not None and anchor and cur > anchor:
                del snoozed[k]
                sn_ch = True
        if sn_ch:
            _save_snoozed(snoozed)

        excluded_keys = set(excluded.keys())
        done_keys = set(done.keys())

        # VIP / 중요 / 메모 로드
        vips = _load_vip()
        important = _load_set(IMPORTANT_FILE)  # {제목, ...} 사용자가 ★ 체크한 메일
        notes = _load_notes()                  # {제목: 메모} 메일별 메모

        # 4건 이상 메일 루프 → 별도 auto_important 집합 (사용자 ★ 토글과 분리)
        auto_important = {
            _t.get("제목", "") for _t in data.get("threads", [])
            if (_t.get("건수") or 0) >= 4
        }

        # 미회신(회신대기): 제외/스누즈/완료 숨김
        hidden_replies = excluded_keys | set(snoozed.keys()) | done_keys
        replies = [t for t in view["replies"]
                   if t.get("제목") not in hidden_replies]

        # urgent/todos/unread: 완료(done)만 숨김
        urgent = [t for t in view["urgent"] if t.get("제목") not in done_keys]
        todos = [t for t in view["todos"] if t.get("제목") not in done_keys]
        unread = [t for t in view["unread"] if t.get("제목") not in done_keys]

        # --- Feature 3: VIP 표시 (발신자/답장주소 기준) ---
        for t in todos:
            t["vip"] = _is_vip(t.get("보낸사람"), vips)
        for t in urgent:
            t["vip"] = _is_vip(t.get("보낸사람"), vips)
        for t in replies:
            t["vip"] = _is_vip(t.get("답장주소"), vips)
        for r in full_table:
            r["vip"] = _is_vip(r.get("상대"), vips)

        # --- 중요(★) / 루프중요 / 메모 표시: 제목 기준 ---
        for lst in (todos, urgent, replies, unread, full_table):
            for t in lst:
                t["중요"] = t.get("제목") in important          # 사용자 ★ (토글 가능)
                t["루프"] = t.get("제목") in auto_important     # 4건+ 자동 (표시 전용)
                t["메모"] = notes.get(t.get("제목"), "")

        # --- 수동 태그 (widget_tags.json): 전체 뷰 행에 태그 부착 + 해당 섹션에 주입 ---
        tags = _load_tags()
        unread_titles = {t.get("제목") for t in unread}
        todo_titles   = {t.get("제목") for t in todos}
        reply_titles  = {t.get("제목") for t in replies}
        for row in full_table:
            nk = build_dashboard.norm_subject(row.get("제목", ""))
            row_tags = tags.get(nk, [])
            row["태그"] = row_tags
            if not row_tags or nk in done_keys:
                continue
            subj = row.get("제목", "")
            if "미읽음" in row_tags and subj not in unread_titles:
                unread.append({"제목": subj, "상대": row.get("상대", ""),
                               "날짜": row.get("날짜", ""), "링크": row.get("링크", ""),
                               "중요": row.get("중요", False), "루프": row.get("루프", False),
                               "vip": row.get("vip", False), "메모": row.get("메모", "")})
                unread_titles.add(subj)
            if "TODO" in row_tags and subj not in todo_titles and row.get("구분") != "보냄":
                todos.append({"제목": subj, "보낸사람": row.get("상대", ""),
                              "날짜": row.get("날짜", ""), "링크": row.get("링크", ""),
                              "미읽음": row.get("미읽음", False), "루프": row.get("루프", False),
                              "중요": row.get("중요", False), "vip": row.get("vip", False),
                              "메모": row.get("메모", "")})
                todo_titles.add(subj)
            if "미회신" in row_tags and nk not in hidden_replies and subj not in reply_titles and row.get("구분") != "보냄":
                replies.append({"제목": subj, "보낸사람": row.get("상대", ""),
                                "날짜": row.get("날짜", ""), "링크": row.get("링크", ""),
                                "경과일": None, "루프": row.get("루프", False),
                                "중요": row.get("중요", False), "vip": row.get("vip", False),
                                "메모": row.get("메모", ""), "답장주소": row.get("상대", ""), "건수": 1})
                reply_titles.add(subj)

        # --- 정렬: (중요 or 루프) 우선 → VIP 우선 → 마감 임박순 → 기존 순서 ---
        def _is_important(t):
            return t.get("중요") or t.get("루프")
        todos = _sort_vip_deadline(todos)
        replies = _sort_vip_deadline(replies)
        todos.sort(key=lambda t: not _is_important(t))
        replies.sort(key=lambda t: not _is_important(t))

        # 프로젝트: 회신대기 1건+ 인 것만, threads 도 제외/스누즈/완료 숨김 + VIP 표시
        projects = []
        for p in view["projects"]:
            waiting = [t for t in p.get("threads", [])
                       if t.get("상태") == "회신 대기"
                       and t.get("제목") not in hidden_replies]
            for t in waiting:
                t["vip"] = _is_vip(t.get("답장주소"), vips)
                t["중요"] = t.get("제목") in important
                t["루프"] = t.get("제목") in auto_important
                t["메모"] = notes.get(t.get("제목"), "")
            if waiting:
                projects.append({
                    "프로젝트": p.get("프로젝트", "기타"),
                    "건수": p.get("건수", 0),
                    "미회신수": len(waiting),
                    "threads": _sort_vip_deadline(waiting),
                })

        # --- Feature 4: 새 미회신 / 14일+ 경과 OS 토스트 ---
        self._maybe_toast(replies)

        out = {
            "counts": {  # 카드 = 실제 보이는 개수 (완료/제외 반영)
                "미읽음": len(unread),
                "TODO": len(todos),
                "사내": sum(1 for t in todos if t.get("내부여부")),
                "외부요청": sum(1 for t in todos if (not t.get("내부여부")) and t.get("참조요청")),
                "미회신": len(replies),
                "긴급": len(urgent),
            },
            "urgent": urgent,
            "replies": replies,
            "todos": todos,
            "unread": unread,
            "projects": projects,
            "stats": view["stats"],
            "table": full_table,
            "mytodos": _load_mytodos(),
            "memos": _load_memos(),
            "갱신시각": view["갱신시각"],
            "project_cards": [],
        }

        # project_cards 주입
        try:
            _raw_cards = _load_project_cards()
            _proj_cards_out = []
            for _c in _raw_cards:
                _mails = build_dashboard.get_card_mails(
                    _c,
                    done_keys=done_keys,
                    excluded_keys=excluded_keys
                )
                _stage = build_dashboard.get_card_stage(_c)
                _proj_cards_out.append({
                    "id": _c.get("id"),
                    "name": _c.get("name"),
                    "senders": _c.get("senders", []),
                    "milestones": _c.get("milestones", []),
                    "mails": _mails,
                    "stage": _stage,
                    "color": _c.get("color", "blue"),
                })
            out["project_cards"] = _proj_cards_out
        except Exception as _e:
            out["project_cards"] = []

        self._last_view = out
        return out

    # --- Feature 4: 토스트 알림 (백그라운드 스레드) ---
    def _maybe_toast(self, replies):
        cur = {t.get("제목") for t in replies}
        aged = {t.get("제목") for t in replies if (t.get("경과일") or 0) >= 14}
        if self._seen_replies is None:        # 첫 호출: 기준선만, 무음
            self._seen_replies = cur
            self._seen_aged = aged
            return
        new_replies = len(cur - self._seen_replies)
        new_aged = len(aged - self._seen_aged)
        self._seen_replies = cur
        self._seen_aged = aged
        if not (new_replies or new_aged):
            return
        parts = []
        if new_replies:
            parts.append("새 미회신 " + str(new_replies) + "건")
        if new_aged:
            parts.append("14일+ 경과 " + str(new_aged) + "건")
        _fire_toast("Outlook 메일", "  ·  ".join(parts))

    def _empty_view(self):
        return {
            "counts": {"미읽음": 0, "TODO": 0, "미회신": 0, "긴급": 0},
            "urgent": [], "replies": [], "todos": [], "unread": [],
            "projects": [], "stats": {}, "table": [], "mytodos": [],
            "memos": [], "project_cards": [], "갱신시각": "",
        }

    # --- 원본 메일 열기 (OWA 링크) ---
    def open_link(self, url):
        if not url:
            return {"ok": False, "error": "no link"}
        try:
            webbrowser.open(url)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # --- 바로 답장(↩): mailto 작성창 (idempotent Re:) ---
    def reply(self, addr, subject):
        if not addr:
            return {"ok": False, "error": "no address"}
        subj = subject or ""
        if subj and not subj.lower().startswith("re:"):
            subj = "Re: " + subj
        url = "mailto:" + urllib.parse.quote(addr)
        if subj:
            url += "?subject=" + urllib.parse.quote(subj)
        try:
            webbrowser.open(url)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # --- 앵커 조회: 스레드 현재 최근(최신 메일 시각). 없으면 "". (Feature 1) ---
    def _anchor_for(self, key):
        try:
            data = build_dashboard.build_data()
        except Exception:
            return ""
        for t in data.get("threads", []):
            if t.get("제목") == key:
                return t.get("최근") or ""
        return ""

    # --- 완료(✓): widget_done.json — {제목: 앵커최근} 영구 추가 ---
    def mark_done(self, key):
        if not key:
            return {"ok": False}
        done = _load_anchor_map(DONE_FILE, {})
        done[key] = self._anchor_for(key)
        _save_anchor_map(DONE_FILE, done)
        _append_done_log(key)
        return {"ok": True}

    # --- 스누즈(💤): {key: {"until": ISO+3일, "anchor": 최근}} ---
    def snooze(self, key, days=None):
        if not key:
            return {"ok": False}
        try:
            days = int(days) if days is not None else SNOOZE_DAYS
        except (TypeError, ValueError):
            days = SNOOZE_DAYS
        if days not in (1, 3, 7):
            days = SNOOZE_DAYS
        snoozed = _load_snoozed()
        until = (datetime.now() + timedelta(days=days)).date().isoformat()
        snoozed[key] = {"until": until, "anchor": self._anchor_for(key)}
        _save_snoozed(snoozed)
        return {"ok": True}

    def get_done_count_today(self):
        """오늘 로컬 자정 기준 완료 건수."""
        try:
            if not os.path.exists(DONE_LOG_FILE):
                return 0
            today = datetime.now().date().isoformat()
            with open(DONE_LOG_FILE, encoding="utf-8") as f:
                log = json.load(f)
            return sum(1 for e in log if isinstance(e, dict) and e.get("ts", "").startswith(today))
        except Exception:
            return 0

    def get_hidden(self):
        """done/excluded/snooze 숨긴 항목을 소스 라벨과 함께 반환."""
        done = _load_anchor_map(DONE_FILE, {})
        excluded = _load_anchor_map(EXCLUDE_FILE, {})
        snoozed = _load_snoozed()
        items = []
        for key in done:
            items.append({"key": key, "kind": "done", "label": "완료"})
        for key in excluded:
            items.append({"key": key, "kind": "excluded", "label": "제외"})
        for key, v in snoozed.items():
            until = v.get("until", "") if isinstance(v, dict) else str(v)
            items.append({"key": key, "kind": "snooze", "label": f"스누즈({until}까지)"})
        return items

    def unhide(self, key, kind):
        """숨긴 항목 수동 해제."""
        if not key or not kind:
            return {"ok": False}
        if kind == "done":
            amap = _load_anchor_map(DONE_FILE, {})
            amap.pop(key, None)
            _save_anchor_map(DONE_FILE, amap)
        elif kind == "excluded":
            amap = _load_anchor_map(EXCLUDE_FILE, {})
            amap.pop(key, None)
            _save_anchor_map(EXCLUDE_FILE, amap)
        elif kind == "snooze":
            snoozed = _load_snoozed()
            snoozed.pop(key, None)
            _save_snoozed(snoozed)
        else:
            return {"ok": False, "msg": "알 수 없는 kind"}
        return {"ok": True}

    def delete_item(self, key):
        """mailbox.json에서 해당 제목 키의 메시지를 영구 삭제."""
        if not key:
            return {"ok": False}
        try:
            rows = []
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, encoding="utf-8") as f:
                    rows = json.load(f)
            norm_key = build_dashboard.norm_subject(key)
            kept = [r for r in rows if build_dashboard.norm_subject(r.get("제목", "")) != norm_key]
            with state_io.lock(JSON_FILE):
                state_io.write_json(JSON_FILE, kept)
            # 메일을 지웠으면 숨김 앵커(완료/제외/스누즈)도 함께 제거 — 안 그러면
            # get_hidden 이 계속 반환해 숨김 패널에서 사라지지 않음.
            done = _load_anchor_map(DONE_FILE, {})
            if done.pop(key, None) is not None:
                _save_anchor_map(DONE_FILE, done)
            excluded = _load_anchor_map(EXCLUDE_FILE, {})
            if excluded.pop(key, None) is not None:
                _save_anchor_map(EXCLUDE_FILE, excluded)
            snoozed = _load_snoozed()
            if snoozed.pop(key, None) is not None:
                _save_snoozed(snoozed)
            return {"ok": True, "deleted": len(rows) - len(kept)}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    # --- 제외(✕): widget_excluded.json — {제목: 앵커최근} 추가 ---
    def exclude(self, key):
        if not key:
            return {"ok": False}
        excluded = _load_anchor_map(EXCLUDE_FILE, {})
        excluded[key] = self._anchor_for(key)
        _save_anchor_map(EXCLUDE_FILE, excluded)
        return {"ok": True}

    # --- VIP 발신자 조회/추가/삭제 (Feature 3) ---
    def get_vip(self):
        return _load_vip()

    def add_vip(self, email):
        email = (email or "").strip().lower()
        if not email:
            return {"ok": False}
        vips = _load_vip()
        if email not in vips:
            vips.append(email)
            _save_vip(vips)
        return {"ok": True}

    def del_vip(self, email):
        email = (email or "").strip().lower()
        vips = [v for v in _load_vip() if v != email]
        _save_vip(vips)
        return {"ok": True}

    # --- 중요(★) 메일 토글: widget_important.json (제목 집합) ---
    def toggle_important(self, key):
        if not key:
            return {"ok": False}
        items = _load_set(IMPORTANT_FILE)
        if key in items:
            items.discard(key)
            now_important = False
        else:
            items.add(key)
            now_important = True
        _save_set(IMPORTANT_FILE, items)
        return {"ok": True, "important": now_important}

    # --- 수동 태그 토글: widget_tags.json {norm_subject: [tag, ...]} ---
    def tag_mail(self, key, tag):
        """tag ∈ {"미읽음","TODO","미회신"}. 이미 있으면 제거, 없으면 추가 (토글)."""
        if not key or tag not in ("미읽음", "TODO", "미회신"):
            return {"ok": False}
        nk = build_dashboard.norm_subject(key)
        tags = _load_tags()
        cur = tags.get(nk, [])
        if tag in cur:
            cur = [t for t in cur if t != tag]
            on = False
        else:
            cur = cur + [tag]
            on = True
        if cur:
            tags[nk] = cur
        else:
            tags.pop(nk, None)
        state_io.write_json(TAGS_FILE, tags)
        return {"ok": True, "on": on}

    # --- 메일별 메모 조회/저장 (widget_notes.json) ---
    def get_note(self, key):
        if not key:
            return ""
        return _load_notes().get(key, "")

    def set_note(self, key, text):
        if not key:
            return {"ok": False}
        notes = _load_notes()
        text = (text or "").strip()
        if text:
            notes[key] = text
        else:
            notes.pop(key, None)   # 빈 메모 = 삭제
        _save_notes(notes)
        return {"ok": True, "note": text}

    def _open_html(self, path):
        """HTML 파일을 기본 브라우저로 열고 위젯을 minimize해 브라우저가 보이게 한다."""
        try:
            os.startfile(path)
        except (AttributeError, OSError):
            webbrowser.open("file:///" + path.replace("\\", "/"))
        try:
            if self._window:
                self._window.minimize()
        except Exception:
            pass

    # --- 주간 리포트 생성 + 열기 ---
    def gen_report(self):
        try:
            path = build_dashboard.build_weekly_report()
        except Exception as e:
            return {"ok": False, "error": str(e)}
        self._open_html(path)
        return {"ok": True, "path": path}

    # --- 주간 업무 회고 생성 + 열기 (내가 보낸 메일 중심, 최근 7일) ---
    def open_weekly_review(self):
        try:
            import weekly_review
            path = weekly_review.build_weekly_review()
        except Exception as e:
            return {"ok": False, "error": str(e)}
        self._open_html(path)
        return {"ok": True, "path": path}

    # --- 창 위치/크기 저장 (on close) ---
    def save_pos(self):
        w = self._window
        if w is None:
            return {"ok": False}
        try:
            x, y, ww, wh = int(w.x), int(w.y), int(w.width), int(w.height)
            # 최소화/화면 밖(-32000 등)·비정상 크기면 저장 skip (다음 실행 시 안 보이는 문제 방지)
            if x <= -10000 or y <= -10000 or ww < 300 or wh < 300:
                return {"ok": False, "skipped": "offscreen"}
            state_io.write_json(POS_FILE, {"x": x, "y": y, "w": ww, "h": wh})
            return {"ok": True}
        except (OSError, AttributeError, ValueError, TypeError):
            return {"ok": False}

    # --- 메일 셀프 업데이트 (수동 새로고침) ---
    def update_mail(self):
        """fetch_mail.main(auto=True) 로 Graph 에서 재수집 → mailbox.json 갱신."""
        try:
            import fetch_mail
            result = fetch_mail.main(auto=True)
            if result is None:
                result = {"ok": True, "auth_required": False, "new": 0, "msg": "완료"}
            return result
        except Exception as e:
            return {"ok": False, "auth_required": False, "new": 0, "msg": "업데이트 실패: " + str(e)}

    # --- 사용자 API 설정 ---
    def get_settings(self):
        uc = _load_user_config()
        return {
            "client_id": uc.get("CLIENT_ID", getattr(config, "CLIENT_ID", "")),
            "tenant_id": uc.get("TENANT_ID", getattr(config, "TENANT_ID", "")),
            "my_email":  uc.get("MY_EMAIL",  getattr(config, "MY_EMAIL",  "")),
            "my_name":   uc.get("MY_NAME",   getattr(config, "MY_NAME",   "")),
            "max_emails": uc.get("MAX_EMAILS", getattr(config, "MAX_EMAILS", 50)),
        }

    def save_settings(self, payload):
        try:
            uc = _load_user_config()
            if payload.get("client_id") is not None: uc["CLIENT_ID"]   = payload["client_id"].strip()
            if payload.get("tenant_id") is not None: uc["TENANT_ID"]   = payload["tenant_id"].strip()
            if payload.get("my_email")  is not None: uc["MY_EMAIL"]    = payload["my_email"].strip()
            if payload.get("my_name")   is not None: uc["MY_NAME"]     = payload["my_name"].strip()
            if payload.get("max_emails") is not None: uc["MAX_EMAILS"] = int(payload["max_emails"])
            os.makedirs(STATE_DIR, exist_ok=True)
            state_io.write_json(USER_CONFIG_FILE, uc)
            _apply_user_config()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def reauth(self):
        """토큰 만료 시 인터랙티브 재인증 (별도 스레드로 실행, UI 스레드 블로킹 방지)."""
        def _do_reauth():
            try:
                import fetch_mail
                fetch_mail.get_token(auto=False)
                fetch_mail.log("재인증 완료.")
            except Exception as e:
                fetch_mail.log(f"재인증 실패: {e}")
        threading.Thread(target=_do_reauth, daemon=True).start()
        return {"ok": True, "msg": "재인증 시작됨"}

    # --- 수동 TODO 추가 ---
    def add_todo(self, text, deadline=None):
        text = (text or "").strip()
        if not text:
            return {"ok": False}
        items = _load_mytodos()
        items.append({"id": _next_todo_id(items), "text": text, "done": False,
                      "deadline": (deadline or "").strip() or None})
        _save_mytodos(items)
        return {"ok": True}

    # --- 수동 TODO 완료 토글 (done=True) ---
    def done_todo(self, tid):
        items = _load_mytodos()
        for it in items:
            if str(it.get("id")) == str(tid):
                it["done"] = True
        _save_mytodos(items)
        return {"ok": True}

    # --- 수동 TODO 삭제 ---
    def del_todo(self, tid):
        items = [it for it in _load_mytodos() if str(it.get("id")) != str(tid)]
        _save_mytodos(items)
        return {"ok": True}

    # --- 메모 추가 ---
    def add_memo(self, text, start, deadline):
        text = (text or "").strip()
        if not text:
            return {"ok": False}
        items = _load_memos()
        items.append({"id": _next_memo_id(items), "text": text,
                       "start": start or datetime.now().date().isoformat(),
                       "deadline": deadline or None})
        _save_memos(items)
        return {"ok": True}

    # --- 메모 수정 ---
    def edit_memo(self, mid, text, deadline):
        items = _load_memos()
        for it in items:
            if str(it.get("id")) == str(mid):
                if text is not None: it["text"] = (text or "").strip()
                it["deadline"] = deadline or None
                break
        _save_memos(items)
        return {"ok": True}

    # --- 메모 삭제 ---
    def del_memo(self, mid):
        items = [it for it in _load_memos() if str(it.get("id")) != str(mid)]
        _save_memos(items)
        return {"ok": True}

    # --- 프로젝트 카드 조회 ---
    def get_project_cards(self):
        return _load_project_cards()

    # --- 프로젝트 카드 추가 ---
    def add_project_card(self, name):
        name = (name or "").strip()
        if not name:
            return {"ok": False, "msg": "name 필수"}
        try:
            new_card = {"id": str(uuid4()), "name": name, "senders": [], "milestones": []}
            cards = _load_project_cards()
            cards.append(new_card)
            with state_io.lock(PROJECT_CARDS_FILE):
                state_io.write_json(PROJECT_CARDS_FILE, cards)
            return {"ok": True, "card": new_card}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    # --- 프로젝트 카드 수정 ---
    def update_project_card(self, id, payload):
        try:
            cards = _load_project_cards()
            for card in cards:
                if card.get("id") == id:
                    if "name" in payload:
                        card["name"] = payload["name"]
                    if "senders" in payload:
                        card["senders"] = payload["senders"]
                    if "keywords" in payload:
                        card["keywords"] = payload["keywords"]
                    if "milestones" in payload:
                        card["milestones"] = payload["milestones"]
                    if "color" in payload:
                        card["color"] = payload["color"]
                    with state_io.lock(PROJECT_CARDS_FILE):
                        state_io.write_json(PROJECT_CARDS_FILE, cards)
                    return {"ok": True}
            return {"ok": False, "msg": "카드를 찾을 수 없음"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    # --- 프로젝트 카드 삭제 ---
    def del_project_card(self, id):
        try:
            cards = _load_project_cards()
            new_cards = [c for c in cards if c.get("id") != id]
            if len(new_cards) == len(cards):
                return {"ok": False, "msg": "카드를 찾을 수 없음"}
            with state_io.lock(PROJECT_CARDS_FILE):
                state_io.write_json(PROJECT_CARDS_FILE, new_cards)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    # --- 프로젝트 규칙 조회 ---
    def get_project_rules(self):
        return build_dashboard.load_project_rules()

    # --- 프로젝트 규칙 저장 (발신자/키워드 자동 분류) ---
    def save_project(self, name, senders):
        name = (name or "").strip()
        if not name:
            return {"ok": False}
        # 쉼표/공백/줄바꿈 구분 → 리스트
        parts = [p.strip() for p in re.split(r"[,\s]+", senders or "") if p.strip()]
        rules = build_dashboard.load_project_rules()
        rules[name] = parts
        _save_project_rules(rules)
        return {"ok": True}

    # --- 프로젝트 규칙 삭제 ---
    def del_project(self, name):
        rules = build_dashboard.load_project_rules()
        rules.pop(name, None)
        _save_project_rules(rules)
        return {"ok": True}

    def assign_sender_to_project(self, email, project):
        """발신자 이메일을 특정 프로젝트에 매핑. widget_projects.json에 atomic 저장."""
        email = (email or "").strip().lower()
        project = (project or "").strip()
        if not email or not project:
            return {"ok": False, "msg": "email/project 필수"}
        try:
            if os.path.exists(PROJECTS_FILE):
                with open(PROJECTS_FILE, encoding="utf-8") as f:
                    projects = json.load(f)
            else:
                projects = {}
            if project not in projects:
                projects[project] = {"senders": [], "keywords": [], "subjects": []}
            senders = projects[project].setdefault("senders", [])
            if email not in senders:
                senders.append(email)
            with state_io.lock(PROJECTS_FILE):
                state_io.write_json(PROJECTS_FILE, projects)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def get_projects(self):
        """현재 프로젝트 목록 반환 (이름 리스트)."""
        try:
            if not os.path.exists(PROJECTS_FILE):
                return []
            with open(PROJECTS_FILE, encoding="utf-8") as f:
                projects = json.load(f)
            return list(projects.keys())
        except Exception:
            return []


def _load_user_config():
    try:
        if os.path.exists(USER_CONFIG_FILE):
            with open(USER_CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _apply_user_config():
    for k, v in _load_user_config().items():
        setattr(config, k, v)

_apply_user_config()


def _restore_pos():
    """저장된 창 위치/크기를 (x, y, w, h) 로 반환. 없으면 (None, None, W, H).

    화면 밖 좌표(최소화 시 Windows 가 -32000 저장)·비정상 크기는 기본값으로 보정 —
    창이 보이지 않는 문제 방지.
    """
    try:
        with open(POS_FILE, "r", encoding="utf-8") as f:
            pos = json.load(f)
        x, y = int(pos.get("x")), int(pos.get("y"))
        w, h = int(pos.get("w", WIN_W)), int(pos.get("h", WIN_H))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return (None, None, WIN_W, WIN_H)
    # 화면 밖(최소화 sentinel 등) → 위치 미지정(기본 위치)
    if x <= -10000 or y <= -10000 or x > 20000 or y > 20000:
        x = y = None
    # 비정상 크기 → 기본 크기
    if w < 300:
        w = WIN_W
    if h < 300:
        h = WIN_H
    return (x, y, w, h)


if __name__ == "__main__":
    import webview

    api = Api()
    x, y, w, h = _restore_pos()

    win_kwargs = dict(
        title="Outlook 메일",
        url=UI_FILE,
        js_api=api,
        width=w,
        height=h,
        on_top=True,
        resizable=True,
        # frameless(커스텀 타이틀바) 는 JS→pywebview 브릿지→SetWindowPos 왕복
        # 구조 때문에 리사이즈가 구조적으로 버벅여서 포기 — Windows 기본 프레임
        # (네이티브 SC_SIZE)으로 확정. 리사이즈/이동 모두 OS가 직접 처리한다.
        frameless=False,
        min_size=(280, 380),
    )
    if x is not None and y is not None:
        win_kwargs["x"] = x
        win_kwargs["y"] = y

    window = webview.create_window(**win_kwargs)
    api.set_window(window)

    # 닫기 직전 위치/크기 저장
    window.events.closing += lambda: api.save_pos()

    # http_port 고정: 랜덤 포트가 Chromium 의 unsafe port 목록(예: 6666,
    # IRC 대역)에 걸리면 ERR_UNSAFE_PORT 로 로드 자체가 실패한다.
    webview.start(http_port=48200)
