@echo off
cd /d "%~dp0"

set "BACKEND=%~dp0..\00. BACKEND"

REM Python 탐색: py 런처 -> 흔한 설치 경로 -> PATH(WindowsApps 스텁 제외)
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
if not defined PY (
  echo [ERROR] Python not found. Run 설치\setup.bat first.
  pause
  exit /b 1
)
for %%D in ("%PY%") do set "PYDIR=%%~dpD"
if exist "%PYDIR%pythonw.exe" (set "PYW=%PYDIR%pythonw.exe") else (set "PYW=%PY%")

"%PY%" -c "import webview" 2>nul
if errorlevel 1 (
  echo [SETUP] Installing required packages...
  "%PY%" -m pip install -r "%~dp0..\requirements.txt" --quiet
  if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
  )
  echo [DONE]  Packages installed.
)

if not exist "%BACKEND%\token_cache.bin" (
  echo [LOGIN] Microsoft login required. Follow the on-screen instructions.
  echo.
  "%PY%" "%BACKEND%\fetch_mail.py"
  if errorlevel 1 (
    echo [ERROR] Login failed. Please try again.
    pause
    exit /b 1
  )
)

echo [START] Launching widget...
start "" "%PYW%" "%BACKEND%\app.py"
