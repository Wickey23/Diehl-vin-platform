@echo off
setlocal
cd /d %~dp0
where py >nul 2>nul
if errorlevel 1 (
  echo Python is required. Installing Python 3.12...
  winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
)
if not exist .venv py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install msedge >nul 2>nul
if errorlevel 1 python -m playwright install chromium
if not exist worker.env python configure_workbook.py
if errorlevel 1 pause & exit /b 1
if not exist browser_profiles mkdir browser_profiles
cls
echo Diehl VIN Worker - outbound Vercel mode
echo ==========================================
echo No Cloudflare. No inbound port. No Outlook.
echo Keep this window running, or use INSTALL_AUTOSTART.bat.
echo.
python outbound_worker.py
pause
