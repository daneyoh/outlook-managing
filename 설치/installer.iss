; ============================================================
;  Outlook 메일 위젯 — Inno Setup 설치파일 스크립트
;  빌드: 설치\build.bat 로 dist\OutlookWidget\ 를 먼저 만든 뒤,
;        이 파일을 Inno Setup(ISCC.exe installer.iss)으로 컴파일한다.
;  결과물: 설치\output\OutlookWidgetSetup.exe (배포용 단일 파일)
; ============================================================

#define MyAppName "Outlook 메일 위젯"
#define MyAppVersion "1.0.0"
#define MyAppExeName "OutlookWidget.exe"

[Setup]
AppId={{B7B6C6C4-6C2A-4E9F-9C7B-1B7B0B8F3B9A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Outlook Mail Widget
DefaultDirName={localappdata}\Programs\OutlookMailWidget
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=OutlookWidgetSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\widget.ico

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "바로가기:"
Name: "startupicon"; Description: "Windows 시작 시 자동 실행"; GroupDescription: "바로가기:"; Flags: unchecked

[Files]
Source: "..\dist\OutlookWidget\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; 이미 설치돼 있어도 몇 초 안에 조용히 끝나므로(no-op) 굳이 레지스트리로
; 사전 확인하지 않는다 — 32/64비트 리다이렉션 때문에 확인 자체가 더 불안정함.
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "WebView2 런타임 확인 중..."; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ConfigPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  ConfigPage := CreateInputQueryPage(wpSelectDir,
    'Microsoft 365 연결 설정', 'Azure 앱 등록 정보를 입력하세요',
    'Azure Portal > 앱 등록 > 개요 화면에서 확인할 수 있습니다. 모르면 관리자에게 문의하세요.');
  ConfigPage.Add('애플리케이션(클라이언트) ID:', False);
  ConfigPage.Add('디렉터리(테넌트) ID (모르면 organizations):', False);
  ConfigPage.Add('본인 이메일 주소:', False);
  ConfigPage.Add('본인 이름:', False);

  ConfigPage.Values[1] := 'organizations';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  // 무인(silent) 설치 시에는 확인해줄 사람이 없으므로 메시지박스로 막지 않는다
  // (막으면 클릭할 사람 없이 영원히 대기하다 멈춘 것처럼 보임).
  if WizardSilent then
    Exit;
  if CurPageID = ConfigPage.ID then
  begin
    if ConfigPage.Values[0] = '' then
    begin
      MsgBox('클라이언트 ID를 입력하세요.', mbError, MB_OK);
      Result := False;
    end;
    if ConfigPage.Values[2] = '' then
    begin
      MsgBox('이메일 주소를 입력하세요.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  StateDir, ConfigPath, TenantId: String;
  JsonLines: TArrayOfString;
begin
  if CurStep = ssPostInstall then
  begin
    StateDir := ExpandConstant('{app}\02. DB\state');
    if not DirExists(StateDir) then
      ForceDirectories(StateDir);

    TenantId := ConfigPage.Values[1];
    if TenantId = '' then TenantId := 'organizations';

    ConfigPath := StateDir + '\user_config.json';
    SetArrayLength(JsonLines, 6);
    JsonLines[0] := '{';
    JsonLines[1] := '  "CLIENT_ID": "' + ConfigPage.Values[0] + '",';
    JsonLines[2] := '  "TENANT_ID": "' + TenantId + '",';
    JsonLines[3] := '  "MY_EMAIL": "' + ConfigPage.Values[2] + '",';
    JsonLines[4] := '  "MY_NAME": "' + ConfigPage.Values[3] + '"';
    JsonLines[5] := '}';
    SaveStringsToFile(ConfigPath, JsonLines, False);
  end;
end;
