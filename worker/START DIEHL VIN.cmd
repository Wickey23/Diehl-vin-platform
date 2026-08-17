@echo off
setlocal EnableExtensions

set "SOURCE=%~dp0"
set "BASE=%LocalAppData%\DiehlVINWorker"
set "INSTALLDIR=%BASE%\v4"
set "PYVER=3.12.10"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "PYINSTALLER=%TEMP%\diehl-python-%PYVER%-amd64.exe"
set "PY312=%LocalAppData%\Programs\Python\Python312\python.exe"

title Diehl VIN - Setup and Start
echo ============================================================
echo  DIEHL VIN - SETUP AND START v4.3
echo ============================================================
echo.
echo This window stays open until setup succeeds or shows an error.
echo.

echo [1/5] Updating local Diehl program files...
if not exist "%INSTALLDIR%" mkdir "%INSTALLDIR%"
if errorlevel 1 goto :fail_install
for %%F in (
  "DiehlInitializer.py"
  "service_v4.py"
  "cleanup_old_diehl.py"
  "shared_workbook.py"
  "workbook_organizer.py"
  "vin_lookup.py"
  "dtna_login_and_sync.py"
  "requirements.txt"
  "README_LOCAL.txt"
  "START DIEHL VIN.cmd"
) do (
  if not exist "%SOURCE%%%~F" (
    echo ERROR: Package file missing: %%~F
    goto :fail_package
  )
  copy /Y "%SOURCE%%%~F" "%INSTALLDIR%\%%~F" >nul
  if errorlevel 1 goto :fail_install
)
echo       Program files ready.
echo.

echo [2/5] Checking Python 3.12...
set "PYEXE="
if exist "%PY312%" set "PYEXE=%PY312%"
if not defined PYEXE (
  where py >nul 2>nul
  if not errorlevel 1 for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE (
  echo       Installing official Python %PYVER% once for this Windows user...
  del /q "%PYINSTALLER%" >nul 2>nul
  curl.exe -fL --retry 2 --connect-timeout 20 -o "%PYINSTALLER%" "%PYURL%"
  if errorlevel 1 goto :fail_python_download
  "%PYINSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_test=0 Include_doc=0 Include_tcltk=1 Include_pip=1 Shortcuts=0
  if errorlevel 1 goto :fail_python_install
  del /q "%PYINSTALLER%" >nul 2>nul
  if exist "%PY312%" set "PYEXE=%PY312%"
)
if not defined PYEXE goto :fail_python_missing
echo       Python ready: %PYEXE%
echo.

echo [3/5] Initializing Diehl VIN...
echo       Verifying environment, cleaning old Diehl processes,
echo       locating the shared OneDrive workbook, organizing sheets,
echo       and starting the local worker.
echo.
cd /d "%INSTALLDIR%"
"%PYEXE%" DiehlInitializer.py
set "RC=%errorlevel%"
if not "%RC%"=="0" goto :fail_initializer

echo.
echo [5/5] SUCCESS
echo       Diehl VIN is ready. The website has been opened.
echo.
timeout /t 3 /nobreak >nul
exit /b 0

:fail_package
echo.
echo The downloaded worker package is incomplete.
echo Download a fresh package from the Diehl VIN website and extract it first.
goto :failed

:fail_install
echo.
echo Windows would not let Diehl VIN update:
echo %INSTALLDIR%
echo Close any old Diehl setup windows and try again.
goto :failed

:fail_python_download
echo.
echo Python 3.12 could not be downloaded from python.org.
goto :failed

:fail_python_install
echo.
echo Python 3.12 installation failed or was blocked.
echo If company endpoint security blocked the official installer, contact IT for approval.
goto :failed

:fail_python_missing
echo.
echo Python 3.12 could not be located after setup.
goto :failed

:fail_initializer
echo.
echo Diehl VIN initialization failed with code %RC%.
echo Read the ERROR above.
echo Worker log: %INSTALLDIR%\logs\worker.log
goto :failed

:failed
echo.
echo ============================================================
echo  SETUP DID NOT COMPLETE
echo ============================================================
echo.
pause
exit /b 1
