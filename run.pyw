#!python3
# -*- coding: utf-8 -*-
"""pc-remote entry point when running from source.

The shebang on the first line is mandatory. Windows opens .pyw through
pyw.exe, which picks the default Python — and the dependencies may well
be installed in a different one. Without the shebang the remote fails on
import silently: pythonw has neither a console nor stderr, so there would
be nowhere for the error to appear.

The autostart task also calls the interpreter by full path, so the
protection is doubled.
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _panic(text):
    """Last resort: if even logging failed to start, drop a file next to us.
    A silent crash is the only truly nasty failure in this project."""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "CRASH.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        pass


def main():
    from app import config
    from app.logging_setup import setup

    log = setup(config.load()["log_level"])
    try:
        from app.server import main as serve
        return serve()
    except Exception:
        log.critical("CRASH ON STARTUP:\n%s", traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        _panic(traceback.format_exc())
        raise
