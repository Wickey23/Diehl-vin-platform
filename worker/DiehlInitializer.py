from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'
CONFIG = ROOT / 'config.json'
SITE = 'https://diehl-vin-platform.vercel.app'


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


def choose_workbook() -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    messagebox.showinfo(
        'Diehl VIN Initializer',
        'Choose the EXISTING Excel workbook this computer should use.\n\n'
        'The worker writes into this same workbook so your existing validation, formulas, tables and formatting remain in place.'
    )
    path = filedialog.askopenfilename(
        title='Choose existing VIN master workbook',
        filetypes=[('Excel workbooks', '*.xlsx *.xlsm'), ('All files', '*.*')]
    )
    root.destroy()
    if not path:
        raise RuntimeError('No workbook was selected.')
    return path


def configure(workbook: str) -> None:
    py = venv_python()
    lookup = f'"{py}" "{ROOT / "vin_lookup.py"}"'
    CONFIG.write_text(json.dumps({
        'masterWorkbook': workbook,
        'vinLookupCommand': lookup,
        'port': 8765,
    }, indent=2), encoding='utf-8')


def start_worker() -> None:
    py = venv_python()
    flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
    subprocess.Popen([str(py), str(ROOT / 'server.py')], cwd=str(ROOT), creationflags=flags)


def main() -> None:
    if os.name != 'nt':
        raise RuntimeError('This initializer is for Windows.')

    print('Diehl VIN Initializer')
    print('Visible local setup - no hidden installer, no PowerShell, no Startup changes.')

    if not VENV.exists():
        run_visible([sys.executable, '-m', 'venv', str(VENV)], 'Creating local Python environment')

    py = venv_python()
    run_visible([str(py), '-m', 'pip', 'install', '--upgrade', 'pip'], 'Updating pip')
    run_visible([str(py), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], 'Installing required Python packages')

    workbook = choose_workbook()
    configure(workbook)

    print('\nStarting the local Diehl worker on 127.0.0.1:8765 ...')
    start_worker()
    time.sleep(2)
    webbrowser.open(SITE)

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    messagebox.showinfo(
        'Diehl VIN is ready',
        f'Workbook:\n{workbook}\n\n'
        'The local worker is now running. The website has been opened.\n\n'
        'From the website, use DTNA or VIN In-Service and press Start.\n'
        'Keep the worker window open while using the site.'
    )
    root.destroy()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('\nERROR:', exc)
        try:
            root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
            messagebox.showerror('Diehl VIN Initializer', str(exc)); root.destroy()
        except Exception:
            pass
        input('\nPress Enter to close...')
        raise
