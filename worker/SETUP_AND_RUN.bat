@echo off
cd /d %~dp0
if not exist worker.env copy worker.env.example worker.env
py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Configure worker.env before first production run.
echo Starting local worker on http://127.0.0.1:8765
python server.py
pause
