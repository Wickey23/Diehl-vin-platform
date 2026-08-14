from __future__ import annotations

import argparse
import json
import os
import socket
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
PORT = 8765
LOG_DIR = ROOT / 'logs'
WORKER_LOG = LOG_DIR / 'worker.log'


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


def port_is_busy(port: int = PORT) -> bool:
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.5):
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
        'port': PORT,
    }, indent=2), encoding='utf-8')


def datetime_stamp() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S')


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


def start_worker() -> None:
    if port_is_busy():
        print('A local service is already listening on port 8765.')
        return

    py = venv_python()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = WORKER_LOG.open('a', encoding='utf-8', buffering=1)
    log_handle.write(f'\n[{datetime_stamp()}] Starting Diehl VIN worker\n')

    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    proc = subprocess.Popen(
        [str(py), str(ROOT / 'server.py')],
        cwd=str(ROOT),
        creationflags=flags,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )

    deadline = time.time() + 8
    while time.time() < deadline:
        if proc.poll() is not None:
            log_handle.flush()
            log_handle.close()
            raise RuntimeError(
                f'The local worker exited during startup with code {proc.returncode}. '
                f'Open {WORKER_LOG} for the exact error.'
            )
        if port_is_busy():
            print('Diehl VIN worker started in the background on 127.0.0.1:8765.')
            # The child process owns the inherited log handle now; closing our copy is safe.
            log_handle.close()
            return
        time.sleep(.25)

    try:
        proc.terminate()
    except Exception:
        pass
    log_handle.flush()
    log_handle.close()
    raise RuntimeError(
        'The local worker did not open port 8765 within 8 seconds. '
        f'Open {WORKER_LOG} for the exact startup error.'
    )


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
    print('One-click visible local setup. The background worker runs without a console window.')

    first_setup = not VENV.exists() or not configured_workbook()
    ensure_environment()

    workbook = configured_workbook()
    if not workbook:
        workbook = choose_workbook()
        configure(workbook)
    else:
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
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            messagebox.showerror('Diehl VIN Local Worker', str(exc))
            root.destroy()
        except Exception:
            pass
        input('\nPress Enter to close...')
        raise
