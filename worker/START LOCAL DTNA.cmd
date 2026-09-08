@echo off
setlocal EnableExtensions

set "SOURCE=%~dp0"
set "ROOT=%LocalAppData%\DiehlLocalDTNA"
set "VENV=%ROOT%\.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PY312=%LocalAppData%\Programs\Python\Python312\python.exe"

title Diehl Local DTNA Writer
color 0F
echo ============================================================
echo  DIEHL LOCAL DTNA WRITER
echo ============================================================
echo.
echo This local app lets you choose the exact workbook and existing
echo worksheet that DTNA should update.
echo.

if not exist "%ROOT%" mkdir "%ROOT%"
if errorlevel 1 goto :fail

for %%F in (
  "local_dtna_app.py"
  "dtna_runtime.py"
  "dtna_login_and_sync.py"
  "database_cache.py"
  "shared_workbook.py"
  "requirements.txt"
) do (
  if not exist "%SOURCE%%%~F" (
    echo ERROR: Missing %%~F from this package.
    goto :fail
  )
  copy /Y "%SOURCE%%%~F" "%ROOT%\%%~F" >nul
)

if not exist "%PY%" (
  echo Creating isolated localhost Python environment...
  if exist "%PY312%" (
    "%PY312%" -m venv "%VENV%"
  ) else (
    where py >nul 2>nul
    if errorlevel 1 goto :no_python
    py -3.12 -m venv "%VENV%"
  )
  if errorlevel 1 goto :fail
)

echo Checking required packages...
"%PY%" -c "import fastapi,uvicorn,openpyxl,pandas,playwright,pythoncom,win32com.client" >nul 2>nul
if errorlevel 1 (
  echo Installing required packages for localhost DTNA...
  "%PY%" -m pip install --upgrade pip >nul
  "%PY%" -m pip install -r "%ROOT%\requirements.txt"
  if errorlevel 1 goto :fail
)

echo.
echo Starting: http://127.0.0.1:8770
echo Keep this window open while using the localhost DTNA app.
echo.
cd /d "%ROOT%"
"%PY%" local_dtna_app.py
exit /b %errorlevel%

:no_python
echo.
echo ERROR: Python 3.12 is not installed on this computer.
echo Run the normal START DIEHL VIN.cmd once first, then run this file again.
goto :failed

:fail
echo.
echo ERROR: Local DTNA setup did not complete.
:failed
echo.
pause
exit /b 1
