# -*- coding: utf-8 -*-
"""Scheduled shutdown state.

Its own module for two reasons. Waitress serves requests on several threads,
so a plain global would race. And the timer lives in Windows, not here: if the
process restarts, the countdown is still running and must not be forgotten —
otherwise the smart home would show "all quiet" ten seconds before shutdown.
"""

import json
import os
import threading
import time

from . import config

_lock = threading.RLock()
_pending = None  # {"action": str, "label": str, "deadline": float}


def _persist():
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(config.STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"pending": _pending}, fh)
    except OSError:
        pass  # only the countdown is lost on restart, nothing critical


def restore():
    """Pick the countdown back up after a restart, if it is still ahead."""
    global _pending
    with _lock:
        try:
            with open(config.STATE_FILE, encoding="utf-8") as fh:
                p = json.load(fh).get("pending")
            if p and p.get("deadline", 0) > time.time():
                _pending = p
                return int(p["deadline"] - time.time())
        except (OSError, ValueError, KeyError, TypeError):
            pass
        _pending = None
        return 0


def set_pending(action, label, delay):
    global _pending
    with _lock:
        _pending = {"action": action, "label": label, "deadline": time.time() + delay}
        _persist()


def clear():
    global _pending
    with _lock:
        _pending = None
        _persist()


def snapshot():
    """(action, label_key, seconds_left). An expired timer clears itself."""
    global _pending
    with _lock:
        if not _pending:
            return None, None, 0
        left = int(_pending["deadline"] - time.time())
        if left <= 0:
            _pending = None
            _persist()
            return None, None, 0
        return _pending["action"], _pending["label"], left
