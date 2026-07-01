# Outlook 메일 위젯

회사 Outlook(Microsoft 365) 메일을 항상 화면에 띄워두는 **always-on-top 위젯**입니다.  
TO DO / 미회신 / 프로젝트별 분류, 주간 리포트·회고 자동 생성을 지원합니다.  
별도 서버·클라이언트 시크릿 없이 **디바이스 코드 로그인** 방식만 사용합니다.

---

## 준비물

| 항목 | 내용 |
|------|------|
| Azure 앱 등록 | CLIENT_ID · TENANT_ID (아래 참고) — **필수** |
| Microsoft 계정 | 회사 Outlook 365 계정 |
| Python | 방법 A(설치파일)는 **불필요**. 방법 B(소스)는 3.9 이상 — 없으면 `setup.bat` 이 자동 설치 |
| WebView2 런타임 | 방법 A·B 모두 없으면 자동 다운로드·설치 |

### Azure 앱 등록 방법 (한 번만)

1. [Azure Portal](https://portal.azure.com) → **앱 등록** → **새 등록**
2. 이름 입력 → 지원 계정 유형: **조직 디렉터리의 계정** → 등록
3. 개요 화면에서 **애플리케이션(클라이언트) ID** 와 **디렉터리(테넌트) ID** 복사
4. **API 사용 권한** → 추가 → Microsoft Graph → 위임된 권한 → `Mail.Read`, `User.Read` 추가
5. **인증** → **모바일 및 데스크톱 애플리케이션** → `https://login.microsoftonline.com/common/oauth2/nativeclient` 체크

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

## 메모

- 권한은 **Mail.Read(읽기)** 만 사용합니다. 메일을 보내거나 수정하지 않습니다.
- 수집 개수는 `config.py` 의 `MAX_EMAILS` 로 조절합니다 (기본 50건).
- 로그인 시 "관리자 승인 필요" 메시지가 뜨면 회사 IT 담당자에게 앱 등록 승인을 요청하세요.
- 메일 데이터(`02. DB/`)는 git에 포함되지 않으며 로컬에만 저장됩니다.
