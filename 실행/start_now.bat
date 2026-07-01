@echo off
REM Start the background fetcher right now (no window, runs every 30 min).
cd /d "%~dp0.."
REM Python 탐색: py 런처 -> 흔한 설치 경로 -> PATH(WindowsApps 스텁 제외)
set "PYW="
for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYW=%%P"
if not defined PYW (
  for %%V in (Python313 Python312 Python311 Python310 Python39) do (
    if not defined PYW if exist "%LocalAppData%\Programs\Python\%%V\python.exe" set "PYW=%LocalAppData%\Programs\Python\%%V\python.exe"
  )
)
if not defined PYW (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | find /i "WindowsApps" >nul
    if errorlevel 1 if not defined PYW set "PYW=%%P"
  )
)
if not defined PYW (
  echo [ERROR] Python not found. Run 설치\setup.bat first.
  pause
  exit /b 1
)
for %%D in ("%PYW%") do set "PYDIR=%%~dpD"
if exist "%PYDIR%pythonw.exe" set "PYW=%PYDIR%pythonw.exe"
start "" "%PYW%" "00. BACKEND\fetch_loop.py"
echo [DONE] Background fetcher started. It runs every 30 minutes.
echo  - Check fetch_log.txt to see activity.
echo.
pause
