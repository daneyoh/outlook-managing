@echo off
REM Install autostart for the desktop widget WITHOUT admin / Task Scheduler.

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP%\OutlookMailWidget.vbs"

REM 빌드된 exe(설치\build.bat 결과물)가 있으면 그걸 우선 사용한다 —
REM pythonw.exe로 직접 실행하면 이 머신에서 작업표시줄 버튼 자체가 안 뜨는
REM 현상이 실측 확인됨(원인: pythonw.exe 호스팅 자체의 셸 등록 문제, 코드 문제
REM 아님). 빌드된 OutlookWidget.exe 는 동일하게 재현해도 정상적으로 작업
REM 표시줄에 뜬다 — 그래서 있으면 exe, 없으면 기존 pythonw 방식으로 폴백.
REM 주의: exe 는 WScript.Shell.Run 의 표시 스타일(0=SW_HIDE)을 첫 폼이 그대로
REM 물려받아 완전히 숨겨진 채로 뜨는 현상이 실측 확인됨(.NET WinForms 이
REM 프로세스의 최초 상속 show-state 를 첫 Form 에 적용하는 동작 — pythonw
REM 실행 경로는 창이 별도 스레드에서 나중에 생성돼 이 영향을 안 받아 0 이어도
REM 정상 표시됨, 아래 pythonw 분기는 그대로 둘 것). exe 는 반드시 1(SW_SHOWNORMAL).
set "BUILT_EXE=%~dp0..\dist\OutlookWidget\OutlookWidget.exe"
if exist "%BUILT_EXE%" (
  > "%VBS%" echo Set sh = CreateObject("WScript.Shell")
  >>"%VBS%" echo sh.Run """%BUILT_EXE%""", 1, False
  goto :done
)

echo [안내] 빌드된 실행파일이 없어 소스 실행(pythonw)으로 자동시작을 등록합니다.
echo        이 경로는 이 PC에서 작업표시줄 아이콘이 안 뜰 수 있습니다(기능은 정상).
echo        작업표시줄 아이콘까지 원하면 설치\build.bat 로 먼저 빌드하세요.
echo.

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

:done
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
