from __future__ import annotations

import argparse
import hashlib
import json
import os
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
REQUIREMENTS = ROOT / 'requirements.txt'
SITE = 'https://diehl-vin-platform.vercel.app'
PING = 'http://127.0.0.1:8765/ping'
LOG_DIR = ROOT / 'logs'
WORKER_LOG = LOG_DIR / 'worker.log'
SERVICE = ROOT / 'service_v4.py'


def venv_python() -> Path:
    return VENV / 'Scripts' / 'python.exe'


def run(args: list[str], label: str) -> None:
    print(label + '...')
    result = subprocess.run(args, cwd=str(ROOT))
    if result.returncode != 0:
        raise RuntimeError(f'{label} failed with exit code {result.returncode}.')


def requirements_hash() -> str:
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest() if REQUIREMENTS.exists() else ''


def ensure_environment() -> None:
    py = venv_python()
    if not py.exists():
        run([sys.executable, '-m', 'venv', str(VENV)], 'Creating local Python environment')
    if not py.exists():
        raise RuntimeError('The local Python environment was not created correctly.')

    marker = VENV / '.diehl_requirements_hash'
    expected = requirements_hash()
    current = marker.read_text(encoding='utf-8').strip() if marker.exists() else ''
    if current != expected:
        run([str(py), '-m', 'pip', 'install', '-r', str(REQUIREMENTS)], 'Installing/updating required packages')
        marker.write_text(expected, encoding='utf-8')


def read_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.exists() else {}
    except Exception:
        return {}


def configured_workbook() -> str:
    path = str(read_config().get('masterWorkbook') or '').strip()
    return path if path and Path(path).exists() else ''


def choose_workbook() -> str:
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
    path = filedialog.askopenfilename(
        title='Choose existing VIN master workbook',
        filetypes=[('Excel workbooks', '*.xlsx *.xlsm'), ('All files', '*.*')]
    )
    root.destroy()
    if not path:
        raise RuntimeError('No workbook was selected.')
    return path


def save_config(workbook: str) -> None:
    py = venv_python()
    CONFIG.write_text(json.dumps({
        'masterWorkbook': workbook,
        'vinLookupCommand': f'"{py}" "{ROOT / "vin_lookup.py"}"',
        'port': 8765,
    }, indent=2), encoding='utf-8')


def ping_worker(timeout: float = 1.0) -> dict | None:
    try:
        with urllib.request.urlopen(PING, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8', errors='replace'))
        if data.get('ok') and data.get('product') == 'DiehlVINWorker':
            return data
    except Exception:
        pass
    return None


def start_worker() -> None:
    current = ping_worker()
    if current and str(current.get('version')) == '4.0':
        print('Diehl VIN worker v4 is already running.')
        return

    if not SERVICE.exists():
        raise RuntimeError('service_v4.py is missing. Download a fresh Local Worker package.')

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = WORKER_LOG.open('a', encoding='utf-8', buffering=1)
    log_handle.write(f'\n[{time.strftime("%Y-%m-%d %H:%M:%S")}] Starting Diehl VIN Worker v4\n')

    proc = subprocess.Popen(
        [str(venv_python()), str(SERVICE)],
        cwd=str(ROOT),
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )

    deadline = time.time() + 10
    while time.time() < deadline:
        if proc.poll() is not None:
            log_handle.close()
            raise RuntimeError(f'Worker exited during startup with code {proc.returncode}. See {WORKER_LOG}.')
        info = ping_worker(.5)
        if info and str(info.get('version')) == '4.0':
            log_handle.close()
            print('Diehl VIN worker v4 is ready.')
            return
        time.sleep(.25)

    try:
        proc.terminate()
    except Exception:
        pass
    log_handle.close()
    raise RuntimeError(f'Worker did not become ready. See {WORKER_LOG}.')


def show_error(message: str) -> None:
    try:
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
        messagebox.showerror('Diehl VIN', message)
        root.destroy()
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--quick-start', action='store_true')
    parser.parse_known_args()

    if os.name != 'nt':
        raise RuntimeError('Diehl VIN local worker is for Windows.')

    print('Diehl VIN v4')
    ensure_environment()

    workbook = configured_workbook()
    if not workbook:
        workbook = choose_workbook()
    save_config(workbook)

    start_worker()
    webbrowser.open(SITE)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('\nERROR:', exc)
        show_error(str(exc))
        raise
