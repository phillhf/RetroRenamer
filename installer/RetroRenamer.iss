; RetroRenamer – grafisches Setup und Deinstallation (Inno Setup 6)
; Bauen: installer\build.ps1   (baut erst dist\RetroRenamer.exe mit PyInstaller, dann dieses Setup)
;   oder direkt: ISCC.exe /DAppVersion=x.y.z installer\RetroRenamer.iss
;
; Ohne Administratorrechte: RetroRenamer legt DAT-Dateien und Einstellungen neben der EXE ab und
; aktualisiert sich selbst - beides braucht einen Ordner, in den der Benutzer schreiben darf.
; Stilles Setup:  RetroRenamer-Setup-x.y.z.exe /VERYSILENT [/DIR="D:\RetroRenamer"] [/TASKS="desktopicon"]
;   [/RESTARTAPP=1 (RetroRenamer nach dem Update wieder starten - so ruft es die Update-Funktion auf)]

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef DistDir
  #define DistDir "..\dist"
#endif

[Setup]
AppId={{C40C06C6-58F7-424D-B1BF-FD19AC8BFB31}
AppName=RetroRenamer
AppVersion={#AppVersion}
AppVerName=RetroRenamer {#AppVersion}
AppPublisher=Phill (phillhf)
AppPublisherURL=https://github.com/phillhf/RetroRenamer
AppSupportURL=https://github.com/phillhf/RetroRenamer/issues
AppUpdatesURL=https://github.com/phillhf/RetroRenamer/releases
VersionInfoVersion={#AppVersion}
VersionInfoDescription=RetroRenamer Setup
DefaultDirName=C:\Tools\RetroRenamer
AppendDefaultDirName=no
DirExistsWarning=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#DistDir}
OutputBaseFilename=RetroRenamer-Setup-{#AppVersion}
SetupIconFile=app.ico
WizardStyle=modern
LicenseFile=..\LICENSE
UninstallDisplayName=RetroRenamer
UninstallDisplayIcon={app}\RetroRenamer.exe
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=auto

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
de.WelcomeLabel1=Willkommen bei RetroRenamer
en.WelcomeLabel1=Welcome to RetroRenamer

[CustomMessages]
de.Welcome=Dieses Setup installiert RetroRenamer {#AppVersion}.%n%nRetroRenamer erkennt Retro-Spiele-ROMs anhand ihres Inhalts (Prüfsumme) und benennt sie mit dem korrekten Namen aus den No-Intro- und Redump-Datenbanken um.%n%nEs werden keine Administratorrechte benötigt.
en.Welcome=This setup installs RetroRenamer {#AppVersion}.%n%nRetroRenamer identifies retro game ROMs by their content (checksum) and renames them to their correct names from the No-Intro and Redump databases.%n%nNo administrator rights are required.
de.WelcomeUpdate=RetroRenamer %1 ist bereits installiert in%n%2%n%nDas Setup aktualisiert auf Version {#AppVersion}. DAT-Dateien und Einstellungen bleiben erhalten.
en.WelcomeUpdate=RetroRenamer %1 is already installed in%n%2%n%nThis setup updates it to version {#AppVersion}. DAT files and settings are kept.
de.NewerInstalled=Installiert ist bereits die neuere Version %1.%n%nTrotzdem die ältere Version {#AppVersion} einspielen?
en.NewerInstalled=The newer version %1 is already installed.%n%nInstall the older version {#AppVersion} anyway?
de.BadDir=Bitte einen Unterordner auf einer lokalen Festplatte wählen, z. B. C:\Tools\RetroRenamer.
en.BadDir=Please choose a subfolder on a local drive, e.g. C:\Tools\RetroRenamer.
de.DesktopIcon=Verknüpfung auf dem Desktop anlegen
en.DesktopIcon=Create a desktop shortcut
de.Shortcuts=Zusätzliche Verknüpfungen:
en.Shortcuts=Additional shortcuts:
de.Uninstall=RetroRenamer deinstallieren
en.Uninstall=Uninstall RetroRenamer
de.LaunchNow=RetroRenamer jetzt starten
en.LaunchNow=Start RetroRenamer now
de.Finished=RetroRenamer {#AppVersion} ist installiert.%n%nNächster Schritt: DAT-Dateien besorgen. Ohne sie kann RetroRenamer keine Spiele erkennen.%n  • Module und Handhelds (GB, SNES, GBA ...): Knopf „No-Intro-DATs (Webseite)“%n  • CD/DVD-Systeme (PlayStation, PS2 ...): Knopf „Redump-DATs laden...“%n%nUpdates bietet RetroRenamer beim Start automatisch an.
en.Finished=RetroRenamer {#AppVersion} is installed.%n%nNext step: get the DAT files. Without them RetroRenamer cannot recognize any games.%n  • Cartridges and handhelds (GB, SNES, GBA ...): “No-Intro DATs (website)” button%n  • CD/DVD systems (PlayStation, PS2 ...): “Get Redump DATs...” button%n%nRetroRenamer offers updates automatically when it starts.
de.No7Zip=Tipp: Für .7z- und .rar-Archive wird zusätzlich 7-Zip benötigt (www.7-zip.org). Es wurde auf diesem Rechner nicht gefunden.
en.No7Zip=Tip: .7z and .rar archives additionally require 7-Zip (www.7-zip.org). It was not found on this computer.
de.Operation=Vorgang:
en.Operation=Operation:
de.OpUpdate=Update von %1 auf {#AppVersion} (DAT-Dateien und Einstellungen bleiben erhalten)
en.OpUpdate=Update from %1 to {#AppVersion} (DAT files and settings are kept)
de.OpInstall=Neuinstallation von RetroRenamer {#AppVersion}
en.OpInstall=New installation of RetroRenamer {#AppVersion}
de.DeleteData=Sollen auch die DAT-Dateien und Einstellungen gelöscht werden?%n%nOrdner: %1%n%nBei „Nein“ bleiben sie erhalten. Eine spätere Neuinstallation in denselben Ordner übernimmt sie.
en.DeleteData=Should the DAT files and settings be deleted as well?%n%nFolder: %1%n%nIf you choose “No” they are kept. A later reinstallation into the same folder will use them again.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:Shortcuts}"

[Dirs]
Name: "{app}\dats"

[Files]
Source: "{#DistDir}\RetroRenamer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README_de.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\dats\README.md"; DestDir: "{app}\dats"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\RetroRenamer\RetroRenamer"; Filename: "{app}\RetroRenamer.exe"; WorkingDir: "{app}"
Name: "{autoprograms}\RetroRenamer\{cm:Uninstall}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\RetroRenamer"; Filename: "{app}\RetroRenamer.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\RetroRenamer.exe"; WorkingDir: "{app}"; Description: "{cm:LaunchNow}"; Flags: postinstall nowait skipifsilent
; Nach einem Update ueber die eingebaute Update-Funktion RetroRenamer wieder starten
Filename: "{app}\RetroRenamer.exe"; WorkingDir: "{app}"; Flags: nowait; Check: RestartAfterSilentUpdate

[UninstallDelete]
; vom Programm selbst angelegte Dateien (Zwischenspeicher, Reste eines EXE-Updates)
Type: files; Name: "{app}\dats\.retrorenamer_cache.pkl"
Type: files; Name: "{app}\RetroRenamer.exe.*.old"
Type: files; Name: "{app}\RetroRenamer.exe.old"
Type: files; Name: "{app}\RetroRenamer.exe.new"
Type: dirifempty; Name: "{app}\dats"
Type: dirifempty; Name: "{app}"

[Code]
var
  OldVersion, OldDir: String;

// Versionen wie 1.10.2 vergleichen: <0 aelter, 0 gleich, >0 neuer
function CompareVersion(A, B: String): Integer;
var
  PA, PB, NA, NB: Integer;
begin
  Result := 0;
  while (Result = 0) and ((A <> '') or (B <> '')) do
  begin
    PA := Pos('.', A); PB := Pos('.', B);
    if PA = 0 then begin NA := StrToIntDef(A, 0); A := ''; end else begin NA := StrToIntDef(Copy(A, 1, PA - 1), 0); A := Copy(A, PA + 1, Length(A)); end;
    if PB = 0 then begin NB := StrToIntDef(B, 0); B := ''; end else begin NB := StrToIntDef(Copy(B, 1, PB - 1), 0); B := Copy(B, PB + 1, Length(B)); end;
    Result := NA - NB;
  end;
end;

function UninstallKey(): String;
begin
  Result := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{C40C06C6-58F7-424D-B1BF-FD19AC8BFB31}_is1';
end;

function IsUpdate(): Boolean;
begin
  Result := OldVersion <> '';
end;

// Vor dem Assistenten: vorhandene Installation erkennen
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not RegQueryStringValue(HKCU, UninstallKey(), 'DisplayVersion', OldVersion) then
    RegQueryStringValue(HKLM, UninstallKey(), 'DisplayVersion', OldVersion);
  if not RegQueryStringValue(HKCU, UninstallKey(), 'InstallLocation', OldDir) then
    RegQueryStringValue(HKLM, UninstallKey(), 'InstallLocation', OldDir);
  if IsUpdate() and (CompareVersion(OldVersion, '{#AppVersion}') > 0) and not WizardSilent() then
    Result := MsgBox(FmtMessage(CustomMessage('NewerInstalled'), [OldVersion]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure InitializeWizard;
begin
  if IsUpdate() then
    WizardForm.WelcomeLabel2.Caption := FmtMessage(CustomMessage('WelcomeUpdate'), [OldVersion, RemoveBackslashUnlessRoot(OldDir)])
  else
    WizardForm.WelcomeLabel2.Caption := CustomMessage('Welcome');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  // Bei einem Update bleibt der Ordner - nur bei einer Neuinstallation fragen
  Result := (PageID = wpSelectDir) and IsUpdate();
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  D: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    D := WizardForm.DirEdit.Text;
    if (Copy(D, 1, 2) = '\\') or (Length(D) <= 3) then
    begin
      MsgBox(CustomMessage('BadDir'), mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := CustomMessage('Operation') + NewLine + Space;
  if IsUpdate() then
    Result := Result + FmtMessage(CustomMessage('OpUpdate'), [OldVersion])
  else
    Result := Result + CustomMessage('OpInstall');
  Result := Result + NewLine + NewLine + MemoDirInfo;
  if MemoTasksInfo <> '' then Result := Result + NewLine + NewLine + MemoTasksInfo;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  // Stilles Update aus dem Programm heraus: laufendes RetroRenamer beenden, damit die EXE ersetzt werden kann.
  // (Interaktiv fragt Inno Setup selbst nach, ob laufende Programme geschlossen werden sollen.)
  if WizardSilent() then
  begin
    Sleep(1500);
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM RetroRenamer.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Sleep(500);
  end;
  Result := '';
end;

function RestartAfterSilentUpdate(): Boolean;
begin
  Result := WizardSilent() and (ExpandConstant('{param:RESTARTAPP|0}') = '1');
end;

function Have7Zip(): Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf64}\7-Zip\7z.exe')) or FileExists(ExpandConstant('{commonpf32}\7-Zip\7z.exe'))
    or FileExists(ExpandConstant('{localappdata}\Programs\7-Zip\7z.exe'));
end;

procedure CurPageChanged(CurPageID: Integer);
var
  T: String;
begin
  if CurPageID = wpFinished then
  begin
    T := CustomMessage('Finished');
    if not Have7Zip() then T := T + #13#10#13#10 + CustomMessage('No7Zip');
    WizardForm.FinishedLabel.Caption := T;
    WizardForm.AdjustLabelHeight(WizardForm.FinishedLabel);
    WizardForm.RunList.Top := WizardForm.FinishedLabel.Top + WizardForm.FinishedLabel.Height + ScaleY(12);
  end;
end;

// ---- Deinstallation: DAT-Dateien und Einstellungen auf Wunsch behalten
var
  DeleteData: Boolean;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  DeleteData := False;
  if not UninstallSilent() then
    DeleteData := MsgBox(FmtMessage(CustomMessage('DeleteData'), [ExpandConstant('{app}')]),
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep <> usPostUninstall then Exit;
  if DeleteData then
  begin
    DelTree(ExpandConstant('{app}\dats'), True, True, True);
    DeleteFile(ExpandConstant('{app}\retrorenamer_settings.json'));
    RemoveDir(ExpandConstant('{app}'));
  end;
end;
