# SuperDL – onedir PyInstaller build + Inno Setup telepítő egy lépésben.
# Használat:  powershell -File tools\build_installer.ps1 [-Version 3.26.0]
param([string]$Version = "")
$ErrorActionPreference = "Stop"
$py   = "C:\Users\msn\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if (-not $Version) {
    $m = Select-String -Path "superdl\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"'
    $Version = $m.Matches[0].Groups[1].Value
}
Write-Host "SuperDL telepítő-build – verzió: $Version"

Write-Host "1/2  PyInstaller onedir build (SuperDL-onedir.spec)…"
& $py -m PyInstaller SuperDL-onedir.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller hiba (kód $LASTEXITCODE)" }
if (-not (Test-Path "dist\SuperDL\SuperDL.exe")) { throw "Hiányzik a dist\SuperDL\SuperDL.exe" }

Write-Host "2/2  Inno Setup telepítő (SuperDL.iss)…"
& $iscc "/DMyAppVersion=$Version" SuperDL.iss
if ($LASTEXITCODE -ne 0) { throw "ISCC hiba (kód $LASTEXITCODE)" }

$out = "installer\SuperDL-Setup-$Version.exe"
if (Test-Path $out) {
    $mb = [math]::Round((Get-Item $out).Length/1MB,1)
    Write-Host "KÉSZ: $out  ($mb MB)"
} else {
    throw "Nem jött létre a telepítő: $out"
}
