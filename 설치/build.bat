@echo off
chcp 65001 > nul

:: 프로젝트 루트를 작업 디렉터리로 고정 (이 배치는 설치\ 하위에 있음)
cd /d "%~dp0.."

echo ============================================
echo  Outlook Widget 배포 빌드
echo ============================================

:: 의존성 설치
echo [1/3] 패키지 설치 중...
python -m pip install pyinstaller pywebview msal requests win11toast pywin32 --quiet
if errorlevel 1 (
    echo.
    echo [오류] 패키지 설치 실패. Python이 설치되어 있는지 확인하세요.
    pause & exit /b 1
)

:: 기존 빌드 정리
echo [2/3] 이전 빌드 정리 중...
if exist "dist\OutlookWidget" rmdir /s /q "dist\OutlookWidget"
if exist "build\OutlookWidget" rmdir /s /q "build\OutlookWidget"

:: 빌드 실행
echo [3/3] PyInstaller 빌드 중...
python -m PyInstaller build.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [오류] 빌드 실패. 위 오류 메시지를 확인하세요.
    pause & exit /b 1
)

echo.
echo ============================================
echo  빌드 완료: dist\OutlookWidget\
echo  OutlookWidget.exe 를 실행하면 됩니다.
echo ============================================
pause
