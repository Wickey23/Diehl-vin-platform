from __future__ import annotations

import os
import re
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

RUN_EXPORT_FOLDER = 'Run Exports'


def _safe_piece(value: str) -> str:
    value = re.sub(r'[^A-Za-z0-9._-]+', '_', str(value or '').strip())
    return value.strip('._-') or 'UNKNOWN'


def run_export_dir(workbook_path: str | Path) -> Path:
    workbook = Path(workbook_path).expanduser()
    folder = workbook.parent / RUN_EXPORT_FOLDER / workbook.stem
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_dtna_run(df: pd.DataFrame, workbook_path: str | Path, run_time: str | None = None) -> Path:
    stamp = run_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        parsed = datetime.strptime(stamp, '%Y-%m-%d %H:%M:%S')
    except Exception:
        parsed = datetime.now()

    computer = _safe_piece(os.environ.get('COMPUTERNAME') or socket.gethostname())
    filename = f'DTNA_RUN_{parsed:%Y%m%d_%H%M%S}_{computer}.xlsx'
    path = run_export_dir(workbook_path) / filename

    export = df.copy()
    if 'lastChangeTime' not in export.columns:
        export['lastChangeTime'] = stamp
    else:
        export['lastChangeTime'] = stamp

    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        export.to_excel(writer, index=False, sheet_name='DTNA')
        meta = pd.DataFrame([
            {'Field': 'Run Type', 'Value': 'DTNA'},
            {'Field': 'Run Time', 'Value': stamp},
            {'Field': 'Computer', 'Value': os.environ.get('COMPUTERNAME') or socket.gethostname()},
            {'Field': 'Source Workbook', 'Value': str(Path(workbook_path))},
            {'Field': 'Row Count', 'Value': len(export)},
        ])
        meta.to_excel(writer, index=False, sheet_name='Run Info')

    return path


def list_runs(workbook_path: str | Path) -> list[dict[str, Any]]:
    folder = run_export_dir(workbook_path)
    items: list[dict[str, Any]] = []
    for path in folder.glob('DTNA_RUN_*.xlsx'):
        try:
            stat = path.stat()
        except OSError:
            continue
        items.append({
            'id': path.name,
            'type': 'DTNA',
            'filename': path.name,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'path': str(path),
        })
    items.sort(key=lambda item: item['modified'], reverse=True)
    return items


def resolve_run(workbook_path: str | Path, filename: str) -> Path:
    name = Path(filename).name
    if name != filename or not name.startswith('DTNA_RUN_') or not name.lower().endswith('.xlsx'):
        raise ValueError('Invalid run export filename.')
    folder = run_export_dir(workbook_path).resolve()
    path = (folder / name).resolve()
    if path.parent != folder:
        raise ValueError('Invalid run export path.')
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(name)
    return path
