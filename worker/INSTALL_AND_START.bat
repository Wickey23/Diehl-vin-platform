@echo off
setlocal
cd /d %~dp0
title Diehl VIN Initializer

echo ============================================
echo        Diehl VIN Initializer
echo ============================================
echo.
echo This setup runs once. After it finishes, open the website and press Start.
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo Installing Python 3.12...
  winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo Python installation failed. Install Python 3.12 and run this initializer again.
    pause
    exit /b 1
  )
)

if not exist .venv (
  echo Creating local worker environment...
  py -3.12 -m venv .venv
  if errorlevel 1 py -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo Worker dependencies failed to install.
  pause
  exit /b 1
)

python -m playwright install msedge >nul 2>nul
if errorlevel 1 python -m playwright install chromium

if not exist config.json (
  python configure_workbook.py
  if errorlevel 1 (
    echo No workbook was selected. Setup was cancelled.
    pause
    exit /b 1
  )
)

if not exist browser_profiles mkdir browser_profiles

call INSTALL_AUTOSTART.bat /quiet

start "" wscript.exe "%~dp0START_WORKER_SILENT.vbs"
timeout /t 3 /nobreak >nul

powershell -NoProfile -Command "try { $r=Invoke-RestMethod -UseBasicParsing http://127.0.0.1:8765/health -TimeoutSec 5; if($r.ok){exit 0}else{exit 1} } catch { exit 1 }"
if errorlevel 1 (
  echo.
  echo Setup completed, but the local worker did not answer yet.
  echo Restart Windows or run START_WORKER_SILENT.vbs, then open the website.
  pause
  exit /b 1
)

echo.
echo ============================================
echo             SETUP COMPLETE
echo ============================================
echo The worker will start automatically with Windows.
echo From now on: open the website and press Start.
echo.
start "" "https://diehl-vin-platform.vercel.app/"
timeout /t 4 /nobreak >nul
exit /b 0
