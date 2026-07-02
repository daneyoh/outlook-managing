# ============================================================
#  분류 규칙 단일 소스 (Phase 2.2)
#  긴급 / 액션(처리필요) / 사내(내부) / 미회신(replied) 판정 로직을
#  한 곳에 모은다. app.py 와 build_dashboard.py 에 흩어져 중복되던 규칙을
#  이 모듈로 수렴시켜 드리프트(drift)를 막는다.
#
#  설계 원칙 — import 순환 회피:
#    이 모듈은 build_dashboard / app 를 import 하지 않는다. 사내 도메인처럼
#    LIVE 설정이 필요한 값은 호출자가 인자(parameter)로 넘긴다. norm_subject 처럼
#    build_dashboard 에만 있는 순수 함수가 필요한 replied_thread_keys 는 그 함수를
#    인자로 주입(inject)받아 순환 import 없이 동작한다.
#
#  동작 보존(behavior-preserving): 각 함수는 추출 이전 호출부의 표현식과
#  1:1 동일한 결과를 반환한다.
# ============================================================


# 긴급/마감 강조 키워드 — 홈 화면 '긴급' pill 을 구동한다 (app._is_urgent 이관).
# ACTION_KEYWORDS 와는 목적이 다른 별개 리스트이므로 병합하지 않는다.
URGENT_KEYWORDS = ["마감", "긴급", "urgent", "asap"]

# 처리 필요(액션) 신호 키워드 — build_dashboard.has_action 이관.
# URGENT_KEYWORDS 를 포함하는 상위집합이지만 용도(TODO 후보 판정)가 달라 별개 유지.
ACTION_KEYWORDS = [
    "요청", "부탁", "검토", "확인", "회신", "답장", "회답", "마감", "기한",
    "까지", "제출", "전달", "공유", "승인", "결재", "피드백", "수정", "보완",
    "필요", "협조", "문의", "답변", "리뷰", "asap", "please", "review",
    "request", "deadline", "urgent", "확인부탁", "회신바랍니다",
]


def is_urgent(title, summary):
    """제목+요약에 긴급 키워드가 하나라도 있으면 True.
    (app._is_urgent 와 동일: lower() 후 URGENT_KEYWORDS 부분일치)"""
    text = (str(title) + " " + str(summary)).lower()
    return any(k in text for k in URGENT_KEYWORDS)


def has_action(title, summary):
    """제목+요약에 액션 키워드가 하나라도 있으면 True.
    (build_dashboard.has_action(row) 와 동일: 두 필드를 공백으로 이어 lower() 후
    ACTION_KEYWORDS 를 각각 lower() 하여 부분일치)"""
    text = (str(title) + " " + str(summary)).lower()
    return any(k.lower() in text for k in ACTION_KEYWORDS)


def is_from_internal(from_field, internal_domain):
    """발신자 문자열(from_field)에 사내 도메인이 포함되면 True.
    호출부의 `bool(internal_domain) and internal_domain in from_field.lower()`
    표현식과 1:1 동일. 사내 도메인은 LIVE 설정이므로 호출자가 넘긴다(import 순환 회피).

    - internal_domain 이 빈 문자열/None → False (도메인 미설정 시 아무것도 사내로 안 봄).
    - from_field 는 소문자화하여 비교(부분일치). internal_domain 은 호출부가 이미
      소문자로 넘긴다(get_internal_domain() 이 lower() 반환) — 방어적으로 여기서
      추가 lower() 는 하지 않는다(호출부 표현식과 정확히 동일하게 유지)."""
    if not internal_domain:
        return False
    return internal_domain in (from_field or "").lower()


def is_external_request(is_internal, to_me, name_match):
    """'외부요청'(참조요청) 판정 — build_dashboard.build_data() 의
    `"참조요청": (not to_me) and name_match` 과 1:1 동일.
    내가 To 수신자가 아닌데(not to_me) 본문/제목이 내 이름을 콕 집은(name_match) 경우.

    is_internal 인자는 호출부 시그니처 일관성을 위해 받되, 현재 참조요청 판정식에는
    쓰이지 않는다(app.py get_view 의 counts['외부요청'] 은 별도로 `(not 내부여부)
    and 참조요청` 을 계산 — 그 조합은 호출부에 그대로 남긴다)."""
    return (not to_me) and name_match


def replied_thread_keys(rows, norm_subject):
    """스레드(정규화 제목)별로 '가장 최근 메일이 내가 보낸 메일(보낸메일)'인 스레드 키 집합.
    = 내가 마지막에 보냈으니 회신 완료로 보는 스레드(미회신 목록에서 제외 대상).

    build_dashboard.build_data() (412-420) 의 인라인 알고리즘과 1:1 동일:
      - 키 = norm_subject(제목) or 제목  (정규화 결과가 빈 문자열이면 원본 제목)
      - 날짜 = row['날짜'] or ""  (문자열 사전식 비교로 최신 판정)
      - 각 키의 '가장 최근' 메일의 구분이 '보낸메일' 이면 replied.

    norm_subject 는 build_dashboard 의 순수 함수를 주입받는다(import 순환 회피)."""
    latest_date, latest_dir = {}, {}
    for r in rows:
        k = norm_subject(r.get("제목", "")) or r.get("제목", "")
        dt = r.get("날짜", "") or ""
        if k not in latest_date or dt > latest_date[k]:
            latest_date[k] = dt
            latest_dir[k] = r.get("구분", "")
    return {k for k, dirn in latest_dir.items() if dirn == "보낸메일"}
