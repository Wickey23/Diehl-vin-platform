from __future__ import annotations

import os
import socket
import time
from pathlib import Path

import psutil

CURRENT_PID = os.getpid()
LOCALAPPDATA = Path(os.environ.get('LOCALAPPDATA', ''))
KNOWN_ROOTS = [
    str(LOCALAPPDATA / 'DiehlVINWorker').lower(),
    str(LOCALAPPDATA / 'DiehlDTNAManual').lower(),
]

# Only Python worker/automation scripts are cleanup targets.
# Launchers, CMD/BAT files, Explorer, Edge, and unrelated Python processes are never targets.
PYTHON_MARKERS = (
    'server.py',
    'service_v4.py',
    'vin_lookup.py',
    'dtna_login_and_sync.py',
)


def ancestor_pids() -> set[int]:
    out = {CURRENT_PID}
    try:
        proc = psutil.Process(CURRENT_PID)
        for parent in proc.parents():
            out.add(parent.pid)
    except Exception:
        pass
    return out


PROTECTED_PIDS = ancestor_pids()


def is_known_diehl_python(proc: psutil.Process) -> bool:
    if proc.pid in PROTECTED_PIDS:
        return False
    try:
        name = (proc.name() or '').lower()
        cmd = ' '.join(proc.cmdline()).lower()
        exe = (proc.exe() or '').lower()
        cwd = (proc.cwd() or '').lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False

    # Never terminate non-Python processes from this cleaner.
    if 'python' not in name and 'python' not in exe:
        return False

    text = ' '.join((cmd, exe, cwd))
    marker_match = any(marker in cmd for marker in PYTHON_MARKERS)
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
            if is_known_diehl_python(proc):
                candidates[proc.pid] = proc
        except Exception:
            pass

    # Port 8765 is only cleaned when the listener is also a verified Diehl Python process.
    for pid in pids_listening_on_8765():
        if pid in PROTECTED_PIDS:
            continue
        try:
            proc = psutil.Process(pid)
            if is_known_diehl_python(proc):
                candidates[pid] = proc
        except Exception:
            pass

    if not candidates:
        print('No stale Diehl worker processes found.')
        return 0

    print(f'Cleaning up {len(candidates)} stale Diehl worker process(es)...')
    for proc in candidates.values():
        try:
            print(f'  stopping PID {proc.pid}: {proc.name()}')
            proc.terminate()
        except Exception:
            pass

    _, alive = psutil.wait_procs(list(candidates.values()), timeout=3)
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
