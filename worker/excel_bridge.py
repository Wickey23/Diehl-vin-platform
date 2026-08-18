from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def norm_path(value: str | Path) -> str:
    try:
        return os.path.normcase(os.path.abspath(str(value))).rstrip('\\/')
    except Exception:
        return str(value).lower().rstrip('\\/')


def collect_open_workbook(pythoncom: Any, win32com: Any, destination: Path):
    """Find the shared workbook across all Excel instances.

    OneDrive-backed workbooks may report an https SharePoint FullName while the
    worker knows the local synced path. Exact local-path matches win; otherwise
    one unique open workbook with the same filename is accepted.
    """
    destination = destination.resolve()
    exact = []
    same_name = []
    seen = set()

    def inspect_workbook(wb):
        try:
            name = str(wb.Name or '')
            full = str(wb.FullName or '')
        except Exception:
            return
        key = (name, full)
        if key in seen:
            return
        seen.add(key)
        if full and norm_path(full) == norm_path(destination):
            exact.append(wb)
        elif name.lower() == destination.name.lower():
            same_name.append(wb)

    def inspect_app(app):
        try:
            count = int(app.Workbooks.Count)
        except Exception:
            return
        for i in range(1, count + 1):
            try:
                inspect_workbook(app.Workbooks.Item(i))
            except Exception:
                continue

    try:
        inspect_app(win32com.client.GetActiveObject('Excel.Application'))
    except Exception:
        pass

    try:
        rot = pythoncom.GetRunningObjectTable()
        enum = rot.EnumRunning()
        bind = pythoncom.CreateBindCtx(0)
        while True:
            monikers = enum.Next(1)
            if not monikers:
                break
            moniker = monikers[0]
            try:
                display = moniker.GetDisplayName(bind, None)
            except Exception:
                display = ''
            if 'excel' not in display.lower() and destination.name.lower() not in display.lower():
                continue
            try:
                obj = win32com.client.Dispatch(rot.GetObject(moniker))
            except Exception:
                continue
            try:
                if hasattr(obj, 'Workbooks'):
                    inspect_app(obj)
                elif hasattr(obj, 'Application') and hasattr(obj, 'FullName'):
                    inspect_workbook(obj)
            except Exception:
                continue
    except Exception:
        pass

    if exact:
        return exact[0]

    unique = []
    keys = set()
    for wb in same_name:
        try:
            key = (str(wb.Name), str(wb.FullName))
        except Exception:
            continue
        if key not in keys:
            keys.add(key)
            unique.append(wb)
    return unique[0] if len(unique) == 1 else None
