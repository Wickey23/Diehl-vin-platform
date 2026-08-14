@echo off
setlocal
cd /d "%~dp0"
title Diehl VIN Local Worker

echo ============================================================
echo  DIEHL VIN - LOCAL WORKER
echo ============================================================
echo.

rem If the correct worker is already running, just open the site.
curl.exe -fsS --max-time 2 http://127.0.0.1:8765/health > "%TEMP%\diehl_vin_health.json" 2>nul
if %errorlevel%==0 (
  findstr /I /C:"\"ok\":true" /C:"\"ok\": true" "%TEMP%\diehl_vin_health.json" >nul 2>nul
  if %errorlevel%==0 (
    echo Diehl VIN worker is already running.
    start "" "https://diehl-vin-platform.vercel.app"
    exit /b 0
  )
)

rem First run: locate an installed Python and let the visible initializer do setup.
if not exist ".venv\Scripts\python.exe" (
  echo First-time setup detected.
  echo.
  where py >nul 2>nul
  if %errorlevel%==0 (
    py DiehlInitializer.py
    exit /b %errorlevel%
  )
  where python >nul 2>nul
  if %errorlevel%==0 (
    python DiehlInitializer.py
    exit /b %errorlevel%
  )
  echo Python is not installed or is not available in PATH.
  echo Please install Python 3.11 or 3.12, then double-click this file again.
  echo.
  pause
  exit /b 1
)

rem Existing setup: run the initializer in quick-start mode. It validates
rem configuration, starts the worker only if needed, and opens the website.
".venv\Scripts\python.exe" DiehlInitializer.py --quick-start
exit /b %errorlevel%
