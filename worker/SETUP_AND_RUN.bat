@echo off
cd /d %~dp0
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
if not exist worker.env copy worker.env.example worker.env
python diehl_worker.py
pause
