@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SOURCE=%~dp0"
set "INSTALLDIR=%LocalAppData%\DiehlVINWorker"
set "SITE=https://diehl-vin-platform.vercel.app"
set "PYVER=3.12.10"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "PYINSTALLER=%TEMP%\diehl-python-%PYVER%-amd64.exe"
set "PYCANDIDATE=%LocalAppData%\Programs\Python\Python312\python.exe"
set "PROBE=%TEMP%\diehl_vin_probe.json"

title Diehl VIN

echo ============================================================
echo  DIEHL VIN - START
echo ============================================================
echo.

if not exist "%INSTALLDIR%" mkdir "%INSTALLDIR%"
cd /d "%INSTALLDIR%"

rem Stop only a verified Diehl worker. Never kill an unknown process.
del /q "%PROBE%" >nul 2>nul
curl.exe -fsS --max-time 1 http://127.0.0.1:8765/ping > "%PROBE%" 2>nul
if !errorlevel!==0 (
  findstr /I /C:"DiehlVINWorker" "%PROBE%" >nul 2>nul
  if !errorlevel!==0 goto stop_worker
)

rem Backward-compatible detection for older Diehl worker versions.
del /q "%PROBE%" >nul 2>nul
curl.exe -fsS --max-time 1 http://127.0.0.1:8765/openapi.json > "%PROBE%" 2>nul
if !errorlevel!==0 (
  findstr /I /C:"Diehl Local VIN Worker" /C:"Diehl VIN Worker" "%PROBE%" >nul 2>nul
  if !errorlevel!==0 goto stop_worker
  echo ERROR: Port 8765 is being used by another local program.
  echo Diehl VIN will not terminate an unknown process.
  pause
  exit /b 1
)
goto worker_stopped

:stop_worker
echo Stopping previous Diehl worker...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:"127.0.0.1:8765 .*LISTENING"') do taskkill /PID %%P /F >nul 2>nul
for /L %%W in (1,1,10) do (
  netstat -ano | findstr /R /C:"127.0.0.1:8765 .*LISTENING" >nul 2>nul
  if errorlevel 1 goto worker_stopped
  timeout /t 1 /nobreak >nul
)
echo ERROR: The previous Diehl worker did not stop.
echo Restart Windows once, then press START DIEHL VIN again.
pause
exit /b 1

:worker_stopped

rem Update program files only after the old worker is stopped.
for %%F in (
  "DiehlInitializer.py"
  "service_v4.py"
  "configure_workbook.py"
  "vin_lookup.py"
  "dtna_login_and_sync.py"
  "requirements.txt"
  "README_LOCAL.txt"
  "START DIEHL VIN.cmd"
) do (
  if exist "%SOURCE%%%~F" copy /Y "%SOURCE%%%~F" "%INSTALLDIR%\%%~F" >nul
)

if not exist "service_v4.py" (
  echo ERROR: This download is incomplete. service_v4.py is missing.
  echo Download a fresh Local Worker ZIP from the Diehl website.
  pause
  exit /b 1
)

rem Locate Python 3.11 or 3.12. The permanent venv is reused if healthy.
set "PYEXE="
if exist ".venv\Scripts\python.exe" if exist ".venv\pyvenv.cfg" (
  findstr /I /C:"version = 3.12" /C:"version = 3.11" ".venv\pyvenv.cfg" >nul 2>nul
  if !errorlevel!==0 set "PYEXE=.venv\Scripts\python.exe"
)

if defined PYEXE goto run_initializer

rem A partial venv is safe to remove now because the worker is stopped.
if exist ".venv" (
  echo Repairing incomplete Diehl environment...
  rmdir /s /q ".venv" >nul 2>nul
  if exist ".venv" (
    echo ERROR: Windows still has the old Diehl environment locked.
    echo Restart Windows once, then press START DIEHL VIN again.
    pause
    exit /b 1
  )
)

where py >nul 2>nul
if !errorlevel!==0 (
  for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
  if not defined PYEXE for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE if exist "%PYCANDIDATE%" set "PYEXE=%PYCANDIDATE%"

if not defined PYEXE (
  echo Python 3.12 is not installed yet. Installing it once for this Windows user...
  del /q "%PYINSTALLER%" >nul 2>nul
  curl.exe -fL --retry 2 --connect-timeout 20 -o "%PYINSTALLER%" "%PYURL%"
  if errorlevel 1 (
    echo ERROR: Python could not be downloaded.
    pause
    exit /b 1
  )
  "%PYINSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_test=0 Include_doc=0 Include_tcltk=1 Include_pip=1 Shortcuts=0
  if errorlevel 1 (
    echo ERROR: Python installation was blocked or failed.
    echo If endpoint security blocked the official Python installer, contact IT for approval.
    pause
    exit /b 1
  )
  del /q "%PYINSTALLER%" >nul 2>nul
  if exist "%PYCANDIDATE%" set "PYEXE=%PYCANDIDATE%"
)

if not defined PYEXE (
  echo ERROR: Python 3.11/3.12 could not be located.
  pause
  exit /b 1
)

:run_initializer
"%PYEXE%" DiehlInitializer.py --quick-start
set "RC=%errorlevel%"
if not "%RC%"=="0" (
  echo.
  echo Diehl VIN setup/start failed. See the message above.
  pause
)
exit /b %RC%
