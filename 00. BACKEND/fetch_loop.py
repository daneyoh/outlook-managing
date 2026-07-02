# ============================================================
#  백그라운드 반복 수집기
#  - 실행되면 즉시 1회 수집, 이후 30분마다 반복.
#  - 시작프로그램에 등록해 두면 로그인 시 자동으로 떠서 계속 돕니다.
#  - 창 없이 돌리려면 pythonw fetch_loop.py 로 실행하세요.
# ============================================================

import json
import os
import time
import traceback
from datetime import timedelta, date

import fetch_mail
import build_dashboard
import paths

INTERVAL_SEC = 30 * 60  # 30분

# Phase 1.5.1: 경로 상수는 paths.py 단일 소스에서 가져온다 (기존 이름 유지).
HERE = paths.HERE
ROOT = paths.ROOT
STATE_DIR = paths.STATE_DIR
REPORT_STATE_FILE = paths.REPORT_STATE_FILE


def _this_week_monday():
    """이번 주 월요일 자정(date 객체)."""
    today = date.today()
    return today - timedelta(days=today.weekday())


def _should_run_weekly_report():
    """last_generated < 이번 주 월요일이면 True (기기 꺼져있어도 다음 실행 시 발화)."""
    try:
        if not os.path.exists(REPORT_STATE_FILE):
            return True
        with open(REPORT_STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
        last = state.get("last_generated", "")
        if not last:
            return True
        return last < _this_week_monday().isoformat()
    except Exception:
        fetch_mail.log("주간 리포트 상태 확인 실패:\n" + traceback.format_exc())
        return False


def _record_weekly_report():
    """리포트 생성 완료 기록."""
    try:
        import state_io
        state_io.write_json(REPORT_STATE_FILE, {"last_generated": date.today().isoformat()})
    except Exception:
        fetch_mail.log("주간 리포트 기록 실패:\n" + traceback.format_exc())


def run_once():
    try:
        result = fetch_mail.main(auto=True)
        if result is None:
            result = {"ok": True, "auth_required": False}
    except Exception:
        fetch_mail.log("수집 중 오류:\n" + traceback.format_exc())
        return

    if result.get("auth_required"):
        fetch_mail.log("토큰 없음/만료. 'python fetch_mail.py'로 다시 로그인하세요.")
        return
    if not result.get("ok"):
        fetch_mail.log("수집 실패: " + result.get("msg", "알 수 없는 오류"))
        return

    # 수집 성공 후 대시보드 갱신
    try:
        build_dashboard.main()
    except Exception:
        fetch_mail.log("대시보드 생성 오류:\n" + traceback.format_exc())

    try:
        build_dashboard.run_archive()
    except Exception:
        fetch_mail.log("아카이브 오류:\n" + traceback.format_exc())

    # 주간 리포트 자동화
    if _should_run_weekly_report():
        try:
            __import__("subprocess").run(["python", os.path.join(HERE, "weekly_review.py")], cwd=HERE)
            _record_weekly_report()
            fetch_mail.log("주간 리포트 자동 생성 완료.")
        except Exception:
            fetch_mail.log("주간 리포트 오류:\n" + traceback.format_exc())


if __name__ == "__main__":
    fetch_mail.log("백그라운드 수집기 시작.")
    while True:
        run_once()
        time.sleep(INTERVAL_SEC)
