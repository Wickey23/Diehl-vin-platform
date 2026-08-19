from __future__ import annotations

from pathlib import Path

import DiehlInitializer as base

base.EXPECTED_WORKER_VERSION = '5.13'
base.SERVICE = Path(__file__).resolve().parent / 'service_v6.py'


if __name__ == '__main__':
    try:
        base.main()
    except SystemExit:
        raise
    except Exception as exc:
        print('\nERROR:', exc)
        base.show_error(str(exc))
        raise SystemExit(1)
