from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path

import psutil

CURRENT_PID = os.getpid()
CURRENT_PARENT = os.getppid()
LOCALAPPDATA = Path(os.environ.get('LOCALAPPDATA', ''))
KNOWN_ROOTS = [
    str(LOCALAPPDATA / 'DiehlVINWorker').lower(),
    str(LOCALAPPDATA / 'DiehlDTNAManual').lower(),
    str(Path.home() / 'Downloads' / 'Diehl_VIN_Local_Worker').lower(),
    str(Path.home() / 'Downloads' / 'Diehl_VIN_Local_Worker_v4').lower(),
    str(Path.home() / 'Downloads' / 'Diehl_VIN_Local_Worker_v4_1').lower(),
]
KNOWN_MARKERS = (
    'server.py',
    'service_v4.py',
    'diehlinitializer.py',
    'vin_lookup.py',
    'dtna_login_and_sync.py',
    'start diehl vin.cmd',
    'start_worker.cmd',
    'install_and_start.bat',
    'setup_and_run.bat',
    'install_autostart.bat',
)


def is_known_diehl_process(proc: psutil.Process) -> bool:
    if proc.pid in {CURRENT_PID, CURRENT_PARENT}:
        return False
    try:
        cmd = ' '.join(proc.cmdline()).lower()
        exe = (proc.exe() or '').lower()
        cwd = (proc.cwd() or '').lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False

    text = ' '.join((cmd, exe, cwd))
    marker_match = any(marker in text for marker in KNOWN_MARKERS)
    root_match = any(root and root in text for root in KNOWN_ROOTS)
    return marker_match and root_match


def pids_listening_on_8765() -> set[int]:
    out: set[int] = set()
    try:
        for conn in psutil.net_connections(kind='tcp'):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == 8765 and conn.pid:
                out.add(conn.pid)
    except Exception:
        pass
    return out


def cleanup() -> int:
    candidates: dict[int, psutil.Process] = {}

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if is_known_diehl_process(proc):
                candidates[proc.pid] = proc
        except Exception:
            pass

    for pid in pids_listening_on_8765():
        if pid in {CURRENT_PID, CURRENT_PARENT}:
            continue
        try:
            proc = psutil.Process(pid)
            if is_known_diehl_process(proc):
                candidates[pid] = proc
        except Exception:
            pass

    if not candidates:
        print('No stale Diehl processes found.')
        return 0

    print(f'Cleaning up {len(candidates)} stale Diehl process(es)...')
    for proc in candidates.values():
        try:
            print(f'  stopping PID {proc.pid}: {proc.name()}')
            proc.terminate()
        except Exception:
            pass

    gone, alive = psutil.wait_procs(list(candidates.values()), timeout=3)
    for proc in alive:
        try:
            print(f'  force stopping PID {proc.pid}: {proc.name()}')
            proc.kill()
        except Exception:
            pass

    if alive:
        psutil.wait_procs(alive, timeout=2)

    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', 8765), timeout=.2):
                time.sleep(.2)
                continue
        except Exception:
            break

    return 0


if __name__ == '__main__':
    raise SystemExit(cleanup())
