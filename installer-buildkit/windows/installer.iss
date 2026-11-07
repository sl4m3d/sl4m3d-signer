#define MyAppName "sl4m3d Signer"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "sl4m3d"
#define MyAppExeName "sl4m3d Signer.exe"

[Setup]
AppId={{A30C6DE7-AC59-46A1-AC37-0C79C379A12B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\sl4m3d Signer
DefaultGroupName=sl4m3d Signer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=windows\output
OutputBaseFilename=sl4m3d-Signer-Setup-v1.2.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "dist\sl4m3d Signer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\sl4m3d Signer"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\sl4m3d Signer"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Verknüpfungen:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "sl4m3d Signer starten"; Flags: nowait postinstall skipifsilent
