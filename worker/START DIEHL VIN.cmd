@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "BASE=%LocalAppData%\DiehlVINWorker"
set "INSTALLDIR=%BASE%\v4"
set "RAW=https://raw.githubusercontent.com/Wickey23/Diehl-vin-platform/main/worker"
set "PYVER=3.12.10"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "PYINSTALLER=%TEMP%\diehl-python-%PYVER%-amd64.exe"
set "PY312=%LocalAppData%\Programs\Python