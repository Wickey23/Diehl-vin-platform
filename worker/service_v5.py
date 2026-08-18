from __future__ import annotations

"""Diehl VIN worker v5.5 integration layer.

The existing service_v4 module retains the proven batch queue, Excel upsert,
verification, retry, and API behavior. This layer changes one important rule:
VIN In-Service jobs never use an existing Excel row as a substitute for a live
OWL lookup. Every submitted VIN is sent through owl_lookup.py first, and the
returned OWL result is then upserted/verified by the existing Excel writer.
"""

import subprocess
from pathlib import Path

import uvicorn
from fastapi import HTTPException

import service_v4 as base

base.VERSION = '5.5'
ROOT = Path(__file__).resolve().parent
OWL_LOGIN = ROOT / 'owl_login.py'


def force_live_owl_lookup(_wanted: set[str]):
    # Returning an empty pre-read makes the existing scheduler classify every
    # submitted VIN as needing a live lookup. run_lookup() then invokes
    # vin_lookup.py -> owl_lookup.py. Excel remains the mandatory destination,
    # not the source of truth for whether OWL should be queried.
    return {}


base.read_master = force_live_owl_lookup


@base.app.get('/owl/status')
def owl_status():
    return {
        'ready': OWL_LOGIN.exists() and (ROOT / 'owl_lookup.py').exists(),
        'source': 'OWL',
        'message': 'VIN In-Service uses live OWL lookups.',
    }


@base.app.post('/owl/open')
def owl_open():
    if not OWL_LOGIN.exists():
        raise HTTPException(500, 'OWL login launcher is not installed. Download the current worker package.')
    py = ROOT / '.venv' / 'Scripts' / 'python.exe'
    if not py.exists():
        raise HTTPException(500, 'Local Python environment is not ready.')
    flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
    subprocess.Popen([str(py), str(OWL_LOGIN)], cwd=str(ROOT), creationflags=flags)
    return {'ok': True, 'message': 'OWL login/browser opened locally.'}


if __name__ == '__main__':
    uvicorn.run(base.app, host='127.0.0.1', port=base.PORT, log_level='warning')
