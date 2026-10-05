#define MyAppName "Omni Download Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "NIK Shop"
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

SetupIconFile="E:\Cluade\omni-download-manager ODM\dist\Omni Download Manager\OMD icon.ico"

UninstallDisplayIcon={app}\OMD icon.ico

PrivilegesRequired=admin

[Files]
Source: "E:\Cluade\omni-download-manager ODM\dist\Omni Download Manager\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\OMD icon.ico"

Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\OMD icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "Launch {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent