# Baut dist\RetroRenamer.exe (PyInstaller) und dist\RetroRenamer-Setup-<Version>.exe (Inno Setup 6).
# Die Version kommt ausschliesslich aus retrorenamer.py (VERSION = "x.y.z").
# Aufruf aus dem Projektordner:  powershell -ExecutionPolicy Bypass -File installer\build.ps1 [-SkipTests]

param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$src = Get-Content "retrorenamer.py" -Raw
if ($src -notmatch 'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"') { throw "VERSION in retrorenamer.py nicht gefunden" }
$version = "$($Matches[1]).$($Matches[2]).$($Matches[3])"
$tuple = "($($Matches[1]), $($Matches[2]), $($Matches[3]), 0)"
Write-Host "Baue RetroRenamer $version"

$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

if (-not $SkipTests) {
    & $python tests\test_retrorenamer.py
    if ($LASTEXITCODE -ne 0) { throw "Tests fehlgeschlagen" }
}

# Versionsinfo fuer die Dateieigenschaften der EXE
New-Item -ItemType Directory -Force build | Out-Null
@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=$tuple, prodvers=$tuple, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704B0', [
      StringStruct('CompanyName', 'Phill (phillhf)'),
      StringStruct('FileDescription', 'RetroRenamer - ROMs anhand des Inhalts erkennen und umbenennen'),
      StringStruct('FileVersion', '$version'),
      StringStruct('InternalName', 'RetroRenamer'),
      StringStruct('LegalCopyright', 'MIT License - Phill (phillhf)'),
      StringStruct('OriginalFilename', 'RetroRenamer.exe'),
      StringStruct('ProductName', 'RetroRenamer'),
      StringStruct('ProductVersion', '$version')])]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
"@ | Set-Content "build\version_info.txt" -Encoding utf8

& $python -m PyInstaller --noconfirm --onefile --windowed --name RetroRenamer `
    --icon "$root\installer\app.ico" --add-data "$root\installer\app.ico;." --version-file "$root\build\version_info.txt" `
    --distpath dist --workpath build\pyinstaller --specpath build retrorenamer_gui.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fehlgeschlagen" }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 nicht gefunden (winget install JRSoftware.InnoSetup)" }

& $iscc /Q "/DAppVersion=$version" installer\RetroRenamer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup fehlgeschlagen" }

Get-Item "dist\RetroRenamer.exe", "dist\RetroRenamer-Setup-$version.exe" |
    ForEach-Object { Write-Host ("{0,-36} {1,6:N1} MB" -f $_.Name, ($_.Length / 1MB)) }
