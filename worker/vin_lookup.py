from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OWL = ROOT / 'owl_lookup_v5.py'
RESULT = Path(os.environ.get('DIEHL_RESULT_FILE', str(ROOT / 'vin-results.json')))
VINS = [x.strip().upper() for x in os.environ.get('DIEHL_VINS', '').splitlines() if x.strip()]


def main() -> int:
    if not VINS:
        RESULT.write_text('{}', encoding='utf-8')
        return 0

    if not OWL.exists():
        raise RuntimeError('Exact live-page OWL VIN In-Service automation is not installed. Download the current worker package.')

    python = ROOT / '.venv' / 'Scripts' / 'python.exe'
    exe = python if python.exists() else Path(sys.executable)

    env = os.environ.copy()
    env['DIEHL_VINS'] = '\n'.join(VINS)
    env['DIEHL_RESULT_FILE'] = str(RESULT)

    completed = subprocess.run([str(exe), str(OWL)], cwd=str(ROOT), env=env, check=False)
    if completed.returncode != 0:
        if RESULT.exists():
            try:
                payload = json.loads(RESULT.read_text(encoding='utf-8'))
                if isinstance(payload, dict) and payload:
                    return completed.returncode
            except Exception:
                pass
        raise RuntimeError('OWL VIN lookup failed. Check the OWL browser window and local OWL log for the exact error.')

    if not RESULT.exists():
        raise RuntimeError('OWL lookup completed without producing a result file.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        RESULT.write_text(json.dumps({'_error': str(exc)}), encoding='utf-8')
        raise
