@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SOURCE=%~dp0"
set "INSTALLDIR=%LocalAppData%\DiehlVINWorker"
set "SITE=https://diehl-vin-platform.vercel.app"
set "PYVER=3.12.10"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "PYINSTALLER=%TEMP%\diehl-python-%PYVER%-amd64.exe"
set "PYCANDIDATE=%LocalAppData%\Programs\Python\Python312\python.exe"
set "PROBEFILE=%TEMP%\diehl_vin_probe.json"

title Diehl VIN Local Worker

echo ============================================================
echo  DIEHL VIN - ONE CLICK START
echo ============================================================
echo.

rem Install/update worker source into one permanent per-user folder.
if not exist "%INSTALLDIR%" mkdir "%INSTALLDIR%"
for %%F in (
  "DiehlInitializer.py"
  "server.py"
  "configure_workbook.py"
  "vin_lookup.py"
  "dtna_login_and_sync.py"
  "requirements.txt"
  "README_LOCAL.txt"
  "START DIEHL VIN.cmd"
) do (
  if exist "%SOURCE%%%~F" copy /Y "%SOURCE%%%~F" "%INSTALLDIR%\%%~F" >nul
)

cd /d "%INSTALLDIR%"

rem If port 8765 is active, verify it is OUR worker before stopping it.
rem We intentionally use FastAPI's lightweight openapi endpoint here so Excel/OneDrive
rem can never block launcher detection.
del /q "%PROBEFILE%" >nul 2>nul
curl.exe -fsS --max-time 2 http://127.0.0.1:8765/openapi.json > "%PROBEFILE%" 2>nul
if !errorlevel!==0 (
  findstr /I /C:"Diehl Local VIN Worker" "%PROBEFILE%" >nul 2>nul
  if !errorlevel!==0 (
    echo Existing Diehl worker found. Restarting it with the latest local files...
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:"127.0.0.1:8765 .*LISTENING"') do (
      taskkill /PID %%P /F >nul 2>nul
    )
    for /L %%W in (1,1,20) do (
      netstat -ano | findstr /R /C:"127.0.0.1:8765 .*LISTENING" >nul 2>nul
      if errorlevel 1 goto worker_stopped
      timeout /t 1 /nobreak >nul
    )
    echo ERROR: The previous Diehl worker did not close cleanly.
    echo Close this window, restart Windows once, then press START DIEHL VIN again.
    pause
    exit /b 1
  ) else (
    echo ERROR: Port 8765 belongs to another local program.
    echo The launcher will not terminate an unknown process.
    pause
    exit /b 1
  )
)

:worker_stopped

rem Validate the permanent venv WITHOUT executing its python.exe.
rem Running python.exe was the old bug: Windows could lock its DLLs while the worker
rem was alive, causing a false "unsupported Python" result and a partial deletion.
set "VENV_OK="
if exist ".venv\Scripts\python.exe" if exist ".venv\pyvenv.cfg" (
  findstr /I /C:"version = 3.12" /C:"version = 3.11" ".venv\pyvenv.cfg" >nul 2>nul
  if !errorlevel!==0 set "VENV_OK=yes"
)

if /I "!VENV_OK!"=="yes" (
  echo Existing Diehl Python environment found. Reusing it.
  ".venv\Scripts\python.exe" DiehlInitializer.py --quick-start
  exit /b !errorlevel!
)

rem Missing pyvenv.cfg or missing python.exe means a prior interrupted delete left
rem a corrupt environment. It is safe to remove now because the Diehl worker above
rem has already been stopped.
if exist ".venv" (
  echo Repairing incomplete local Python environment...
  rmdir /s /q ".venv" 2>nul
  if exist ".venv" (
    echo ERROR: Windows still has files locked inside the old Diehl environment.
    echo Restart Windows once, then press START DIEHL VIN again.
    pause
    exit /b 1
  )
)

echo First-time environment setup on this PC.
echo.

rem Find a compatible existing Python first.
set "PYEXE="
where py >nul 2>nul
if !errorlevel!==0 (
  for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
  if not defined PYEXE for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE (
  if exist "%PYCANDIDATE%" set "PYEXE=%PYCANDIDATE%"
)
if not defined PYEXE (
  where python >nul 2>nul
  if !errorlevel!==0 (
    for /f "delims=" %%P in ('python -c "import sys; print(sys.executable if sys.version_info[:2] in [(3,11),(3,12)] else '')" 2^>nul') do set "PYEXE=%%P"
  )
)

rem No compatible Python: install the official Python.org build once for this user.
if not defined PYEXE (
  echo Python 3.11/3.12 was not found.
  echo Downloading official Python %PYVER% 64-bit...
  del /q "%PYINSTALLER%" >nul 2>nul
  curl.exe -fL --retry 2 --connect-timeout 20 -o "%PYINSTALLER%" "%PYURL%"
  if errorlevel 1 (
    echo ERROR: Python could not be downloaded.
    echo Check the network connection and try again.
    pause
    exit /b 1
  )

  echo Installing Python for this Windows user...
  "%PYINSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_test=0 Include_doc=0 Include_tcltk=1 Include_pip=1 Shortcuts=0
  if errorlevel 1 (
    echo ERROR: Python installation did not complete successfully.
    echo Company endpoint security may require IT approval for the official installer.
    pause
    exit /b 1
  )
  del /q "%PYINSTALLER%" >nul 2>nul
  if exist "%PYCANDIDATE%" set "PYEXE=%PYCANDIDATE%"
)

if not defined PYEXE (
  echo ERROR: Python 3.11/3.12 could not be located after setup.
  pause
  exit /b 1
)

echo Python ready: %PYEXE%
echo Creating the Diehl environment once...
echo.
"%PYEXE%" DiehlInitializer.py
exit /b %errorlevel%
