@echo off
cd /d %~dp0
if not exist worker.env copy worker.env.example worker.env
if not exist .venv py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install msedge >nul 2>nul
if errorlevel 1 python -m playwright install chromium
cls
echo Diehl VIN Worker
echo ===============================
echo Local worker: http://127.0.0.1:8765
echo Keep this window open while using the website.
echo.
python server_ext.py
pause
