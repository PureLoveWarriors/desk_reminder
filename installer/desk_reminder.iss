; Desk Reminder 安装脚本。先 python build.py，再 python build_setup.py。
; 安装范围由向导选择：所有用户（Program Files，需管理员）或仅为我（LocalAppData\Programs）。

#define AppName "Desk Reminder"
#define AppVersion "1.0.0"
#define AppPublisher "PureLoveWarriors"
#define AppExe "DeskReminder.exe"

[Setup]
AppId={{8F4E2A91-6C3D-4B17-A5E8-1D9C0B7E4F26}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Desk Reminder Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion=1.0.0.0
DefaultDirName={autopf}\DeskReminder
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=no
LicenseFile=disclaimer.txt
OutputDir=..\dist
OutputBaseFilename=DeskReminder-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=force
RestartApplications=no
AlwaysShowDirOnReadyPage=yes
ShowLanguageDialog=no

[Languages]
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单项不可取消，Win 搜索靠这个名字。
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "立即运行 {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function IsAppRunning: Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if not Exec(
    ExpandConstant('{cmd}'),
    '/C tasklist /FI "IMAGENAME eq {#AppExe}" /NH | find /I "{#AppExe}">NUL',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Exit;
  Result := ResultCode = 0;
end;

function EnsureAppClosed: Boolean;
begin
  Result := True;
  while IsAppRunning do
  begin
    if MsgBox('Desk Reminder 正在运行。' #13#10 +
              '请先退出程序（包括系统托盘），然后点“重试”。',
              mbError, MB_RETRYCANCEL) = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;
  end;
end;

function InitializeSetup: Boolean;
begin
  Result := EnsureAppClosed;
end;

function InitializeUninstall: Boolean;
begin
  Result := EnsureAppClosed;
end;
