@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SOURCE=%~dp0"
set "BASE=%LocalAppData%\DiehlVINWorker"
set "INSTALLDIR=%BASE%\v4"
set "SITE=https://diehl-vin-platform.vercel.app"
set "PYVER=3.12.10"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "PYINSTALLER=%TEMP%\diehl-python-%PYVER%-amd64.exe"
set "PY312=%LocalAppData%\Programs\Python\Python312\python.exe"
set "PROBE=%TEMP%\diehl_vin_probe.json"

title Diehl VIN
echo ============================================================
echo  DIEHL VIN - START v4
echo ============================================================
echo.

if not exist "%INSTALLDIR%" mkdir "%INSTALLDIR%"

rem Copy only v4 program files. Never touch the old .venv.
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

if not exist "%INSTALLDIR%\service_v4.py" (
  echo ERROR: This package is incomplete. service_v4.py is missing.
  pause
  exit /b 1
)

rem Stop only a verified Diehl worker already listening on 8765.
del /q "%PROBE%" >nul 2>nul
curl.exe -fsS --max-time 1 http://127.0.0.1:8765/ping > "%PROBE%" 2>nul
if !errorlevel!==0 (
  findstr /I /C:"DiehlVINWorker" "%PROBE%" >nul 2>nul
  if !errorlevel!==0 goto stop_worker
)

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
pause
exit /b 1

:worker_stopped

rem Require Python 3.12 specifically. Do not use Python 3.14 from PATH.
set "PYEXE="
if exist "%PY312%" set "PYEXE=%PY312%"
if not defined PYEXE (
  where py >nul 2>nul
  if !errorlevel!==0 for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)

if not defined PYEXE (
  echo Installing official Python %PYVER% for this Windows user once...
  del /q "%PYINSTALLER%" >nul 2>nul
  curl.exe -fL --retry 2 --connect-timeout 20 -o "%PYINSTALLER%" "%PYURL%"
  if errorlevel 1 (
    echo ERROR: Python 3.12 could not be downloaded.
    pause
    exit /b 1
  )
  "%PYINSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_test=0 Include_doc=0 Include_tcltk=1 Include_pip=1 Shortcuts=0
  if errorlevel 1 (
    echo ERROR: Python 3.12 installation failed or was blocked.
    echo If endpoint security blocked the official installer, contact IT for approval.
    pause
    exit /b 1
  )
  del /q "%PYINSTALLER%" >nul 2>nul
  if exist "%PY312%" set "PYEXE=%PY312%"
)

if not defined PYEXE (
  echo ERROR: Python 3.12 could not be located.
  pause
  exit /b 1
)

echo Python 3.12 ready: %PYEXE%
cd /d "%INSTALLDIR%"
"%PYEXE%" DiehlInitializer.py --quick-start
set "RC=%errorlevel%"
if not "%RC%"=="0" (
  echo.
  echo Diehl VIN setup/start failed. See the error above.
  pause
)
exit /b %RC%
