DIEHL VIN LOCAL WORKER - PLAIN PYTHON VERSION

This package intentionally does NOT use:
- PowerShell
- winget
- hidden VBS startup
- registry changes
- Windows Startup changes
- remote GitHub bootstrap downloads

FIRST RUN
1. Extract the ZIP to a normal folder such as Documents\Diehl VIN Worker.
2. Make sure Python 3.11 or 3.12 is installed.
3. Open Command Prompt in this folder.
4. Run: python DiehlInitializer.py
5. Choose the EXISTING Excel workbook you want to keep using.
6. Keep the worker console window open.
7. The initializer opens https://diehl-vin-platform.vercel.app automatically.
8. On the website, press Start in VIN In-Service or DTNA.

LATER IN THE SAME WINDOWS SESSION
The worker stays running until its console is closed.

AFTER A REBOOT
Run START_WORKER.cmd once, then use the website normally.
This version deliberately does not add itself to Windows Startup because that behavior was being blocked by corporate endpoint security.

EXCEL
The selected workbook remains the source file. VIN writes use desktop Excel COM when available so existing validation, formulas, tables, and formatting are preserved as much as Excel itself permits.

DTNA
DTNA browser/login/MFA remain local to this computer. The persistent browser profile is stored locally.
