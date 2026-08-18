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
color 0F
echo ============================================================
echo  DIEHL VIN - SETUP AND START v5.1
echo ============================================================
echo.
echo Permanent runtime:
echo %INSTALLDIR%
echo.
echo This version uses the files already included in the downloaded ZIP.
echo It does not download worker files during startup.
echo.

echo [1/5] Installing packaged Diehl program files...
if not exist "%INSTALLDIR%" mkdir "%INSTALLDIR%"
if errorlevel 1 goto :fail_install

call :copy_file "DiehlInitializer.py"
if errorlevel 1 goto :fail_package
call :copy_file "service_v4.py"
if errorlevel 1 goto :fail_package
call :copy_file "database_service.py"
if errorlevel 1 goto :fail_package
call :copy_file "shared_workbook.py"
if errorlevel 1 goto :fail_package
call :copy_file "workbook_organizer.py"
if errorlevel 1 goto :fail_package
call :copy_file "vin_lookup.py"
if errorlevel 1 goto :fail_package
call :copy_file "dtna_login_and_sync.py"
if errorlevel 1 goto :fail_package
call :copy_file "dtna_runtime.py"
if errorlevel 1 goto :fail_package
call :copy_file "requirements.txt"
if errorlevel 1 goto :fail_package
call :copy_file "README_LOCAL.txt"
if errorlevel 1 goto :fail_package
call :copy_file "STOP ALL DIEHL.cmd"
if errorlevel 1 goto :fail_package

echo       Packaged program files installed.
echo.

echo [2/5] Checking Python 3.12...
set "PYEXE="
if exist "%PY312%" set "PYEXE=%PY312%"
if not defined PYEXE (
  where py >nul 2>nul
  if not errorlevel 1 for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)

if not defined PYEXE (
  echo       Python 3.12 is not installed. Installing official Python %PYVER% once...
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

echo [3/5] Verifying and repairing local environment if needed...
echo [4/5] Finding shared OneDrive workbook and starting worker services...
echo.
cd /d "%INSTALLDIR%"
"%PYEXE%" DiehlInitializer.py
set "RC=%errorlevel%"
if not "%RC%"=="0" goto :fail_initializer

echo.
echo [5/5] SUCCESS
echo       Diehl VIN worker and Database viewer are running.
echo       The website has been opened.
echo.
timeout /t 3 /nobreak >nul
exit /b 0

:copy_file
set "NAME=%~1"
if not exist "%SOURCE%%NAME%" (
  echo ERROR: Missing packaged file: %NAME%
  exit /b 1
)
copy /Y "%SOURCE%%NAME%" "%INSTALLDIR%\%NAME%" >nul
if errorlevel 1 (
  echo ERROR: Could not copy packaged file: %NAME%
  exit /b 1
)
if not exist "%INSTALLDIR%\%NAME%" exit /b 1
echo       %NAME%
exit /b 0

:fail_package
echo.
echo ERROR: The downloaded package is incomplete or was not fully extracted.
echo Extract the entire ZIP to a normal folder, then run START DIEHL VIN.cmd from that folder.
goto :failed

:fail_install
echo.
echo ERROR: Windows would not allow Diehl VIN to use:
echo %INSTALLDIR%
goto :failed

:fail_python_download
echo.
echo ERROR: Python 3.12 could not be downloaded from python.org.
goto :failed

:fail_python_install
echo.
echo ERROR: Python 3.12 installation failed or was blocked.
echo If company endpoint security blocked the official installer, contact IT for approval.
goto :failed

:fail_python_missing
echo.
echo ERROR: Python 3.12 could not be located after setup.
goto :failed

:fail_initializer
echo.
echo ERROR: Diehl VIN initialization failed with code %RC%.
echo Read the error printed above.
echo Main worker log: %INSTALLDIR%\logs\worker.log
echo Database log: %INSTALLDIR%\logs\database.log
echo.
echo If an older Diehl worker is already running, double-click STOP ALL DIEHL.cmd,
echo then run START DIEHL VIN.cmd again.
goto :failed

:failed
echo.
echo ============================================================
echo  SETUP DID NOT COMPLETE
echo ============================================================
echo.
pause
exit /b 1
