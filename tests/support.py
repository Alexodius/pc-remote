# -*- coding: utf-8 -*-
"""Shared harness: isolated settings and stubbed system calls."""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import actions, config, security, state  # noqa: E402


class Recorder:
    """Stands in for run_cmd/run_detached: records calls, executes nothing."""

    def __init__(self, returncode=0, stderr=""):
        self.calls = []
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, args, timeout=None):
        self.calls.append(list(args))
        return self.returncode, self.stderr

    @property
    def last(self):
        return self.calls[-1] if self.calls else None


class Base(unittest.TestCase):
    """Every test gets fresh settings in a temporary directory.

    The real data/config.json is never touched: otherwise a test run would
    rewrite the working password, broker credentials and action set.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patches = [
            mock.patch.object(config, "DATA_DIR", self._tmp.name),
            mock.patch.object(config, "CONFIG_FILE",
                              os.path.join(self._tmp.name, "config.json")),
            mock.patch.object(config, "STATE_FILE",
                              os.path.join(self._tmp.name, "state.json")),
            mock.patch.object(config, "LOG_FILE",
                              os.path.join(self._tmp.name, "server.log")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        config._cache = None
        self.addCleanup(setattr, config, "_cache", None)

        # Without a handler logging prints warnings to stderr and clutters
        # the run; no log file is needed here.
        import logging
        from app.logging_setup import log as applog
        applog.handlers = [logging.NullHandler()]
        applog.propagate = False

        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("REMOTE_WIN11_PASSWORD", None)

        cfg = config.load(force=True)
        cfg["password"] = "secret"
        cfg["api_tokens"] = []
        config.save(cfg)

        state.clear()
        security._fails.clear()
        self.addCleanup(self._tmp.cleanup)

    def stub_system(self, returncode=0, stderr=""):
        """Close every door to the system. Returns the call log.

        There are more than two doors: besides spawning processes there are
        direct WinAPI calls — blanking the monitors, tapping media keys — and
        launching programs. Without these a test would really press them.
        """
        rec = Recorder(returncode, stderr)
        for name in ("run_cmd", "run_detached"):
            p = mock.patch.object(actions, name, rec)
            p.start()
            self.addCleanup(p.stop)

        for name, marker in (("_monitor_power", "monitor_power"),
                             ("_tap_key", "tap_key"),
                             ("_start", "start")):
            def fake(*args, _m=marker, _r=rec, **kwargs):
                _r.calls.append([_m, *[str(a) for a in args]])
                return _r.returncode, _r.stderr
            p = mock.patch.object(actions, name, fake)
            p.start()
            self.addCleanup(p.stop)
        return rec
