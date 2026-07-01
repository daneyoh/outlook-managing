@echo off
chcp 65001 > nul
cd /d "%~dp0.."

echo ============================================
echo  Outlook 메일 위젯 — 최초 설정
echo ============================================
echo.

REM ── 1. Python 탐색 (py 런처 → 흔한 설치 경로 → PATH 순으로 확인) ──
set "PY="
set "PYW="

for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%P"

if not defined PY (
  for %%V in (Python313 Python312 Python311 Python310 Python39) do (
    if not defined PY if exist "%LocalAppData%\Programs\Python\%%V\python.exe" set "PY=%LocalAppData%\Programs\Python\%%V\python.exe"
  )
)

if not defined PY (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | find /i "WindowsApps" >nul
    if errorlevel 1 if not defined PY set "PY=%%P"
  )
)

REM ── Python이 전혀 없으면 python.org 설치 파일을 자동 다운로드해서 설치 ──
if not defined PY (
  echo [1/6] Python이 없어 자동으로 설치합니다 ^(인터넷 필요, 1~2분 소요^)...
  set "PYINST=%TEMP%\python-installer.exe"
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.1/python-3.13.1-amd64.exe' -OutFile '%PYINST%' -UseBasicParsing } catch { exit 1 }"
  if errorlevel 1 (
    echo [오류] Python 설치 파일 다운로드 실패. 인터넷 연결을 확인하거나
    echo        https://www.python.org/downloads/ 에서 직접 설치 후 다시 실행하세요.
    pause & exit /b 1
  )
  echo        설치 중...
  "%PYINST%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0
  del "%PYINST%" >nul 2>&1

  set "PY="
  for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%P"
  if not defined PY (
    echo [오류] Python 설치 후에도 찾을 수 없습니다. PC를 재부팅한 뒤 다시
    echo        실행해보거나 https://www.python.org/downloads/ 에서 수동 설치하세요.
    pause & exit /b 1
  )
  echo        Python 설치 완료
) else (
  echo [1/6] Python 확인 완료 ^(%PY%^)
)

REM pythonw.exe는 python.exe와 같은 폴더의 것을 우선 사용 — 없는 설치본이면
REM (일부 축약 배포판) python.exe로 대체해서 콘솔창이 잠깐 보이더라도 동작은 하게 함
for %%D in ("%PY%") do set "PYDIR=%%~dpD"
if exist "%PYDIR%pythonw.exe" (
  set "PYW=%PYDIR%pythonw.exe"
) else (
  set "PYW=%PY%"
)

REM ── 2. WebView2 런타임 확인 (위젯 화면을 그리는 데 필수) ──
set "WV2_GUID={F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\%WV2_GUID%" /v pv >nul 2>&1
if errorlevel 1 reg query "HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\%WV2_GUID%" /v pv >nul 2>&1
if errorlevel 1 (
  echo [2/6] WebView2 런타임이 없어 자동으로 설치합니다...
  set "WV2SETUP=%TEMP%\MicrosoftEdgeWebview2Setup.exe"
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile '%WV2SETUP%' -UseBasicParsing } catch { exit 1 }"
  if errorlevel 1 (
    echo [경고] WebView2 런타임 다운로드 실패 — 위젯 화면이 안 뜨면
    echo        https://developer.microsoft.com/microsoft-edge/webview2/ 에서 수동 설치하세요.
  ) else (
    "%WV2SETUP%" /silent /install
    del "%WV2SETUP%" >nul 2>&1
    echo        WebView2 설치 완료
  )
) else (
  echo [2/6] WebView2 런타임 확인 완료
)

REM ── 3. 패키지 설치 ──────────────────────────
echo [3/6] 패키지 설치 중...
"%PY%" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
  echo [오류] 패키지 설치 실패. 네트워크 연결을 확인하세요.
  pause & exit /b 1
)
echo       완료

REM ── 4. config.py 생성 ───────────────────────
if exist "00. BACKEND\config.py" (
  echo [4/6] config.py 이미 존재 — 건너뜀
  goto :login
)

echo [4/6] 설정 입력 ^(Azure Portal 앱 등록 정보^)
echo.
echo   Azure Portal ^> 앱 등록 ^> 개요 화면에서 복사하세요.
echo   모르면 tenant_id 는 그냥 Enter 누르면 organizations 으로 설정됩니다.
echo.

set /p "CID=  애플리케이션(클라이언트) ID: "
set /p "TID=  디렉터리(테넌트)   ID [Enter=organizations]: "
if "%TID%"=="" set "TID=organizations"
set /p "EMAIL=  본인 이메일 주소: "
set /p "NAME=  본인 이름 (한글 가능): "

REM config.py 생성
(
echo # ============================================================
echo #  Outlook^(Microsoft Graph^) 연동 설정  ^<^<^< setup.bat 으로 생성됨
echo # ============================================================
echo CLIENT_ID = "%CID%"
echo TENANT_ID = "%TID%"
echo MY_EMAIL  = "%EMAIL%"
echo MY_NAME   = "%NAME%"
echo MAX_EMAILS = 50
echo SCOPES = ["Mail.Read", "User.Read"]
echo LOCK_TIMEOUT = 5
echo SNOOZE_DEFAULT_DAYS = 3
echo FETCH_FULL_BODY = False
echo BODY_MAX_CHARS = 10000
echo MAX_AGE_DAYS = 90
echo ARCHIVE_MAX_AGE_DAYS = 365
) > "00. BACKEND\config.py"
echo       config.py 생성 완료

REM ── 5. 로그인 ───────────────────────────────
:login
echo.
echo [5/6] Microsoft 계정 로그인
echo       브라우저가 열리면 회사 계정으로 로그인하세요.
echo.
"%PY%" "00. BACKEND\fetch_mail.py"
if errorlevel 1 (
  echo [오류] 로그인 실패. 위 메시지를 확인하세요.
  pause & exit /b 1
)

REM ── 6. 위젯 실행 ────────────────────────────
echo.
echo [6/6] 위젯 실행 중...
start "" "%PYW%" "00. BACKEND\app.py"

echo.
echo ============================================
echo  설정 완료! 위젯이 화면에 표시됩니다.
echo.
echo  다음 번부터는 실행\start_widget.bat 을 실행하세요.
echo  자동 시작 등록: 설치\install_widget_autostart.bat
echo ============================================
echo.
pause
