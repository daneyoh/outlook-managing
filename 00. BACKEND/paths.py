# ============================================================
#  경로 단일 소스 (Phase 1.5.1)
#  - 모든 파일시스템 경로 상수를 이 모듈이 소유한다.
#  - app / build_dashboard / fetch_mail / fetch_loop / weekly_review
#    다섯 모듈이 각자 재정의하던 경로를 여기서 한 번만 정의하고 가져다 쓴다.
#
#  LEAF MODULE: os / sys 만 import 한다. app·build_dashboard·config 등
#  프로젝트 모듈을 절대 import 하지 않는다 (순환 import 재발 방지).
#
#  ROOT 도출은 frozen-aware 방식으로 통일한다.
#  - app.py / fetch_mail.py / weekly_review.py 는 이미 frozen 분기를 갖고 있었고
#    (frozen → dirname(sys.executable)), build_dashboard.py / fetch_loop.py 는
#    dirname(abspath(__file__)) 만 썼다. PyInstaller .exe 는 frozen 으로 배포되므로
#    frozen-aware 도출을 단일 기준으로 삼아, 개발/배포 양쪽에서 모든 모듈이 동일한
#    ROOT 를 갖도록 한다.
# ============================================================

import os
import sys

if getattr(sys, "frozen", False):
    # PyInstaller: 실행 파일이 프로젝트 루트에 놓인다.
    HERE = os.path.dirname(sys.executable)
    ROOT = os.path.dirname(sys.executable)
    # _MEIPASS = _internal/ (번들된 데이터 파일 위치)
    _MEIPASS = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    UI_FILE = os.path.join(_MEIPASS, "ui.html")
else:
    HERE = os.path.dirname(os.path.abspath(__file__))   # 00. BACKEND
    ROOT = os.path.dirname(HERE)                          # 프로젝트 루트 (backend의 부모)
    UI_FILE = os.path.join(ROOT, "01. FRONTEND", "ui.html")

# --- 최상위 디렉터리 ---
DB_DIR = os.path.join(ROOT, "02. DB")                    # app.DB_DIR 의미
MAIL_DB_DIR = os.path.join(DB_DIR, "MAIL_db")            # fetch_mail.DB_DIR 의미
STATE_DIR = os.path.join(DB_DIR, "state")
FRONTEND_DIR = os.path.join(ROOT, "01. FRONTEND")

# --- 메일 데이터 파일 ---
MAIL_JSON_FILE = os.path.join(MAIL_DB_DIR, "mailbox.json")
ARCHIVE_FILE = os.path.join(MAIL_DB_DIR, "mailbox_archive.json")

# --- 캐시 / 로그 ---
CACHE_FILE = os.path.join(DB_DIR, "token_cache.bin")
LOG_FILE = os.path.join(DB_DIR, "logs", "fetch_log.txt")

# --- 설정 ---
USER_CONFIG_FILE = os.path.join(STATE_DIR, "user_config.json")

# --- 위젯 상태 파일 (state/) ---
POS_FILE = os.path.join(STATE_DIR, "widget_pos.json")
EXCLUDE_FILE = os.path.join(STATE_DIR, "widget_excluded.json")
SNOOZE_FILE = os.path.join(STATE_DIR, "widget_snooze.json")
DONE_FILE = os.path.join(STATE_DIR, "widget_done.json")
DONE_LOG_FILE = os.path.join(STATE_DIR, "widget_done_log.json")
MYTODOS_FILE = os.path.join(STATE_DIR, "widget_mytodos.json")
MEMOS_FILE = os.path.join(STATE_DIR, "widget_memos.json")
TAGS_FILE = os.path.join(STATE_DIR, "widget_tags.json")
VIP_FILE = os.path.join(STATE_DIR, "widget_vip.json")
IMPORTANT_FILE = os.path.join(STATE_DIR, "widget_important.json")
NOTES_FILE = os.path.join(STATE_DIR, "widget_notes.json")
HIDE_TS_FILE = os.path.join(STATE_DIR, "widget_hide_ts.json")
PROJECTS_FILE = os.path.join(STATE_DIR, "widget_projects.json")
PROJECT_CARDS_FILE = os.path.join(STATE_DIR, "widget_project_cards.json")
AD_TRASH_FILE = os.path.join(STATE_DIR, "widget_ad_trash.json")
REPORT_STATE_FILE = os.path.join(STATE_DIR, "widget_report_state.json")
# build_dashboard.AUTO_GROUPS_FILE 와 fetch_mail.MY_GROUPS_FILE 가 가리키는 동일 파일.
MY_GROUPS_FILE = os.path.join(STATE_DIR, "widget_my_groups.json")

# --- 생성 결과물 (01. FRONTEND/) ---
DASHBOARD_OUT_FILE = os.path.join(FRONTEND_DIR, "dashboard.html")
WEEKLY_OUT_FILE = os.path.join(FRONTEND_DIR, "weekly_report.html")
WEEKLY_REVIEW_OUT_FILE = os.path.join(FRONTEND_DIR, "weekly_review.html")
