; Hard2Assist installer.
;
; Built by build.py, which passes the version and the folder to package:
;
;     python build.py --installer
;
; Needs Inno Setup 6.3 or newer (free, no account): https://jrsoftware.org/isdl.php
;
; Unprivileged. It defaults to a per-user install under
; %LOCALAPPDATA%\Programs, which needs no administrator rights and raises no
; UAC prompt; the user can still choose an all-users install from the first
; page. Hard2Assist needs no elevation at all -- it writes only to its own
; folder and to %APPDATA%.

#define AppName "Hard2Assist"
#define AppPublisher "Andrija Simic"
#define AppExe "Hard2Assist.exe"
#define AppUrl "https://github.com/S11mk3/Hard2Assist"

; Both are supplied by build.py; the fallbacks let the script be compiled by
; hand from the Inno Setup IDE.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppSource
  #define AppSource "dist\Hard2Assist"
#endif


[Setup]
; Never change AppId: it is how Windows recognises an existing installation,
; and a new one would leave the old version installed alongside the new.
AppId={{2467736F-DA9D-4495-AD45-D622FCFD0AC1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
VersionInfoVersion={#AppVersion}

; {autopf} is %LOCALAPPDATA%\Programs for a per-user install and Program Files
; for an all-users one, so this follows whichever the user picked.
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

; -- privileges ------------------------------------------------------------
; lowest = install per-user with no elevation. "dialog" adds the page that
; lets the user choose an all-users install instead, which then elevates.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; -- where it will and will not run ----------------------------------------
; The .exe is 64-bit, and every Windows API the app calls is Windows 10 or
; newer. Refuse rather than install something that cannot start.
ArchitecturesAllowed=x64compatible
MinVersion=10.0

; -- safety ----------------------------------------------------------------
; Stops a second copy of the installer running at the same time.
SetupMutex={#AppName}Setup,Global\{#AppName}Setup
; Uses Restart Manager to notice Hard2Assist already running and offer to
; close it, instead of failing halfway through with files in use.
CloseApplications=yes
RestartApplications=no

; -- output ----------------------------------------------------------------
OutputDir=installer
OutputBaseFilename={#AppName}-Setup
Compression=lzma2/max
SolidCompression=yes
SetupIconFile=H2A.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

; -- appearance ------------------------------------------------------------
WizardStyle=modern
WizardSizePercent=110
DisableWelcomePage=no
ShowLanguageDialog=no

; Uncomment once a code-signing certificate is configured. Signing the
; installer is what removes the SmartScreen warning; nothing else does.
; SignTool=signtool


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"


[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nHard2Assist listens for a wake word and then opens programs and websites, controls volume and media, and answers questions about your PC out loud.%n%nIt needs a microphone and an internet connection.


[Tasks]
; Unchecked by default, which is the Windows convention.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked


[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon


[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent


[UninstallDelete]
; Written after installation, so the uninstaller does not know about them:
; comtypes generates its SAPI wrapper on first run, into the app folder when
; that is writable and into %TEMP% when it is not.
Type: filesandordirs; Name: "{app}\_internal\comtypes\gen"
Type: filesandordirs; Name: "{%TEMP}\comtypes_cache\{#AppName}-*"
Type: dirifempty; Name: "{app}"


[Code]
{ The user's settings and saved apps live in %APPDATA%\Hard2Assist, separately
  from the installation, so the uninstaller asks before removing them. The
  default is to keep them.

  SuppressibleMsgBox rather than MsgBox: a plain MsgBox is shown even during a
  /VERYSILENT uninstall, where nobody can answer it and the uninstall hangs on
  a dialog no one can see. This one returns the IDNO default whenever message
  boxes are suppressed, so an unattended uninstall keeps the settings. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\{#AppName}');

    if DirExists(DataDir) then
    begin
      if SuppressibleMsgBox('Also remove your Hard2Assist settings?' + #13#10#13#10 +
                            'This is your wake word, how it listens, and any apps ' +
                            'you added by hand.' + #13#10#13#10 +
                            'Choose No to keep them for a future reinstall.',
                            mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
