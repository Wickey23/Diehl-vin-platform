@echo off
setlocal
cd /d %~dp0
set TARGET=%~dp0START_WORKER_SILENT.vbs
set SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Diehl VIN Worker.lnk
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%');$s.TargetPath='wscript.exe';$s.Arguments='""%TARGET%""';$s.WorkingDirectory='%~dp0';$s.Save()"
if /I "%~1"=="/quiet" exit /b 0
echo Diehl VIN Worker will start automatically when you sign in to Windows.
pause
