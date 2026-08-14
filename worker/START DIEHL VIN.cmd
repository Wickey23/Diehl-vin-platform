@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Diehl VIN Local Worker

set "SITE=https://diehl-vin-platform.vercel.app"
set "PYVER=3.12.10"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "PYINSTALLER=%TEMP%\diehl-python-%PYVER%-amd64.exe"
set "PYCANDIDATE=%LocalAppData%\Programs\Python\Python312\python.exe"
set "HEALTHFILE=%TEMP%\diehl_vin_health.json"

echo ============================================================
echo  DIEHL VIN - ONE CLICK START
echo ============================================================
echo.

rem Detect a running Diehl worker. Current v3.2 workers can be reused.
del /q "%HEALTHFILE%" >nul 2>nul
curl.exe -fsS --max-time 2 http://127.0.0.1:8765/health > "%HEALTHFILE%" 2>nul
if %errorlevel%==0 (
  findstr /I /C:"master_workbook" "%HEALTHFILE%" >nul 2>nul
  if !errorlevel!==0 (
    findstr /I /C:"\"version\":\"3.2\"" /C:"\"version\": \"3.2\"" "%HEALTHFILE%" >nul 2>nul
    if !errorlevel!==0 (
      echo Diehl VIN worker v3.2 is already running.
      start "" "%SITE%"
      exit /b 0
    )

    echo An older Diehl VIN worker is running. Updating it automatically...
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:"127.0.0.1:8765 .*LISTENING"') do (
      taskkill /PID %%P /F >nul 2>nul
    )
    timeout /t 2 /nobreak >nul
  ) else (
    echo ERROR: Port 8765 is occupied by another local program.
    echo Close that program and run START DIEHL VIN again.
    pause
    exit /b 1
  )
)

rem Existing environment must be Python 3.11 or 3.12. Old 3.14 venvs are rebuilt.
if exist ".venv\Scripts\python.exe" (
  set "VENV_OK="
  for /f "delims=" %%V in ('".venv\Scripts\python.exe" -c "import sys; print('yes' if sys.version_info[:2] in [(3,11),(3,12)] else 'no')" 2^>nul') do set "VENV_OK=%%V"
  if /I "!VENV_OK!"=="yes" (
    ".venv\Scripts\python.exe" DiehlInitializer.py --quick-start
    exit /b !errorlevel!
  )
  echo Existing local environment uses an unsupported Python version.
  echo Rebuilding it with Python 3.12...
  rmdir /s /q ".venv"
)

echo First-time/update setup detected.
echo.

rem Find a compatible existing Python first.
set "PYEXE="
where py >nul 2>nul
if %errorlevel%==0 (
  for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
  if not defined PYEXE for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE (
  where python >nul 2>nul
  if %errorlevel%==0 (
    for /f "delims=" %%P in ('python -c "import sys; print(sys.executable if sys.version_info[:2] in [(3,11),(3,12)] else '')" 2^>nul') do set "PYEXE=%%P"
  )
)

rem No compatible Python: install the official Python.org build for this user.
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
  if not defined PYEXE (
    for /f "delims=" %%P in ('where /r "%LocalAppData%\Programs\Python" python.exe 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
  )
)

if not defined PYEXE (
  echo ERROR: Python could not be located after setup.
  pause
  exit /b 1
)

echo Python ready: %PYEXE%
echo Completing Diehl VIN setup...
echo.
"%PYEXE%" DiehlInitializer.py
exit /b %errorlevel%
