; Hard2Assist installer, for Inno Setup 6.3 or newer (free, no account): https://jrsoftware.org/isdl.php
;
; Built by build.py, which passes the name, publisher, version and folder from version.py:
;
;     python build.py --installer
;
; Unprivileged: it installs per user under %LOCALAPPDATA%\Programs with no UAC prompt, and the
; user can still choose an all-users install. Hard2Assist itself needs no elevation.

#ifndef AppVersion
  #error Build the installer with: python build.py --installer
#endif

#define AppExe AppName + ".exe"
#define AppUrl "https://github.com/S11mk3/Hard2Assist"


[Setup]
; Never change AppId: it is how Windows recognises an existing installation, and a new one would
; leave the old version installed alongside the new.
AppId={{2467736F-DA9D-4495-AD45-D622FCFD0AC1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
VersionInfoVersion={#AppVersion}

; {autopf} follows the user's choice: %LOCALAPPDATA%\Programs, or Program Files for everyone.
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; The .exe is 64-bit, and the Windows APIs it calls are Windows 10 or newer.
ArchitecturesAllowed=x64compatible
MinVersion=10.0

SetupMutex={#AppName}Setup,Global\{#AppName}Setup
; The mutex the running app holds (win.first_instance), so setup knows to ask for it to be closed.
AppMutex=Hard2AssistRunning
; Restart Manager notices Hard2Assist running and offers to close it, rather than failing
; halfway through with files in use.
CloseApplications=yes
RestartApplications=no

OutputDir=installer
OutputBaseFilename={#AppName}-Setup
Compression=lzma2/max
SolidCompression=yes
SetupIconFile=H2A.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

WizardStyle=modern
WizardSizePercent=110
DisableWelcomePage=no
ShowLanguageDialog=no

; Uncomment once a code-signing certificate is configured: signing is the only thing that removes
; the SmartScreen warning.
; SignTool=signtool


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"


[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nHard2Assist sits at the top of your screen and listens for a wake word, then opens programs and websites, moves and closes windows, types for you, controls the volume, and answers questions about your PC out loud.%n%nIt needs a microphone. The first time it starts, it downloads its hearing and its voice (about 400 MB, once); after that it works offline, and nothing you say ever leaves your PC.


[Tasks]
; Unchecked by default, which is the Windows convention.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Start {#AppName} when Windows starts"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked


[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon


[Registry]
; The same value the dock's "Start when Windows starts" switch writes (win.set_starts_with_windows).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: startup


[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent


[UninstallDelete]
; Written after installation, so the uninstaller does not know about them: comtypes generates its
; COM wrappers on first use, into the app folder when writable and into %TEMP% when not.
Type: filesandordirs; Name: "{app}\_internal\comtypes\gen"
Type: filesandordirs; Name: "{%TEMP}\comtypes_cache\{#AppName}-*"
Type: dirifempty; Name: "{app}"


[Code]
{ The user's own files live apart from the installation -- settings and saved apps in
  %APPDATA%\Hard2Assist, the downloaded hearing and voice in %LOCALAPPDATA%\Hard2Assist -- so the
  uninstaller asks before removing them, defaulting to keep. SuppressibleMsgBox, not MsgBox: a
  /VERYSILENT uninstall would otherwise hang on a dialog nobody can see; this one answers IDNO.

  The start-with-Windows value goes either way: the dock's switch can have written it even when
  the installer did not, and it would point at a program that is gone. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir, ModelDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#AppName}');

    DataDir := ExpandConstant('{userappdata}\{#AppName}');
    ModelDir := ExpandConstant('{localappdata}\{#AppName}');
    if DirExists(DataDir) or DirExists(ModelDir) then
    begin
      if SuppressibleMsgBox('Also remove your Hard2Assist settings and downloads?' + #13#10#13#10 +
                            'This is your wake word and voice, the apps and websites you added, ' +
                            'any commands you added, the log, and the downloaded hearing and voice ' +
                            '(about 400 MB).' + #13#10#13#10 +
                            'Choose No to keep them for a future reinstall.',
                            mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
        DelTree(ModelDir, True, True, True);
      end;
    end;
  end;
end;
