@echo off
setlocal EnableExtensions
title Diehl VIN - Stop All Running
color 0C

echo ============================================================
echo  DIEHL VIN - STOP ALL RUNNING
echo ============================================================
echo.
echo Only verified Diehl local services on ports 8765 and 8766 will be stopped.
echo Excel, Edge, Explorer, and unrelated Python programs will not be touched.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports=@(8765,8766); $stopped=0; foreach($port in $ports){ try { $r=Invoke-RestMethod -Uri ('http://127.0.0.1:'+ $port +'/ping') -TimeoutSec 2; $ok=($r.product -eq 'DiehlVINWorker' -or $r.product -eq 'DiehlVINDatabase'); if(-not $ok){ Write-Host ('Port '+$port+' is not a verified Diehl service. Leaving it alone.'); continue }; $c=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if($c){ $p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$c.OwningProcess) -ErrorAction SilentlyContinue; $cmd=[string]$p.CommandLine; $safe=($cmd -match 'service_v7\.py' -or $cmd -match 'service_v5\.py' -or $cmd -match 'service_v4\.py' -or $cmd -match 'database_service\.py' -or $cmd -match 'DiehlVINWorker'); if($safe){ Write-Host ('Stopping verified Diehl service on port '+$port+' (PID '+$c.OwningProcess+')...'); Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop; $stopped++ } else { Write-Host ('Verified Diehl ping found on '+$port+', but process identity was not safe to terminate automatically.'); Write-Host ('Command line: '+$cmd) } } } catch { Write-Host ('No running Diehl service detected on port '+$port+'.') } }; Write-Host ''; Write-Host ($stopped.ToString()+' Diehl service(s) stopped. You can now run START DIEHL VIN.cmd.');"

echo.
pause
exit /b 0
