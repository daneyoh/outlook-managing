@echo off
REM Remove autostart launcher from the Startup folder.
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\OutlookMailFetch.vbs" 2>nul
echo [DONE] Autostart removed.
echo  - A fetcher already running this session stops at next logoff/restart.
echo  - To stop it immediately: end "pythonw.exe" in Task Manager.
echo.
pause
