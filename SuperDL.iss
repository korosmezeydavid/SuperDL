; SuperDL telepítő (Inno Setup 6) – a onedir build csomagolása.
; Fordítás:  ISCC.exe /DMyAppVersion=3.26.0 SuperDL.iss
; (a verziót a build-szkript adja át; az alapérték lentebb)

#ifndef MyAppVersion
  #define MyAppVersion "3.25.1"
#endif
#define MyAppName "SuperDL"
#define MyAppPublisher "Kőrösmezey Dávid"
#define MyAppURL "https://github.com/korosmezeydavid/SuperDL"
#define MyAppExeName "SuperDL.exe"
#define DistDir "dist\SuperDL"

[Setup]
; Állandó AppId a frissítésekhez/eltávolításhoz (NE változzon verziók közt)
AppId={{B8F2A1C4-7E3D-4A9B-9C2E-5D1F6A0B3C7E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
; FELHASZNÁLÓI telepítés (nincs admin): a mappa ÍRHATÓ marad → a self-update és a
; modulok működnek rendszergazda nélkül. Ez a moduláris terv mappaszerkezete.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; ÖNFRISSÍTÉS onedir-ben: a telepítő a futó SuperDL-t bezárja (mutex + Restart
; Manager) és a végén újraindítja – így a `_internal` mappa is cserélődhet.
AppMutex=SuperDL_SingleInstance_Mutex
CloseApplications=yes
RestartApplications=yes
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=SuperDL-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
; akadálymentes: nincs felesleges kép, tiszta szöveges varázsló
SetupIconFile=
DisableWelcomePage=no

[Languages]
Name: "hu"; MessagesFile: "compiler:Languages\Hungarian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; a teljes onedir-tartalom (exe + DLL-ek + adatmappák), almappákkal együtt
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; a frissítés-maradékok takarítása eltávolításkor (a felhasználói ADATOKAT –
; ~/.superdl, modules – SOHA nem töröljük, az máshol, a profilban van)
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
