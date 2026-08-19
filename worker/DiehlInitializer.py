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
from tkinter import messagebox

from shared_workbook import find_shared_workbook, load_cached_path, WORKBOOK_NAME

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'
CONFIG = ROOT / 'config.json'
REQUIREMENTS = ROOT / 'requirements.txt'
SITE = 'https://diehl-vin-platform.vercel.app'
WORKER_PING = 'http://127.0.0.1:8765/ping'
DATABASE_PING = 'http://127.0.0.1:8766/ping'
LOG_DIR = ROOT / 'logs'
WORKER_LOG = LOG_DIR / 'worker.log'
DATABASE_LOG = LOG_DIR / 'database.log'
SERVICE = ROOT / 'service_v5.py'
DATABASE_SERVICE = ROOT / 'database_service.py'
EXPECTED_WORKER_VERSION = '5.12'


def venv_python() -> Path:
    return VENV / 'Scripts' / 'python.exe'


def run(args: list[str], label: str) -> None:
    print(f'      {label}...')
    result = subprocess.run(args, cwd=str(ROOT))
    if result.returncode != 0:
        raise RuntimeError(f'{label} failed with exit code {result.returncode}.')


def requirements_hash() -> str:
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest() if REQUIREMENTS.exists() else ''


def import_check(py: Path) -> bool:
    code = (
        'import fastapi, uvicorn, openpyxl, psutil; '
        'import pythoncom; '
        'import win32com.client; '
        'import playwright.sync_api; '
        'print("dependency-check-ok")'
    )
    result = subprocess.run(
        [str(py), '-c', code], cwd=str(ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True,
    )
    if result.returncode == 0:
        return True
    print('      Dependency verification failed:')
    for line in (result.stdout or '').splitlines()[-8:]:
        print(f'        {line}')
    return False


def repair_pywin32(py: Path) -> None:
    print('      Repairing Windows Excel integration (pywin32)...')
    run([str(py), '-m', 'pip', 'install', '--upgrade', '--force-reinstall', '--no-cache-dir', 'pywin32>=306'], 'Reinstalling pywin32')
    post = VENV / 'Scripts' / 'pywin32_postinstall.py'
    if post.exists():
        result = subprocess.run([str(py), str(post), '-install'], cwd=str(ROOT), check=False)
        if result.returncode != 0:
            print('      pywin32 post-install returned a warning; verifying imports directly...')
    if not import_check(py):
        raise RuntimeError('Windows Excel integration could not be initialized. pywin32 was reinstalled, but pythoncom/win32com still cannot load.')


def ensure_environment() -> None:
    print('[3/5] Preparing local Python environment...')
    py = venv_python()
    if not py.exists():
        run([sys.executable, '-m', 'venv', str(VENV)], 'Creating local Python environment')
    if not py.exists():
        raise RuntimeError('The local Python environment was not created correctly.')

    marker = VENV / '.diehl_requirements_hash'
    expected = requirements_hash()
    current = marker.read_text(encoding='utf-8').strip() if marker.exists() else ''

    if current != expected:
        run([str(py), '-m', 'pip', 'install', '--upgrade', '-r', str(REQUIREMENTS)], 'Installing/updating required packages')
    else:
        print('      Requirements marker is current. Verifying installed modules...')

    if not import_check(py):
        print('      Installed environment is incomplete. Repairing dependencies...')
        run([str(py), '-m', 'pip', 'install', '--upgrade', '--force-reinstall', '--no-cache-dir', '-r', str(REQUIREMENTS)], 'Repairing required packages')

    if not import_check(py):
        repair_pywin32(py)

    marker.write_text(expected, encoding='utf-8')
    print('      Environment verified.')


def save_config(workbook: Path) -> None:
    py = venv_python()
    CONFIG.write_text(json.dumps({
        'masterWorkbook': str(workbook),
        'workbookName': WORKBOOK_NAME,
        'workbookMode': 'shared-onedrive',
        'vinLookupCommand': f'"{py}" "{ROOT / "vin_lookup.py"}"',
        'port': 8765,
        'databasePort': 8766,
        'vinInServiceSource': 'OWL',
    }, indent=2), encoding='utf-8')


def resolve_shared_workbook() -> Path:
    cached = load_cached_path(CONFIG)
    print('[4/5] Finding shared OneDrive workbook...')
    print(f'      Runtime Python: {sys.executable}')
    print(f'      Locating shared workbook: {WORKBOOK_NAME}')
    workbook = find_shared_workbook(cached)
    print(f'      Found: {workbook}')
    save_config(workbook)
    print('      Shared workbook bound to this worker.')
    print('      VIN In-Service source: OWL exact-field mapper.')
    print('      DTNA Sales Order/AUTO VIN remains a separate workflow.')
    return workbook


def ping(url: str, product: str, timeout: float = 1.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8', errors='replace'))
        if data.get('ok') and data.get('product') == product:
            return data
    except Exception:
        pass
    return None


def spawn_background(script: Path, log_path: Path, label: str) -> subprocess.Popen:
    if not script.exists():
        raise RuntimeError(f'{script.name} is missing. Download a fresh Local Worker package.')
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handle = log_path.open('a', encoding='utf-8', buffering=1)
    handle.write(f'\n[{time.strftime("%Y-%m-%d %H:%M:%S")}] Starting {label}\n')
    proc = subprocess.Popen(
        [str(venv_python()), str(script)], cwd=str(ROOT),
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        stdout=handle, stderr=subprocess.STDOUT,
    )
    proc._diehl_log_handle = handle  # type: ignore[attr-defined]
    return proc


def wait_ready(proc: subprocess.Popen, url: str, product: str, log_path: Path, timeout_seconds: int = 15) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            try:
                proc._diehl_log_handle.close()  # type: ignore[attr-defined]
            except Exception:
                pass
            raise RuntimeError(f'{product} exited during startup with code {proc.returncode}. See {log_path}.')
        info = ping(url, product, .5)
        if info:
            try:
                proc._diehl_log_handle.close()  # type: ignore[attr-defined]
            except Exception:
                pass
            return info
        time.sleep(.15)
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc._diehl_log_handle.close()  # type: ignore[attr-defined]
    except Exception:
        pass
    raise RuntimeError(f'{product} did not become ready. See {log_path}.')


def start_services() -> None:
    existing = ping(WORKER_PING, 'DiehlVINWorker', .5)
    if existing:
        version = str(existing.get('version') or '')
        if version != EXPECTED_WORKER_VERSION:
            raise RuntimeError(
                f'An older Diehl worker (v{version or "unknown"}) is already running on port 8765. '
                'Use Stop All Running, then start this version.'
            )
        print(f'      Main worker already running: v{EXPECTED_WORKER_VERSION}.')
    else:
        proc = spawn_background(SERVICE, WORKER_LOG, f'Diehl VIN Worker v{EXPECTED_WORKER_VERSION}')
        info = wait_ready(proc, WORKER_PING, 'DiehlVINWorker', WORKER_LOG)
        if str(info.get('version') or '') != EXPECTED_WORKER_VERSION:
            raise RuntimeError(f'Unexpected worker version started: {info.get("version")}')
        print('      Local worker connected on 127.0.0.1:8765.')

    if ping(DATABASE_PING, 'DiehlVINDatabase', .5):
        print('      Database viewer already running.')
    else:
        proc = spawn_background(DATABASE_SERVICE, DATABASE_LOG, 'Diehl VIN Database Viewer')
        wait_ready(proc, DATABASE_PING, 'DiehlVINDatabase', DATABASE_LOG)
        print('      Database viewer connected on 127.0.0.1:8766.')


def show_error(message: str) -> None:
    try:
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
        messagebox.showerror('Diehl VIN', message)
        root.destroy()
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--inside-venv', action='store_true')
    args, _ = parser.parse_known_args()

    if os.name != 'nt':
        raise RuntimeError('Diehl VIN local worker is for Windows.')

    if not args.inside_venv:
        ensure_environment()
        py = venv_python()
        print('      Switching initialization to verified venv Python...')
        print(f'      Venv Python: {py}')
        result = subprocess.run([str(py), str(Path(__file__).resolve()), '--inside-venv'], cwd=str(ROOT))
        raise SystemExit(result.returncode)

    current = Path(sys.executable).resolve()
    expected = venv_python().resolve()
    if os.path.normcase(str(current)) != os.path.normcase(str(expected)):
        raise RuntimeError(f'Initializer is using the wrong Python runtime: {current}. Expected: {expected}')

    if not import_check(current):
        raise RuntimeError('Verified venv dependencies are no longer available.')

    resolve_shared_workbook()
    print('      Starting local worker services...')
    start_services()
    webbrowser.open(SITE)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print('\nERROR:', exc)
        show_error(str(exc))
        raise SystemExit(1)
