# ============================================================
#  Outlook(Microsoft Graph) 연동 설정
#  이 파일을 복사해 config.py 로 저장한 뒤 값을 채워 넣으세요.
#  Azure Portal > 앱 등록(App registrations) 에서 복사해 넣으세요.
# ============================================================

# 앱 등록 > 개요(Overview) 화면의 "애플리케이션(클라이언트) ID"
CLIENT_ID = "YOUR_CLIENT_ID"

# 앱 등록 > 개요 화면의 "디렉터리(테넌트) ID"
TENANT_ID = "YOUR_TENANT_ID"

# 본인 이메일 주소
MY_EMAIL = "your@email.com"

# 본인 이름 — 메일 본문에 이 이름이 나오면 "나에게 온 요청"으로 간주
MY_NAME = "홍길동"

# 사내(내부) 도메인 — 내부/외부 메일 구분에 사용.
# 비워두면 MY_EMAIL 의 도메인 부분에서 자동으로 도출한다.
INTERNAL_DOMAIN = ""

# 가져올 메일 개수 (받은편지함/보낸편지함 각각)
MAX_EMAILS = 50

# 위임된(delegated) 권한 — Azure에서 추가한 것과 동일하게
SCOPES = ["Mail.Read", "User.Read"]

# 동시성 제어
LOCK_TIMEOUT = 5

# 스누즈 기본 기간(일)
SNOOZE_DEFAULT_DAYS = 3

# 본문 전체 수집 옵션 (False = 기존 bodyPreview만)
FETCH_FULL_BODY = False
BODY_MAX_CHARS = 10000

# 메일 보존 기간
MAX_AGE_DAYS = 90
ARCHIVE_MAX_AGE_DAYS = 365
