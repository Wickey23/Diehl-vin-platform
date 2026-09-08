from __future__ import annotations

from pathlib import Path

import DiehlInitializer as base

base.EXPECTED_WORKER_VERSION = '5.16.2'
base.SERVICE = Path(__file__).resolve().parent / 'service_v7.py'

# Keep this wrapper focused on version/service compatibility. The base
# initializer is responsible for opening the Diehl VIN Platform after the
# local services are confirmed ready.


if __name__ == '__main__':
    try:
        base.main()
    except SystemExit:
        raise
    except Exception as exc:
        print('\nERROR:', exc)
        base.show_error(str(exc))
        raise SystemExit(1)
