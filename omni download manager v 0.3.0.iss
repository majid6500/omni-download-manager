#define MyAppName "Omni Download Manager"
#define MyAppVersion "0.3.0"
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
Source: "browser_extension\*"; \
    DestDir: "{app}\browser_extension"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
Type: files; Name: "{app}\browser_integration\com.omni_download_manager.json"

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

[Code]
const
  ChromeHostKey = 'Software\Google\Chrome\NativeMessagingHosts\com.omni_download_manager';
  EdgeHostKey = 'Software\Microsoft\Edge\NativeMessagingHosts\com.omni_download_manager';

var
  BrowserPage: TInputQueryWizardPage;

function IsExtensionId(Value: String): Boolean;
var
  Index: Integer;
begin
  Result := Length(Value) = 32;
  if not Result then
    Exit;
  for Index := 1 to Length(Value) do
    if (Value[Index] < 'a') or (Value[Index] > 'p') then
    begin
      Result := False;
      Exit;
    end;
end;

function JsonEscape(Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

procedure InitializeWizard;
var
  Existing: String;
begin
  BrowserPage := CreateInputQueryPage(
    wpSelectDir,
    'Browser companion',
    'Connect Chrome or Microsoft Edge to Omni Download Manager',
    'The extension must be installed separately from its official store. ' +
    'Enter its 32-character ID to register the desktop Native Messaging host. ' +
    'Leave an ID blank to skip that browser.'
  );
  BrowserPage.Add('Chrome extension ID (optional)', False);
  BrowserPage.Add('Microsoft Edge extension ID (optional)', False);
  if RegQueryStringValue(HKLM, ChromeHostKey, 'ExtensionId', Existing) then
    BrowserPage.Values[0] := Existing;
  if RegQueryStringValue(HKLM, EdgeHostKey, 'ExtensionId', Existing) then
    BrowserPage.Values[1] := Existing;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = BrowserPage.ID then
  begin
    if (Trim(BrowserPage.Values[0]) <> '') and
       not IsExtensionId(Trim(BrowserPage.Values[0])) then
    begin
      MsgBox('The Chrome extension ID must contain 32 letters from a to p.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if (Trim(BrowserPage.Values[1]) <> '') and
       not IsExtensionId(Trim(BrowserPage.Values[1])) then
    begin
      MsgBox('The Edge extension ID must contain 32 letters from a to p.',
        mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ChromeId, EdgeId, Origins, ManifestPath, NativeHostPath, Manifest: String;
begin
  if CurStep <> ssPostInstall then
    Exit;

  ChromeId := Trim(BrowserPage.Values[0]);
  EdgeId := Trim(BrowserPage.Values[1]);

  Origins := '';
  if ChromeId <> '' then
    Origins := '"chrome-extension://' + ChromeId + '/"';
  if EdgeId <> '' then
  begin
    if Origins <> '' then
      Origins := Origins + ',';
    Origins := Origins + '"chrome-extension://' + EdgeId + '/"';
  end;

  if Origins = '' then
  begin
    RegDeleteKeyIncludingSubkeys(HKLM, ChromeHostKey);
    RegDeleteKeyIncludingSubkeys(HKLM, EdgeHostKey);
    Exit;
  end;

  ManifestPath := ExpandConstant('{app}\browser_integration\com.omni_download_manager.json');
  NativeHostPath := ExpandConstant('{app}\ODM Native Host.exe');
  if not ForceDirectories(ExtractFileDir(ManifestPath)) then
    RaiseException('Could not create the browser integration folder.');
  Manifest := '{"name":"com.omni_download_manager",' +
    '"description":"Omni Download Manager browser bridge",' +
    '"path":"' + JsonEscape(NativeHostPath) + '",' +
    '"type":"stdio","allowed_origins":[' + Origins + ']}';
  if not SaveStringToFile(ManifestPath, UTF8Encode(Manifest), False) then
    RaiseException('Could not write the Native Messaging host manifest.');

  if ChromeId <> '' then
  begin
    if not RegWriteStringValue(HKLM, ChromeHostKey, '', ManifestPath) or
       not RegWriteStringValue(HKLM, ChromeHostKey, 'ExtensionId', ChromeId) then
      RaiseException('Could not register the Native Messaging host for Chrome.');
  end
  else
    RegDeleteKeyIncludingSubkeys(HKLM, ChromeHostKey);

  if EdgeId <> '' then
  begin
    if not RegWriteStringValue(HKLM, EdgeHostKey, '', ManifestPath) or
       not RegWriteStringValue(HKLM, EdgeHostKey, 'ExtensionId', EdgeId) then
      RaiseException('Could not register the Native Messaging host for Microsoft Edge.');
  end
  else
    RegDeleteKeyIncludingSubkeys(HKLM, EdgeHostKey);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RegDeleteKeyIncludingSubkeys(HKLM, ChromeHostKey);
    RegDeleteKeyIncludingSubkeys(HKLM, EdgeHostKey);
  end;
end;