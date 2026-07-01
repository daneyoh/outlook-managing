@echo off
REM Install autostart for the desktop widget WITHOUT admin / Task Scheduler.

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP%\OutlookMailWidget.vbs"

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

> "%VBS%" echo Set sh = CreateObject("WScript.Shell")
>>"%VBS%" echo sh.Run """%PYW%"" ""%~dp0..\00. BACKEND\app.py""", 0, False

if exist "%VBS%" (
  echo [DONE] Widget autostart installed.
  echo  - It starts automatically at the next logon/boot.
  echo  - To start NOW without rebooting: double-click 실행\start_widget.bat
  echo  - To remove: delete "%VBS%"
) else (
  echo [FAILED] Could not write to the Startup folder.
)
echo.
pause
