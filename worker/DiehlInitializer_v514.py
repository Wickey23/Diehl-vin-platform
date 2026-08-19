from __future__ import annotations

from pathlib import Path

import DiehlInitializer as base

base.EXPECTED_WORKER_VERSION = '5.14'
base.SERVICE = Path(__file__).resolve().parent / 'service_v7.py'

# The website is already open when employees start/restart the local worker.
# Do not open another Diehl VIN Platform tab on every worker restart.
base.webbrowser.open = lambda *args, **kwargs: False


if __name__ == '__main__':
    try:
        base.main()
    except SystemExit:
        raise
    except Exception as exc:
        print('\nERROR:', exc)
        base.show_error(str(exc))
        raise SystemExit(1)
