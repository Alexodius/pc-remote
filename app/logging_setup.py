# -*- coding: utf-8 -*-
"""File logging.

Under pythonw there is no stdout and no stderr, so anything not written to a
file is lost. That is how a failed import once went unnoticed for weeks. The
single handler is therefore a file, and every foreign logger and unhandled
exception hook is routed into it, including waitress threads.
"""

import logging
import os
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler

from . import config

log = logging.getLogger("pc-remote")


def setup(level="INFO"):
    os.makedirs(config.DATA_DIR, exist_ok=True)

    handler = RotatingFileHandler(
        config.LOG_FILE, maxBytes=512 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    log.handlers.clear()
    log.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    log.addHandler(handler)

    for name in ("waitress", "werkzeug", "flask.app"):
        other = logging.getLogger(name)
        other.handlers.clear()
        other.addHandler(handler)
        other.setLevel(logging.WARNING)

    sys.excepthook = _crash
    threading.excepthook = lambda a: _crash(a.exc_type, a.exc_value, a.exc_traceback)
    return log


def _crash(exc_type, exc, tb):
    log.critical("UNHANDLED ERROR:\n%s",
                 "".join(traceback.format_exception(exc_type, exc, tb)))


def tail(lines=200):
    """Last N lines, for the log viewer in the web UI."""
    if not os.path.exists(config.LOG_FILE):
        return []
    try:
        with open(config.LOG_FILE, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()[-lines:]
    except OSError as e:
        return [f"could not read the log: {e}"]
