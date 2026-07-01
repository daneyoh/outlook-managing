@echo off
chcp 65001 > nul
cd /d "%~dp0.."

echo ============================================
echo  Outlook 메일 위젯 — 배포용 설치파일(exe) 빌드
echo ============================================
echo.

REM ── Inno Setup 확인 ──
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo [오류] Inno Setup 이 설치되어 있지 않습니다.
  echo        https://jrsoftware.org/isdl.php 에서 설치 후 다시 실행하세요.
  pause & exit /b 1
)

REM ── WebView2 부트스트래퍼 확인(없으면 다운로드) ──
if not exist "설치\MicrosoftEdgeWebview2Setup.exe" (
  echo [1/4] WebView2 부트스트래퍼 다운로드 중...
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile '설치\MicrosoftEdgeWebview2Setup.exe' -UseBasicParsing } catch { exit 1 }"
  if errorlevel 1 (
    echo [오류] 다운로드 실패. 인터넷 연결을 확인하세요.
    pause & exit /b 1
  )
) else (
  echo [1/4] WebView2 부트스트래퍼 확인 완료
)

REM ── 개인 config.py 를 배포용 placeholder 로 잠시 교체 ──
REM     (실수로 개인 Azure 시크릿이 배포 exe 에 박히는 것을 방지)
set "HAD_CONFIG=0"
if exist "00. BACKEND\config.py" (
  set "HAD_CONFIG=1"
  copy /y "00. BACKEND\config.py" "00. BACKEND\config.py.devbackup" >nul
)
copy /y "00. BACKEND\config.example.py" "00. BACKEND\config.py" >nul
echo [2/4] 배포용 placeholder config 적용 완료

REM ── PyInstaller 빌드 ──
echo [3/4] PyInstaller 빌드 중...
call "설치\build.bat" <nul
set "BUILD_ERR=%errorlevel%"

REM ── 개인 config.py 복원 (빌드 성패와 무관하게 항상 복원) ──
if "%HAD_CONFIG%"=="1" (
  copy /y "00. BACKEND\config.py.devbackup" "00. BACKEND\config.py" >nul
  del "00. BACKEND\config.py.devbackup" >nul 2>&1
) else (
  del "00. BACKEND\config.py" >nul 2>&1
)
echo       개인 config.py 복원 완료

if not "%BUILD_ERR%"=="0" (
  echo [오류] PyInstaller 빌드 실패.
  pause & exit /b 1
)

REM ── Inno Setup 컴파일 ──
echo [4/4] 설치파일(exe) 컴파일 중...
"%ISCC%" "설치\installer.iss"
if errorlevel 1 (
  echo [오류] 설치파일 컴파일 실패.
  pause & exit /b 1
)

echo.
echo ============================================
echo  완료: 설치\output\OutlookWidgetSetup.exe
echo  이 파일 하나만 배포하면 됩니다.
echo ============================================
pause
