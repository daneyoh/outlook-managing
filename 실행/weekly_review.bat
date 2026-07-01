@echo off
REM 주간 업무 회고 생성 — 콘솔 없이 실행 (pythonw).
REM 메일 재수집(토큰 있으면) → weekly_review.html 생성 → 열기 → 토스트.
REM 매주 수요일 16:00 작업 스케줄러에서 이 배치를 실행한다.
REM bare "pythonw" 가 WindowsApps 스텁으로 잡혀 조용히 실패하는 문제 방지 — 실제 설치 경로 탐색.
cd /d "%~dp0.."

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
if not defined PYW exit /b 1
for %%D in ("%PYW%") do set "PYDIR=%%~dpD"
if exist "%PYDIR%pythonw.exe" set "PYW=%PYDIR%pythonw.exe"
start "" "%PYW%" "00. BACKEND\weekly_review.py"
