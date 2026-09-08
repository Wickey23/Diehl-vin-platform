from __future__ import annotations

from pathlib import Path

import DiehlInitializer as base

base.EXPECTED_WORKER_VERSION = '5.16'
base.SERVICE = Path(__file__).resolve().parent / 'service_v7.py'

# DiehlInitializer.py v5.16 no longer exposes a webbrowser module and already
# avoids opening a second Diehl VIN Platform tab. Keep this wrapper compatible
# with both the current initializer and older packaged initializers.
if hasattr(base, 'webbrowser'):
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
