DIEHL VIN LOCAL WORKER v4

SUPPORTED FLOW
1. Download the Local Worker ZIP from https://diehl-vin-platform.vercel.app
2. Extract the ZIP.
3. Double-click START DIEHL VIN.cmd.
4. On the first successful setup, choose the existing Excel workbook this PC should use.
5. The worker starts in the background and opens the website.

PERMANENT LOCAL INSTALL
The launcher keeps the working installation under:
%LocalAppData%\DiehlVINWorker

That folder preserves:
- the Python virtual environment
- workbook selection/config.json
- local worker database
- logs
- local DTNA/browser state used by the worker

Future downloaded ZIPs update the program files in that permanent folder and reuse the environment. Packages are only installed again when requirements actually change or the environment is damaged.

DETECTION
The worker exposes an instant local endpoint:
http://127.0.0.1:8765/ping

The website uses localhost only. Worker-alive detection does not open Excel and does not depend on OneDrive.

EXCEL
The existing workbook remains the source file. Workbook access is serialized. Desktop Excel COM is preferred when available so an already-open workbook can be used and existing formatting/validation is preserved as much as possible.

DTNA
DTNA login/MFA and browser profile remain local to this computer. The website only sends commands to the worker on 127.0.0.1.

AFTER A REBOOT
Double-click START DIEHL VIN.cmd once before using the website. No registry, Startup-folder, VBS, or hidden persistence is installed.

TROUBLESHOOTING
Worker log:
%LocalAppData%\DiehlVINWorker\logs\worker.log

If endpoint security blocks the official Python installer, do not bypass it. IT must approve/allow the installer or provide Python 3.11/3.12 on the PC.
