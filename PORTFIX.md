Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object {
    $targetPid = $_.OwningProcess
    $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
    Write-Host "Stopping PID=$targetPid Process=$($proc.ProcessName)"
    Stop-Process -Id $targetPid -Force
  }