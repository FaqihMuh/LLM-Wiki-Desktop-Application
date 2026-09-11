; Inno Setup script for the LLM Wiki desktop application.
;
; Packages the existing PyInstaller onedir build (dist\LLM Wiki\, produced
; by `python build.py` / `pyinstaller gui.spec`) into a standard Windows
; installer. This script does not build the application — run build.py
; first (or let installer_build.py do it for you).
;
; Installs the application only. Workspace creation (CLAUDE.md, docs/,
; wiki/, raw/) remains the responsibility of WorkspaceManager on first
; launch — nothing here creates, repairs, or removes a workspace.
;
; Build with:
;   iscc installer.iss
; or:
;   python installer_build.py

#define MyAppName "LLM Wiki"
#define MyAppVersion "1.1.0"
#define MyAppExeName "LLM Wiki.exe"
#define MyDistDir "dist-final-r3\LLM Wiki"

[Setup]
; Fixed AppId — the same value must be kept across every release so
; Windows (and the [Code] upgrade check below) recognizes a newer build
; as an upgrade of the same product rather than a separate install.
AppId={{5D5EF1C1-B158-4FD6-AE0C-CFDED1D5DD28}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer\output
OutputBaseFilename=LLM_Wiki_Setup_r3
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Program Files requires elevation; the installer itself never touches
; the user's workspace (which lives outside {app}, e.g. under Documents).
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; Everything PyInstaller produced for the onedir build, verbatim —
; the .exe plus its bundled runtime (PySide6, Python, and the bundled
; assets/workspace_template used later by WorkspaceManager.create()).
; Nothing here is a workspace; it is application payload only.
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
// ── Upgrade detection ──────────────────────────────────────────────
//
// Looks up the standard Windows uninstall registry entry for this
// AppId (never scans the filesystem for stray .exe files). If a
// previous install is found, the user is offered the choice to
// uninstall it first; declining aborts setup so two copies can never
// coexist. The previous version's uninstaller only removes what it
// installed under its own {app} — it has no knowledge of the user's
// workspace, so the workspace is never touched by this step.

function GetUninstallString(): String;
var
  sUnInstPath: String;
  sUnInstallString: String;
begin
  sUnInstPath := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1';
  sUnInstallString := '';
  if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    RegQueryStringValue(HKLM32, sUnInstPath, 'UninstallString', sUnInstallString);
  Result := sUnInstallString;
end;

function InitializeSetup(): Boolean;
var
  sUnInstallString: String;
  iResultCode: Integer;
begin
  Result := True;
  sUnInstallString := GetUninstallString();
  if sUnInstallString <> '' then
  begin
    if MsgBox('An existing installation of {#MyAppName} was found.' + #13#10 +
              'It must be uninstalled before Setup can continue.' + #13#10#13#10 +
              'Uninstall the previous version now?',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      sUnInstallString := RemoveQuotes(sUnInstallString);
      Exec(sUnInstallString, '/SILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_SHOWNORMAL,
        ewWaitUntilTerminated, iResultCode);
    end
    else
      Result := False; // user declined — abort setup rather than allow two copies
  end;
end;
