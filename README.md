# Outlook 메일 위젯

회사 Outlook(Microsoft 365) 메일을 항상 화면에 띄워두는 **always-on-top 위젯**입니다.  
TO DO / 미회신 / 프로젝트별 분류, 주간 리포트·회고 자동 생성을 지원합니다.  
별도 서버·클라이언트 시크릿 없이 **디바이스 코드 로그인** 방식만 사용합니다.

---

## 준비물

| 항목 | 내용 |
|------|------|
| Azure 앱 등록 | CLIENT_ID · TENANT_ID (아래 [Azure 앱 등록 방법](#azure-앱-등록-방법-최초-1회-약-5분) 참고) — **필수, 사용자가 준비** |
| Microsoft 계정 | Outlook 365 계정 |
| Python | 방법 A(설치파일)는 **불필요**. 방법 B(소스)는 3.9 이상 — 없으면 `setup.bat` 이 자동 설치 |
| WebView2 런타임 | 화면 렌더링 엔진. 없으면 자동 설치 ([설명](#webview2-런타임이란-자동-설치되므로-대개-신경-안-써도-됨)) |

### Azure 앱 등록 방법 (최초 1회, 약 5분)

이 위젯이 내 Outlook 메일을 읽으려면, Microsoft 365에 "이 프로그램이 메일을
읽어도 된다"고 등록해야 합니다. 이 등록에서 나오는 **CLIENT_ID**(앱 고유번호)와
**TENANT_ID**(조직 고유번호)를 설치 중에 입력하게 됩니다.

> 💡 **client secret(비밀키)은 필요 없습니다.** 이 위젯은 "디바이스 코드 로그인"
> 방식이라 비밀키 없이 본인이 브라우저에서 직접 로그인합니다. 따라서 아래 과정에서
> 비밀키를 만들거나 복사할 필요가 없습니다.

**1단계 — 앱 등록 만들기**
1. [Azure Portal](https://portal.azure.com) 접속 → 회사 계정으로 로그인
2. 상단 검색창에 **앱 등록**(App registrations) 입력 → 클릭
3. **+ 새 등록**(New registration) 클릭
4. **이름**: 아무거나 (예: `Outlook 메일 위젯`)
5. **지원되는 계정 유형**: **"이 조직 디렉터리의 계정만"**(Single tenant) 선택
6. **리디렉션 URI**: 지금은 비워둠
7. **등록**(Register) 클릭

**2단계 — ID 두 개 복사 (설치 시 입력할 값)**
- 등록 직후 나오는 **개요**(Overview) 화면에서:
  - **애플리케이션(클라이언트) ID** → 이게 `CLIENT_ID`
  - **디렉터리(테넌트) ID** → 이게 `TENANT_ID`
- 두 값을 메모장에 복사해 둡니다. (설치 마법사에서 붙여넣기)

**3단계 — 메일 읽기 권한 추가**
1. 왼쪽 메뉴 **API 권한**(API permissions) 클릭
2. **+ 권한 추가**(Add a permission) → **Microsoft Graph** → **위임된 권한**(Delegated permissions)
3. 검색해서 다음 2개 체크: **`Mail.Read`**, **`User.Read`**
4. **권한 추가**(Add permissions) 클릭
5. (선택) 목록에 뜨면 **관리자 동의 허용**(Grant admin consent) 클릭 — 회사 정책상
   개인이 못 누르면, 회사 IT 담당자에게 이 앱 승인을 요청하세요.

**4단계 — 데스크톱 앱으로 로그인 허용**
1. 왼쪽 메뉴 **인증**(Authentication) 클릭
2. **+ 플랫폼 추가**(Add a platform) → **모바일 및 데스크톱 애플리케이션**
3. `https://login.microsoftonline.com/common/oauth2/nativeclient` 체크 → **구성**(Configure)
4. 아래쪽 **고급 설정** → **"공용 클라이언트 흐름 허용"**(Allow public client flows)을
   **예**(Yes)로 설정 → **저장**(Save)

이제 설치 중 `CLIENT_ID` / `TENANT_ID` 입력란에 2단계에서 복사한 값을 넣으면 됩니다.
`TENANT_ID`를 모르면 `organizations` 라고 입력해도 대부분 동작합니다.

---

## WebView2 런타임이란? (자동 설치되므로 대개 신경 안 써도 됨)

이 위젯의 화면은 웹페이지(HTML/CSS/JS)로 만들어져 있고, 그 화면을 데스크톱 창
안에 그려주는 마이크로소프트 부품이 **WebView2 런타임**입니다. 쉽게 말해
**"앱 안에 들어가는 Edge(크롬) 엔진"** 입니다. 이게 없으면 위젯 창이 비어 보입니다.

- **Windows 11 · 최신 Windows 10**: 대부분 **기본 내장**되어 있어 아무 일도 안 일어납니다.
- **없는 경우**: `설치/setup.bat` 과 설치파일(exe)이 **자동으로 다운로드·설치**합니다.
  (이미 있으면 몇 초 만에 "이미 설치됨"으로 건너뜁니다.)
- 수동 설치가 필요하면: [Microsoft WebView2 다운로드](https://developer.microsoft.com/microsoft-edge/webview2/)
  에서 **Evergreen Standalone Installer** 를 받아 실행하세요.

---

## 설치 — 방법 A: 설치파일(권장, 일반 사용자용)

**`OutlookWidgetSetup.exe` 하나만 받아서 실행**하면 됩니다. Python 설치도 필요 없습니다.

- 다운로드: [GitHub Releases](https://github.com/daneyoh/outlook-managing/releases) 의 최신 `OutlookWidgetSetup.exe`
- 실행하면: WebView2 자동 설치 → 설치 위치 선택 → **Azure ID·이메일·이름 입력** → 바탕화면 바로가기 생성 → 위젯 실행
- 제거: 설정 → 앱 → "Outlook 메일 위젯" 제거

입력한 Azure 설정은 설치 폴더의 `02. DB/state/user_config.json` 에 저장됩니다.
로그인은 위젯의 **설정** 화면 또는 최초 메일 새로고침 시 브라우저로 진행됩니다.

---

## 설치 — 방법 B: 소스에서 직접 (개발자용)

`설치/setup.bat` 을 더블클릭하면 자동으로 진행됩니다.

```
설치\setup.bat
```

진행 순서:
1. Python 확인 — 없으면 python.org 설치 파일을 자동 다운로드해서 설치
2. WebView2 런타임 확인 — 없으면 자동 다운로드해서 설치
3. 패키지 자동 설치
4. Azure ID·이메일·이름 입력 → `config.py` 자동 생성
5. Microsoft 계정 로그인 (브라우저)
6. 위젯 실행

> `config.py` 는 개인정보가 포함되므로 git에 포함되지 않습니다.  
> 재설정이 필요하면 `00. BACKEND/config.py` 를 직접 편집하거나 삭제 후 `설치/setup.bat` 재실행.

---

## 실행 파일 안내

배치 파일은 용도별로 `실행/` 과 `설치/` 폴더에 정리되어 있습니다.

### 실행/ — 평소 사용

| 파일 | 설명 |
|------|------|
| `실행/start_widget.bat` | 위젯 실행 (로그인 세션 있을 때) |
| `실행/restart_widget.bat` | 위젯 재시작 |
| `실행/start_now.bat` | 백그라운드 메일 수집 즉시 실행 |
| `실행/weekly_review.bat` | 주간 업무 회고 HTML 생성·열기 |

### 설치/ — 최초 설치·등록·빌드

| 파일 | 설명 |
|------|------|
| `설치/setup.bat` | **최초 설치** — 패키지·config·로그인·위젯 한 번에 처리 |
| `설치/install_widget_autostart.bat` | 로그온 시 위젯 자동 시작 등록 |
| `설치/install_autostart.bat` | 로그온 시 백그라운드 수집 자동 시작 등록 |
| `설치/uninstall_autostart.bat` | 자동 시작 제거 |
| `설치/build.bat` | 실행파일 빌드 (PyInstaller → `dist/OutlookWidget/`) |
| `설치/build_installer.bat` | **배포용 단일 설치파일 빌드** (PyInstaller + Inno Setup → `설치/output/OutlookWidgetSetup.exe`) |
| `설치/installer.iss` | Inno Setup 설치파일 스크립트 |

> 배포용 설치파일을 만들려면 [Inno Setup](https://jrsoftware.org/isdl.php) 을 설치한 뒤
> `설치\build_installer.bat` 을 실행하세요. 개인 `config.py` 는 빌드 중 자동으로
> placeholder 로 교체됐다가 복원되어, 배포 exe 에 개인정보가 포함되지 않습니다.

---

## 위젯 기능

- **홈** — TO DO / 미회신 / 외부요청 / 내부 메일 분류
- **프로젝트** — 프로젝트별 메일 그룹 + 마일스톤 관리
- **통계** — 주간 리포트·회고 생성 버튼, 미회신 지연 현황
- **전체** — 전체 메일 목록 + 숨긴 항목 관리
- **설정** — Azure ID·이름·메일·수집 개수 변경

### 카드 액션

| 버튼 | 동작 |
|------|------|
| ✓ 체크 | 완료 처리 (숨김) |
| 🔔 벨 | 스누즈 (3일 후 다시 표시) |
| ✎ 메모 | 메일별 메모 저장 |
| ⭐ 별 | 중요 표시 |

---

## 폴더 구조

```
00. BACKEND/         Python 소스
  app.py             위젯 메인 (pywebview)
  fetch_mail.py      메일 수집 (Microsoft Graph)
  fetch_loop.py      30분 주기 백그라운드 수집
  build_dashboard.py 대시보드·주간 리포트 생성
  weekly_review.py   주간 업무 회고 생성
  config.example.py  설정 템플릿 (config.py 로 복사해 사용)
  state_io.py        파일 락·JSON 저장 유틸

01. FRONTEND/        UI
  ui.html            위젯 화면 (HTML/CSS/JS)

02. DB/              런타임 데이터 (git 제외)
  MAIL_db/           메일 원본 JSON
  state/             위젯 상태 (완료·스누즈·메모 등)
  token_cache.bin    인증 토큰

*.bat                실행 런처
requirements.txt     Python 패키지 목록
build.spec           PyInstaller EXE 빌드 설정
```

---

## 문제 해결 (FAQ)

- **위젯 창이 하얗게 비어서 뜸** → WebView2 런타임이 없는 경우입니다.
  위 [WebView2 설명](#webview2-런타임이란-자동-설치되므로-대개-신경-안-써도-됨)의
  수동 설치 링크로 설치 후 다시 실행하세요.
- **로그인 시 "관리자 승인 필요"(admin consent required)** → 회사 정책상 개인이
  권한에 동의할 수 없는 경우입니다. 회사 IT 담당자에게 Azure 앱 등록의
  `Mail.Read` 권한 승인을 요청하세요.
- **"AADSTS700016: 애플리케이션을 찾을 수 없음"** → `CLIENT_ID` 또는 `TENANT_ID`
  가 잘못 입력됐습니다. Azure 개요 화면에서 다시 복사해 입력하세요.
- **로그인이 이동으로 폴백되거나 안 뜸** → Azure **인증** 설정에서
  "공용 클라이언트 흐름 허용"이 **예**인지 확인하세요(4단계).
- **설정 다시 바꾸기** → 위젯의 **설정** 화면에서 ID·이메일·이름·수집 개수를
  변경할 수 있습니다. (방법 B 소스 설치는 `00. BACKEND/config.py` 직접 편집도 가능)

## 메모

- 권한은 **Mail.Read(읽기)** 만 사용합니다. 메일을 보내거나 수정하지 않습니다.
- 수집 개수는 설정 화면(또는 `config.py` 의 `MAX_EMAILS`)으로 조절합니다 (기본 50건).
- 내부/외부 메일 구분은 내 이메일 도메인 기준입니다. 다르게 쓰려면 `config.py` 의
  `INTERNAL_DOMAIN` 을 지정하세요 (비우면 내 이메일 도메인 자동 사용).
- 메일 데이터·로그인 토큰(`02. DB/`)은 git·배포 exe 에 포함되지 않으며 로컬에만 저장됩니다.
