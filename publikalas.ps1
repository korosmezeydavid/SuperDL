# SuperDL - új verzió publikálása egy lépésben.
# Indítsd a "Publikalas.cmd" fájllal (dupla kattintás).
#
# Mit csinál: bekéri az új verziószámot, frissíti a forrást, megépíti a két
# exét, frissíti a terjesztési ZIP-et, feltölti a GitHubra, és közzéteszi az
# új kiadást a két exével. A GitHub-belépésed már megvan, így nem kér újat.

$ErrorActionPreference = "Stop"
chcp 65001 > $null
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $proj

# ---- beállítások ----------------------------------------------------
$distDir = "C:\superdl1"                       # ide kerül a terjeszthető ZIP
$ghExe = "C:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $ghExe)) { $ghExe = "gh" }
$initFile = Join-Path $proj "superdl\__init__.py"

function Stop-OnError($msg) { Write-Host ""; Write-Host "HIBA: $msg" -ForegroundColor Red; Write-Host "A publikálás megszakadt."; pause; exit 1 }

Write-Host "============================================"
Write-Host "  SuperDL - új verzió publikálása"
Write-Host "============================================"
Write-Host ""

# ---- 1. verziószám -------------------------------------------------
$raw = Get-Content $initFile -Raw
$cur = [regex]::Match($raw, '__version__\s*=\s*"([^"]+)"').Groups[1].Value
Write-Host "Jelenlegi verzió: $cur"
$ver = (Read-Host "Add meg az UJ verziot (pl. 1.5.0)").Trim()
if ($ver -notmatch '^\d+\.\d+\.\d+$') { Stop-OnError "Érvénytelen verzió: '$ver'. Formátum: szám.szám.szám" }
$notes = (Read-Host "Rövid leírás a kiadáshoz (Enter = alapértelmezett)").Trim()
if ([string]::IsNullOrWhiteSpace($notes)) {
    $notes = "SuperDL $ver - akadálymentes, többfunkciós, többszálú letöltő. Készítette: Kőrösmezey Dávid."
}

# ---- 2. verzió beírása a forrásba ----------------------------------
$newRaw = [regex]::Replace($raw, '__version__\s*=\s*"[^"]+"', "__version__ = `"$ver`"")
[System.IO.File]::WriteAllText($initFile, $newRaw, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Verzió frissítve: $ver"

# ---- 3. exe-k építése ----------------------------------------------
Write-Host ""
Write-Host "Az exe-k építése folyamatban (ez pár percet vesz igénybe)..."
Get-Process SuperDL*, aria2c -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 600
foreach ($f in "dist\SuperDL.exe", "dist\SuperDL-cli.exe") {
    if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
}
$common = @("--collect-submodules", "yt_dlp", "--collect-submodules", "feedparser",
    "--hidden-import", "win32com.client", "--hidden-import", "pythoncom",
    "--hidden-import", "pywintypes", "--add-binary", "bin\aria2c.exe;.")
python -m PyInstaller --noconfirm --onefile --windowed --name SuperDL @common superdl_gui.py
python -m PyInstaller --noconfirm --onefile --console --name SuperDL-cli @common superdl.py
if (-not (Test-Path "dist\SuperDL.exe") -or -not (Test-Path "dist\SuperDL-cli.exe")) {
    Stop-OnError "Az exe-k építése nem sikerült. Nézd át a fenti üzeneteket."
}
Write-Host "Exe-k elkészültek." -ForegroundColor Green

# ---- 4. terjesztési ZIP frissítése ---------------------------------
$stage = Join-Path $distDir "SuperDL"
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item "dist\SuperDL.exe" $stage -Force
Copy-Item "dist\SuperDL-cli.exe" $stage -Force
Copy-Item "README.md" $stage -Force
$zip = Join-Path $distDir "SuperDL-$ver.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $stage -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Terjesztési ZIP: $zip" -ForegroundColor Green

# ---- 5. feltöltés a GitHubra ---------------------------------------
Write-Host ""
Write-Host "Feltöltés a GitHubra..."
git add -A
git commit -q -m "SuperDL $ver"
if (-not $?) { Write-Host "(nincs commitolható változás, vagy a commit kimaradt)" }
git push -q
if (-not $?) { Stop-OnError "A 'git push' nem sikerült (internet/belépés?)." }

# ---- 6. GitHub-kiadás közzététele ----------------------------------
Write-Host "A kiadás (v$ver) közzététele a két exével..."
& $ghExe release create "v$ver" "dist\SuperDL.exe" "dist\SuperDL-cli.exe" --title "SuperDL $ver" --notes $notes
if (-not $?) { Stop-OnError "A kiadás közzététele nem sikerült (talán már létezik ez a verzió?)." }

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  KÉSZ! A v$ver verzió közzétéve." -ForegroundColor Green
Write-Host "  A felhasználók gépe magától felajánlja a frissítést." -ForegroundColor Green
Write-Host "  Terjeszthető ZIP: $zip" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
pause
