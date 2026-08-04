# Stop YOLO banknote training and free CPU.
# Resume later: python tools/train_banknote_yolo.py --model yolo11s.pt --resume --export-tflite

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'train_banknote_yolo|finish_banknote|build_huf_banknote' }

if (-not $procs) {
    Write-Host "No banknote training Python process found."
    exit 0
}

foreach ($p in $procs) {
    Write-Host "Stopping PID $($p.ProcessId): $($p.CommandLine.Substring(0, [Math]::Min(120, $p.CommandLine.Length)))..."
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

# Optional: also stop the PowerShell pipeline wrapper if still running
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -match 'train_banknote_yolo|YOLO RETRY|training_precision_run' } |
    ForEach-Object {
        Write-Host "Stopping shell PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Write-Host ""
Write-Host "Training stopped. Weights saved under tools/runs/banknote/huf_detect-2/weights/"
Write-Host "Resume: python tools/train_banknote_yolo.py --model yolo11s.pt --resume --export-tflite"