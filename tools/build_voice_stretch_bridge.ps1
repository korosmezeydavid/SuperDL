param(
    [string]$OutputPath = "modules_src/supermedia/supermedia_mod/bin/voice_stretch_bridge.dll",
    [string]$Compiler = "C:/msys64/ucrt64/bin/g++.exe"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$source = Join-Path $PSScriptRoot "voice_stretch_bridge.cpp"
$vendor = Join-Path $PSScriptRoot "voice_stretch_vendor"
if (-not (Test-Path -LiteralPath $Compiler)) {
    throw "MinGW UCRT64 fordító nem található: $Compiler"
}
if (-not (Test-Path -LiteralPath (Join-Path $vendor "signalsmith-stretch.h"))) {
    throw "Signalsmith Stretch fejléc hiányzik."
}
$target = if ([IO.Path]::IsPathRooted($OutputPath)) {
    [IO.Path]::GetFullPath($OutputPath)
} else {
    [IO.Path]::GetFullPath((Join-Path $root $OutputPath))
}
$parent = Split-Path -Parent $target
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$env:PATH = "$(Split-Path -Parent $Compiler);$env:PATH"
& $Compiler -std=c++17 -O3 -shared -static -static-libgcc -static-libstdc++ `
    -I $vendor -o $target $source
if ($LASTEXITCODE -ne 0) {
    throw "A voice_stretch_bridge.dll fordítása sikertelen (kód: $LASTEXITCODE)."
}
Write-Output "Elkészült: $target"
