@echo off
setlocal EnableExtensions

set "BASE=%LocalAppData%\DiehlVINWorker"
set "INSTALLDIR=%BASE%\v4"
set "RAW=https://raw.githubusercontent.com/Wickey23/Diehl-vin-platform/main/worker"
set "PYVER=3.12.10"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "PYINSTALLER=%TEMP%\diehl-python-%PYVER%-amd64.exe"
set "PY312=%LocalAppData%\Programs\Python\Python312\python.exe"

title Diehl VIN - Setup and Start
color 0F
echo ============================================================
echo  DIEHL VIN - SETUP AND START v4.4
echo ============================================================
echo.
echo This launcher installs/updates the worker into:
echo %INSTALLDIR%
echo.
echo It does NOT depend on files beside this CMD file.
echo.

echo [1/5] Downloading current Diehl program files...
if not exist "%INSTALLDIR%" mkdir "%INSTALLDIR%"
if errorlevel 1 goto :fail_install

call :download "DiehlInitializer.py"
if errorlevel 1 goto :fail_download
call :download "service_v4.py"
if errorlevel 1 goto :fail_download
call :download "cleanup_old_diehl.py"
if errorlevel 1 goto :fail_download
call :download "shared_workbook.py"
if errorlevel 1 goto :fail_download
call :download "workbook_organizer.py"
if errorlevel 1 goto :fail_download
call :download "vin_lookup.py"
if errorlevel 1 goto :fail_download
call :download "dtna_login_and_sync.py"
if errorlevel 1 goto :fail_download
call :download "requirements.txt"
if errorlevel 1 goto :fail_download
call :download "README_LOCAL.txt"
if errorlevel 1 goto :fail_download

echo       Current program files verified.
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

echo [3/5] Initializing local environment and cleaning old Diehl processes...
echo [4/5] Finding shared OneDrive workbook, organizing sheets, and starting worker...
echo.
cd /d "%INSTALLDIR%"
"%PYEXE%" DiehlInitializer.py
set "RC=%errorlevel%"
if not "%RC%"=="0" goto :fail_initializer

echo.
echo [5/5] SUCCESS
echo       Diehl VIN worker is running and the website has been opened.
echo.
timeout /t 3 /nobreak >nul
exit /b 0

:download
set "FILE=%~1"
set "TMP=%INSTALLDIR%\%~1.download"
del /q "%TMP%" >nul 2>nul
echo       %~1
curl.exe -fsSL --retry 3 --connect-timeout 15 --max-time 90 -o "%TMP%" "%RAW%/%~1?v=%RANDOM%"
if errorlevel 1 exit /b 1
for %%S in ("%TMP%") do if %%~zS LSS 10 exit /b 1
move /Y "%TMP%" "%INSTALLDIR%\%~1" >nul
if errorlevel 1 exit /b 1
if not exist "%INSTALLDIR%\%~1" exit /b 1
exit /b 0

:fail_download
echo.
echo ERROR: Could not download all required Diehl worker files.
echo Check the network connection and try again.
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
