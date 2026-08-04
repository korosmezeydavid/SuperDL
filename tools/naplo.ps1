# SUPERDL — EGYSEGES NAPLOZO
#
# Minden SDL_ cimket egyszerre figyel, es fajlba menti.
# A "nagytakaritas" hibakereses minden koreben ez fut a hatterben.
#
# Hasznalat:
#   .\tools\naplo.ps1                 -> naplo indul, a fajl: naplo_<idopont>.txt
#   .\tools\naplo.ps1 -Clear          -> elobb torli a regi naplot a telefonon

param([switch]$Clear)

$adb = "C:\Users\msn\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$serial = "3116TF1010002416"

# Minden SuperDL naplocimke egy helyen
$tags = @(
    "SDL_IMAP", "SDL_SMS", "SDL_CALL", "SDL_ALARM", "SDL_CASH",
    "SDL_CALENDAR", "SDL_PINASSIST", "SDL_SCREENREADER", "SDL_CURTAIN",
    "SDL_KEYBOARD", "SDL_BRAILLE", "SDL_APP", "SDL_RADIO", "SDL_GPS",
    "SuperDL.Portal", "AndroidRuntime"
)
$filter = ($tags | ForEach-Object { "$($_):V" }) -join " "

if ($Clear) {
    & $adb -s $serial logcat -c
    Write-Host "Regi naplo torolve a telefonon."
}

$stamp = Get-Date -Format "MMdd_HHmm"
$out = "naplo_$stamp.txt"
Write-Host "Naplozas indul -> $out"
Write-Host "Leallitas: Ctrl+C"

& $adb -s $serial logcat -v time $filter *:S | Tee-Object -FilePath $out
