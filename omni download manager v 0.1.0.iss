#define MyAppName "Omni Download Manager"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Omni Download Manager"
#define MyAppExeName "Omni Download Manager.exe"

[Setup]
AppId={{OMNI-DOWNLOAD-MANAGER}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

OutputDir=installer
OutputBaseFilename=Omni-Download-Manager-Setup

Compression=lzma
SolidCompression=yes

ArchitecturesInstallIn64BitMode=x64compatible

; Paths are relative to this script so the build works from any checkout.
; The executable already carries the icon, so shortcuts and the uninstall entry
; point at it instead of a loose .ico file (which PyInstaller does not copy).
SetupIconFile="omni_download_manager\resources\app.ico"

UninstallDisplayIcon={app}\Omni Download Manager.exe

PrivilegesRequired=admin

[Files]
Source: "dist\Omni Download Manager\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\{#MyAppExeName}"

Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "Launch {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent