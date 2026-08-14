@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Diehl VIN Local Worker

set "SITE=https://diehl-vin-platform.vercel.app"
set "PYVER=3.12.10"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "PYINSTALLER=%TEMP%\diehl-python-%PYVER%-amd64.exe"
set "PYCANDIDATE=%LocalAppData%\Programs\Python\Python312\python.exe"

echo ============================================================
echo  DIEHL VIN - ONE CLICK START
echo ============================================================
echo.

rem If the correct worker is already running, just open the site.
curl.exe -fsS --max-time 2 http://127.0.0.1:8765/health > "%TEMP%\diehl_vin_health.json" 2>nul
if %errorlevel%==0 (
  findstr /I /C:"\"ok\":true" /C:"\"ok\": true" "%TEMP%\diehl_vin_health.json" >nul 2>nul
  if %errorlevel%==0 (
    echo Diehl VIN worker is already running.
    start "" "%SITE%"
    exit /b 0
  )
)

rem If this folder is already initialized, use its own Python immediately.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" DiehlInitializer.py --quick-start
  exit /b %errorlevel%
)

echo First-time setup detected.
echo.

rem Find a compatible existing Python first.
set "PYEXE="
where py >nul 2>nul
if %errorlevel%==0 (
  for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE (
  where python >nul 2>nul
  if %errorlevel%==0 (
    for /f "delims=" %%P in ('python -c "import sys; print(sys.executable if sys.version_info[:2] in [(3,11),(3,12)] else '')" 2^>nul') do set "PYEXE=%%P"
  )
)

rem No compatible Python: download the official, signed Python.org installer and install for this user.
if not defined PYEXE (
  echo Python 3.11/3.12 was not found.
  echo Downloading the official Python %PYVER% 64-bit installer from python.org...
  echo.
  del /q "%PYINSTALLER%" >nul 2>nul
  curl.exe -fL --retry 2 --connect-timeout 20 -o "%PYINSTALLER%" "%PYURL%"
  if errorlevel 1 (
    echo.
    echo ERROR: Python could not be downloaded.
    echo Check your internet/company network connection and try again.
    pause
    exit /b 1
  )

  echo Installing Python for this Windows user...
  "%PYINSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_test=0 Include_doc=0 Include_tcltk=1 Include_pip=1 Shortcuts=0
  if errorlevel 1 (
    echo.
    echo ERROR: Python installation did not complete successfully.
    echo Your company security software may have blocked the official installer.
    pause
    exit /b 1
  )
  del /q "%PYINSTALLER%" >nul 2>nul

  if exist "%PYCANDIDATE%" set "PYEXE=%PYCANDIDATE%"
  if not defined PYEXE (
    for /f "delims=" %%P in ('where /r "%LocalAppData%\Programs\Python" python.exe 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
  )
)

if not defined PYEXE (
  echo.
  echo ERROR: Python was installed but could not be located.
  echo Close this window and double-click START DIEHL VIN.cmd again.
  pause
  exit /b 1
)

echo.
echo Python ready: %PYEXE%
echo Completing Diehl VIN setup...
echo.
"%PYEXE%" DiehlInitializer.py
exit /b %errorlevel%
