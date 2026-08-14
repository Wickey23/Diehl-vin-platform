from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'
CONFIG = ROOT / 'config.json'
SITE = 'https://diehl-vin-platform.vercel.app'
HEALTH = 'http://127.0.0.1:8765/health'


def venv_python() -> Path:
    return VENV / 'Scripts' / 'python.exe'


def run_visible(args: list[str], title: str) -> None:
    print('\n' + '=' * 72)
    print(title)
    print('=' * 72)
    print(' '.join(str(x) for x in args))
    result = subprocess.run(args, cwd=str(ROOT))
    if result.returncode != 0:
        raise RuntimeError(f'{title} failed with exit code {result.returncode}.')


def worker_is_healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=2) as response:
            if response.status != 200:
                return False
            data = json.loads(response.read().decode('utf-8', errors='replace'))
            return bool(data.get('ok'))
    except Exception:
        return False


def port_is_busy(port: int = 8765) -> bool:
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.7):
            return True
    except Exception:
        return False


def choose_workbook() -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    messagebox.showinfo(
        'Diehl VIN Initializer',
        'Choose the EXISTING Excel workbook this computer should use.\n\n'
        'This is only required on first setup or when you choose to change the workbook.'
    )
    path = filedialog.askopenfilename(
        title='Choose existing VIN master workbook',
        filetypes=[('Excel workbooks', '*.xlsx *.xlsm'), ('All files', '*.*')]
    )
    root.destroy()
    if not path:
        raise RuntimeError('No workbook was selected.')
    return path


def read_config() -> dict:
    if not CONFIG.exists():
        return {}
    try:
        return json.loads(CONFIG.read_text(encoding='utf-8'))
    except Exception:
        return {}


def configured_workbook() -> str:
    path = str(read_config().get('masterWorkbook') or '').strip()
    return path if path and Path(path).exists() else ''


def configure(workbook: str) -> None:
    py = venv_python()
    lookup = f'"{py}" "{ROOT / "vin_lookup.py"}"'
    CONFIG.write_text(json.dumps({
        'masterWorkbook': workbook,
        'vinLookupCommand': lookup,
        'port': 8765,
    }, indent=2), encoding='utf-8')


def ensure_environment() -> None:
    if not VENV.exists():
        run_visible([sys.executable, '-m', 'venv', str(VENV)], 'Creating local Python environment')

    py = venv_python()
    if not py.exists():
        raise RuntimeError('The local Python environment was not created correctly.')

    marker = VENV / '.diehl_requirements_ready'
    requirements = ROOT / 'requirements.txt'
    needs_install = not marker.exists()
    if marker.exists() and requirements.exists():
        needs_install = marker.stat().st_mtime < requirements.stat().st_mtime

    if needs_install:
        run_visible([str(py), '-m', 'pip', 'install', '--upgrade', 'pip'], 'Updating pip')
        run_visible([str(py), '-m', 'pip', 'install', '-r', str(requirements)], 'Installing required Python packages')
        marker.write_text(datetime_stamp(), encoding='utf-8')


def datetime_stamp() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S')


def start_worker() -> None:
    if worker_is_healthy():
        print('Diehl VIN worker is already running.')
        return

    if port_is_busy():
        raise RuntimeError(
            'Port 8765 is already being used by another program.\n\n'
            'Close the old program using port 8765, then double-click START DIEHL VIN again.'
        )

    py = venv_python()
    flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
    subprocess.Popen([str(py), str(ROOT / 'server.py')], cwd=str(ROOT), creationflags=flags)

    for _ in range(30):
        if worker_is_healthy():
            print('Diehl VIN worker is ready on 127.0.0.1:8765.')
            return
        time.sleep(.5)
    raise RuntimeError('The local worker did not become ready within 15 seconds.')


def show_ready(workbook: str, first_setup: bool) -> None:
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    messagebox.showinfo(
        'Diehl VIN is ready',
        ('Setup complete.\n\n' if first_setup else 'Worker ready.\n\n') +
        f'Workbook:\n{workbook}\n\n'
        'The website is opening now. From there, use DTNA or VIN In-Service and press Start.'
    )
    root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--quick-start', action='store_true')
    args, _ = parser.parse_known_args()

    if os.name != 'nt':
        raise RuntimeError('This initializer is for Windows.')

    print('Diehl VIN Local Worker')
    print('One-click visible local setup. No PowerShell, no hidden VBS, no registry changes.')

    first_setup = not VENV.exists() or not configured_workbook()
    ensure_environment()

    workbook = configured_workbook()
    if not workbook:
        workbook = choose_workbook()
        configure(workbook)
    else:
        # Refresh command paths in case the folder was moved after extraction.
        configure(workbook)

    start_worker()
    webbrowser.open(SITE)

    if first_setup or not args.quick_start:
        show_ready(workbook, first_setup)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('\nERROR:', exc)
        try:
            root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
            messagebox.showerror('Diehl VIN Local Worker', str(exc)); root.destroy()
        except Exception:
            pass
        input('\nPress Enter to close...')
        raise
