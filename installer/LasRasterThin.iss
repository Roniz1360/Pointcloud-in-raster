; Inno-Setup-Skript: erstellt LasRasterThin-Setup-<Version>.exe
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6C1E2B7A-4F0B-4B8E-9C61-2D7A9F3E5A10}
AppName=LasRasterThin
AppVersion={#AppVersion}
AppPublisher=LasRasterThin
DefaultDirName={autopf}\LasRasterThin
DefaultGroupName=LasRasterThin
OutputDir=Output
OutputBaseFilename=LasRasterThin-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
VersionInfoVersion={#AppVersion}
VersionInfoCompany=LasRasterThin
VersionInfoDescription=LasRasterThin Setup
VersionInfoProductName=LasRasterThin
VersionInfoProductVersion={#AppVersion}
UninstallDisplayIcon={app}\LasRasterThin.exe

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzlich:"

[Files]
Source: "..\dist\LasRasterThin\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\LasRasterThin"; Filename: "{app}\LasRasterThin.exe"
Name: "{group}\LasRasterThin deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\LasRasterThin"; Filename: "{app}\LasRasterThin.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LasRasterThin.exe"; Description: "LasRasterThin starten"; Flags: nowait postinstall skipifsilent
