# ============================================================
#  주간 업무 회고 생성기 (standalone)
#  - "내가 지난 일주일 무슨 일 했는지" 를 내가 보낸 메일 기준으로 정리.
#  - mailbox.json 을 읽어 weekly_review.html 을 생성한다 (최근 7일).
#  - JARVIS/dark 스타일 (ui.html 과 동일 색감) — 자체 포함 인라인 CSS, CDN 없음.
#  - 직접 실행하면 메일 재수집(있으면) → HTML 생성 → 열기 → 토스트.
#  - 매주 수요일 16:00 작업 스케줄러용 (등록은 부모가 처리).
# ============================================================

import html
import os
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta

import build_dashboard
# Phase 1.5.2: MY_EMAIL 은 import 시점에 값을 캡처하는 value-binding import 였으나,
# MY_EMAIL 이 LIVE accessor(build_dashboard.get_my_email)로 바뀌면서 이 모듈이
# stale(또는 함수 객체) 바인딩을 붙잡지 않도록 import 목록에서 제거한다. 필요 시
# build_dashboard.get_my_email() 로 LIVE 값을 얻는다 (현재 이 모듈 본문 미사용).
from build_dashboard import (
    load, norm_subject, fmt_date, project_of, load_project_rules,
    _parse_dt,
)

import paths
# Phase 1.5.1: 경로 상수는 paths.py 단일 소스에서 가져온다 (기존 이름 유지).
HERE = paths.HERE
ROOT = paths.ROOT                                  # 프로젝트 루트 (backend의 부모)
REVIEW_OUT_FILE = paths.WEEKLY_REVIEW_OUT_FILE

# JARVIS/dark — ui.html 의 색 언어 재사용 (deep black / cyan accent / off-white)
REVIEW_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>주간 업무 회고</title>
<style>
  :root{{--bg:#0a0e14;--bg-2:#080b10;--card:#10161e;--card-hi:#172430;
        --line:rgba(46,230,214,.16);--line-soft:rgba(46,230,214,.09);
        --ink:#eaf6f8;--sub:#9fb4bd;--faint:#62757e;
        --accent:#2ee6d6;--accent-strong:#35d0ff;--accent-hi:#5cf2ff;
        --accent-soft:rgba(46,230,214,.14);--amber:#ffb44a;--red:#ff5a52;
        --good:#3fe0a0;
        --mono:"Consolas","Courier New",ui-monospace,"D2Coding",monospace;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);
       font-family:"Malgun Gothic","맑은 고딕",system-ui,sans-serif;font-size:14px;
       -webkit-font-smoothing:antialiased;
       background-image:
         radial-gradient(120% 90% at 50% -10%, rgba(46,230,214,.06), transparent 60%),
         linear-gradient(rgba(46,230,214,.035) 1px, transparent 1px),
         linear-gradient(90deg, rgba(46,230,214,.035) 1px, transparent 1px);
       background-size:100% 100%, 34px 34px, 34px 34px;background-attachment:fixed;}}
  .wrap{{max-width:820px;margin:0 auto;padding:26px 22px 40px}}
  h1{{margin:0 0 4px;font-size:21px;letter-spacing:-.3px;
     color:var(--accent-hi);text-shadow:0 0 12px rgba(46,230,214,.45)}}
  .range{{color:var(--sub);font-size:12px;margin-bottom:20px}}
  .range .gen{{color:var(--faint)}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
         gap:12px;margin-bottom:26px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;
        padding:15px 16px;box-shadow:0 0 0 1px rgba(46,230,214,.03) inset}}
  .card .n{{font-family:var(--mono);font-size:27px;font-weight:700;color:var(--accent);
           line-height:1;text-shadow:0 0 9px rgba(46,230,214,.4)}}
  .card .l{{color:var(--sub);font-size:12px;margin-top:7px}}
  h2{{font-size:15px;margin:26px 0 10px;color:var(--ink);
     border-left:3px solid var(--accent);padding-left:9px;letter-spacing:-.2px}}
  .proj{{background:var(--card);border:1px solid var(--line);border-radius:12px;
        margin-bottom:14px;overflow:hidden}}
  .proj-h{{display:flex;align-items:center;justify-content:space-between;
          padding:11px 15px;background:var(--card-hi);border-bottom:1px solid var(--line-soft)}}
  .proj-h .nm{{font-weight:700;color:var(--accent-hi);font-size:13px}}
  .proj-h .nm .tag{{color:var(--amber);font-weight:400;font-size:11px;margin-left:6px}}
  .proj-h .cnt{{font-family:var(--mono);color:var(--accent);font-size:13px}}
  .outline{{padding:6px 0}}
  .ol2{{display:flex;align-items:baseline;gap:8px;padding:6px 15px 6px 24px;
       border-bottom:1px solid var(--line-soft);font-size:13px}}
  .ol2:last-child{{border-bottom:none}}
  .ol2 .mk{{color:var(--accent);font-family:var(--mono);flex:0 0 auto}}
  .ol2 .subj{{color:var(--ink);flex:1}}
  .ol2 .to{{color:var(--accent-strong);font-size:12px;flex:0 0 auto}}
  .ol2 .dt{{font-family:var(--mono);color:var(--sub);font-size:12px;flex:0 0 auto;white-space:nowrap}}
  .ol2 .tag{{font-size:11px;flex:0 0 auto;padding:1px 7px;border-radius:8px}}
  .ol2 .tag.done{{color:var(--good);background:rgba(63,224,160,.12)}}
  .ol2 .tag.ing{{color:var(--amber);background:rgba(255,180,74,.12)}}
  .ol3{{display:flex;align-items:baseline;gap:8px;padding:2px 15px 8px 48px;font-size:12px}}
  .ol3 .mk{{color:var(--faint);font-family:var(--mono);flex:0 0 auto}}
  .ol3 .obs{{color:var(--sub)}}
  .who-row{{display:flex;align-items:center;gap:10px;padding:7px 15px;
           border-bottom:1px solid var(--line-soft)}}
  .who-row:last-child{{border-bottom:none}}
  .who-name{{flex:0 0 240px;color:var(--accent-strong);font-size:13px;
            overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .who-bar{{flex:1;height:9px;background:var(--bg-2);border-radius:5px;overflow:hidden}}
  .who-fill{{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent-strong));
            box-shadow:0 0 8px rgba(46,230,214,.5)}}
  .who-n{{flex:0 0 34px;text-align:right;font-family:var(--mono);color:var(--accent);font-size:13px}}
  .barbox{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
  .bar-row{{display:flex;align-items:center;gap:10px;padding:4px 0}}
  .bar-day{{flex:0 0 78px;font-family:var(--mono);color:var(--sub);font-size:12px}}
  .bar-track{{flex:1;height:14px;background:var(--bg-2);border-radius:4px;overflow:hidden}}
  .bar-fill{{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent-strong))}}
  .bar-n{{flex:0 0 30px;text-align:right;font-family:var(--mono);color:var(--accent);font-size:12px}}
  .empty{{color:var(--sub);background:var(--card);border:1px solid var(--line);
         border-radius:12px;padding:30px;text-align:center}}
</style></head>
<body><div class="wrap">
<h1>주간 업무 회고</h1>
<div class="range">{기간} <span class="gen">· 지난 7일 · 생성 {생성시각}</span></div>
{본문}
</div></body></html>
"""


def _esc(s):
    return html.escape(str(s or ""))


def build_weekly_review():
    """최근 7일(now-7d ~ now) 동안 내가 보낸 메일 중심의 업무 회고 HTML 을 생성하고 경로 반환.
    - 보낸 메일 / 회신한 대화 / 받은 메일 / 처리한 프로젝트 수 (요약 카드)
    - 내가 보낸 메일 (프로젝트별 그룹, 그룹 내 최신순)
    - 활발했던 상대 (내가 보낸 수 기준 Top)
    - 일자별 보낸 건수 미니 바
    데이터 없으면 최소 "데이터 없음" 리포트도 작성한다.
    """
    rows = load()
    now = datetime.now()                 # 런타임 스크립트라 now() 사용 OK
    week_ago = now - timedelta(days=7)
    rules = load_project_rules()

    range_txt = f"{week_ago.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
    gen_txt = now.strftime("%Y-%m-%d %H:%M")

    # 데이터 없음 가드 — 최소 리포트라도 작성
    if not rows:
        body = '<div class="empty">표시할 메일 데이터가 없습니다.</div>'
        out = REVIEW_TEMPLATE.format(기간=range_txt, 생성시각=gen_txt, 본문=body)
        with open(REVIEW_OUT_FILE, "w", encoding="utf-8") as f:
            f.write(out)
        return REVIEW_OUT_FILE

    # 최근 7일 범위 분리
    sent_recent = []          # 내가 보낸 (범위 내)
    recv_n = 0                # 받은 메일 수 (범위 내)
    for r in rows:
        dt = _parse_dt(r.get("날짜", ""))
        if dt is None or dt < week_ago or dt > now:
            continue
        if r.get("구분") == "보낸메일":
            sent_recent.append(r)
        elif r.get("구분") == "받은메일":
            recv_n += 1

    # 회신한 대화 수: 범위 내 보낸 메일 중, 같은 스레드에 그 이전 받은메일이 있던 것
    recv_dts_by_key = defaultdict(list)
    for r in rows:
        if r.get("구분") == "받은메일":
            dt = _parse_dt(r.get("날짜", ""))
            if dt is not None:
                recv_dts_by_key[norm_subject(r.get("제목", ""))].append(dt)
    replied_keys = set()
    for s in sent_recent:
        sdt = _parse_dt(s.get("날짜", ""))
        if sdt is None:
            continue
        key = norm_subject(s.get("제목", ""))
        if any(rd < sdt for rd in recv_dts_by_key.get(key, [])):
            replied_keys.add(key)

    # 프로젝트별 그룹화 (그룹 내 최신순)
    proj_groups = defaultdict(list)
    for s in sent_recent:
        proj_groups[project_of(s, rules)].append(s)
    for msgs in proj_groups.values():
        msgs.sort(key=lambda m: m.get("날짜", ""), reverse=True)
    # 그룹은 건수 desc 로 정렬
    groups_sorted = sorted(proj_groups.items(), key=lambda kv: len(kv[1]), reverse=True)

    # 활발했던 상대: 보낸 메일의 받는사람(상대) 카운트
    who_count = defaultdict(int)
    for s in sent_recent:
        to = (s.get("받는사람", "") or "").strip()
        if to:
            who_count[to] += 1
    who_top = sorted(who_count.items(), key=lambda kv: kv[1], reverse=True)[:8]
    who_max = who_top[0][1] if who_top else 1

    # 일자별 보낸 건수 (오래된→최신, 7일)
    day_keys = [(now - timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(6, -1, -1)]
    sent_by_day = defaultdict(int)
    for s in sent_recent:
        sent_by_day[(s.get("날짜", "") or "")[:10]] += 1
    day_max = max((sent_by_day.get(d, 0) for d in day_keys), default=0) or 1

    # ---- 요약 카드 ----
    cards = (
        '<div class="cards">'
        f'<div class="card"><div class="n">{len(sent_recent)}</div>'
        '<div class="l">보낸 메일</div></div>'
        f'<div class="card"><div class="n">{len(replied_keys)}</div>'
        '<div class="l">회신한 대화</div></div>'
        f'<div class="card"><div class="n">{recv_n}</div>'
        '<div class="l">받은 메일</div></div>'
        f'<div class="card"><div class="n">{len(proj_groups)}</div>'
        '<div class="l">처리한 프로젝트</div></div>'
        '</div>'
    )

    # ---- 내가 보낸 메일 (프로젝트별 · 회고 아웃라인) ----
    # 프로젝트(#) > 건/스레드(-) > 왕복 관찰(>) 3단 아웃라인으로 표시.
    sent_html = '<h2>내가 보낸 메일 · 프로젝트별</h2>'
    if groups_sorted:
        for proj, msgs in groups_sorted:
            # 같은 스레드(정규화 제목)로 묶어 왕복 횟수를 관찰(>)로 뽑아낸다.
            thread_order, thread_map = [], defaultdict(list)
            for m in msgs:                       # msgs: 최신순
                key = norm_subject(m.get("제목", ""))
                if key not in thread_map:
                    thread_order.append(key)
                thread_map[key].append(m)
            proj_ing = any(len(v) > 1 for v in thread_map.values())

            sent_html += (
                '<div class="proj"><div class="proj-h">'
                f'<span class="nm">{_esc(proj)}'
                f'<span class="tag">({"진행중" if proj_ing else "완료"})</span></span>'
                f'<span class="cnt">{len(msgs)}건</span></div>'
                '<div class="outline">'
            )
            for key in thread_order:
                items = thread_map[key]          # 스레드 내 최신순
                latest = items[0]
                ing = len(items) > 1
                sent_html += (
                    '<div class="ol2"><span class="mk">-</span>'
                    f'<span class="subj">{_esc(latest.get("제목", ""))}</span>'
                    f'<span class="to">{_esc(latest.get("받는사람", ""))}</span>'
                    f'<span class="dt">{_esc(fmt_date(latest.get("날짜", "")))}</span>'
                    f'<span class="tag {"ing" if ing else "done"}">{"진행중" if ing else "완료"}</span>'
                    '</div>'
                )
                if ing:
                    oldest = items[-1]
                    sent_html += (
                        '<div class="ol3"><span class="mk">&gt;</span>'
                        f'<span class="obs">{len(items)}회 메일 왕복 · '
                        f'최초 {_esc(fmt_date(oldest.get("날짜", "")))} → '
                        f'최근 {_esc(fmt_date(latest.get("날짜", "")))}</span></div>'
                    )
            sent_html += '</div></div>'
    else:
        sent_html += '<div class="empty">지난 7일 동안 보낸 메일이 없습니다.</div>'

    # ---- 활발했던 상대 ----
    who_html = '<h2>활발했던 상대 · 내가 보낸 수</h2>'
    if who_top:
        who_html += '<div class="barbox">'
        for email, n in who_top:
            pct = int(n / who_max * 100)
            who_html += (
                '<div class="who-row">'
                f'<div class="who-name">{_esc(email)}</div>'
                f'<div class="who-bar"><div class="who-fill" style="width:{pct}%"></div></div>'
                f'<div class="who-n">{n}</div>'
                '</div>'
            )
        who_html += '</div>'
    else:
        who_html += '<div class="empty">상대 데이터가 없습니다.</div>'

    # ---- 일자별 보낸 건수 미니 바 ----
    day_html = '<h2>일자별 보낸 건수</h2><div class="barbox">'
    for d in day_keys:
        n = sent_by_day.get(d, 0)
        pct = int(n / day_max * 100)
        day_html += (
            '<div class="bar-row">'
            f'<div class="bar-day">{d[5:]}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>'
            f'<div class="bar-n">{n}</div>'
            '</div>'
        )
    day_html += '</div>'

    body = cards + sent_html + who_html + day_html
    out = REVIEW_TEMPLATE.format(기간=range_txt, 생성시각=gen_txt, 본문=body)
    with open(REVIEW_OUT_FILE, "w", encoding="utf-8") as f:
        f.write(out)
    return REVIEW_OUT_FILE


def _open_file(path):
    """Windows 기본 핸들러로 열고, 실패 시 webbrowser 폴백."""
    try:
        os.startfile(path)  # noqa: S606 (Windows 전용)
    except (AttributeError, OSError):
        try:
            webbrowser.open("file://" + path.replace("\\", "/"))
        except Exception:
            pass


if __name__ == "__main__":
    # 1) 메일 재수집 (캐시 토큰만 사용). 토큰 없거나 오류면 기존 데이터로 진행.
    try:
        import fetch_mail
        fetch_mail.main(auto=True)
    except Exception:
        pass            # 네트워크 등 오류 — 기존 데이터로 진행

    # 2) 회고 HTML 생성
    path = build_weekly_review()
    print(f"주간 회고 생성 완료: {os.path.basename(path)}")

    # 3) 열기
    _open_file(path)

    # 4) 토스트 알림 (win11toast 없으면 조용히 무시)
    try:
        from win11toast import toast as _toast
        _toast("주간 회고 준비됨", "지난 7일 업무 회고가 생성되었습니다.")
    except Exception:
        pass
