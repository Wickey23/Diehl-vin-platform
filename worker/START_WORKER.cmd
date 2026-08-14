@echo off
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo Diehl VIN has not been initialized yet.
  echo Run: python DiehlInitializer.py
  pause
  exit /b 1
)
.venv\Scripts\python.exe server.py
pause
