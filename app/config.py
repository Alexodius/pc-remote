# -*- coding: utf-8 -*-
"""Settings: defaults, loading and atomic writes.

Everything tweakable lives in data/config.json and is edited from the web UI.
The code keeps only defaults so that updating the project never overwrites
user settings; data/ is not in git.
"""

import json
import os
import sys
import tempfile
import threading

# In a frozen build __file__ points into a temporary extraction directory,
# so data/ would end up there and be lost on every run.
if getattr(sys, "frozen", False):
    PROJECT_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(PROJECT_DIR, "data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
LOG_FILE = os.path.join(DATA_DIR, "server.log")

CONFIG_VERSION = 2

DEFAULTS = {
    "version": CONFIG_VERSION,
    "host": "0.0.0.0",
    "port": 5000,
    # Placeholder only; the real password lives in data/config.json.
    # REMOTE_WIN11_PASSWORD overrides the file when set.
    # This is the human password — integrations should use tokens instead,
    # so that changing it does not break them all at once.
    "password": "changeme",
    # [{"name", "id", "token", "created", "last_used"}], accepted wherever
    # the password is, plus as an Authorization: Bearer header.
    "api_tokens": [],
    "pc_name": "",  # empty means the host name
    # Language for what lives outside a browser: smart-home entity names and
    # the tray menu. The web UI picks its own language per device.
    "language": "en",
    "default_delay": 30,
    "delay_choices": [0, 10, 30, 60],
    # Private ranges by default: a home network and a VPN both land here,
    # while public addresses are refused.
    "allowed_networks": [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
    ],
    "max_fails": 5,
    "lockout_sec": 300,
    "log_level": "INFO",
    # {action_id: {"enabled": bool}}; missing ones fall back to the catalog.
    "actions": {},
    # [{"name", "target", "icon"}] — effectively "run any program",
    # so empty by default.
    "launchers": [],
    "tray": True,
    # Settings backups: [{"name", "url", "enabled", "auth_header"}].
    # Secrets are stripped from outgoing copies: they travel to a remote
    # address, and keys have no business being there.
    "backups": {
        "webhooks": [],
        "auto_enabled": False,
        "interval_hours": 24,
        "include_secrets": False,
        "last_run": None,
        "last_result": None,
    },
    # MQTT bridge with auto-discovery. Off until credentials are set.
    "mqtt": {
        "enabled": False,
        "host": "",
        "port": 1883,
        "username": "",
        "password": "",
        "discovery_prefix": "homeassistant",
        "device_name": "",
    },
}

_lock = threading.RLock()
_cache = None


def _fill(target, defaults):
    """Add missing keys without touching what the user already set."""
    for k, v in defaults.items():
        if k not in target:
            target[k] = json.loads(json.dumps(v))  # a copy, not a shared ref
        elif isinstance(v, dict) and isinstance(target[k], dict):
            _fill(target[k], v)
    return target


def load(force=False):
    """Read config.json, filling in defaults. Cached."""
    global _cache
    with _lock:
        if _cache is not None and not force:
            return _cache
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, encoding="utf-8") as fh:
                    cfg = json.load(fh)
            except (OSError, ValueError):
                # A broken file must not keep the remote down: start on
                # defaults and set the file aside for inspection.
                try:
                    os.replace(CONFIG_FILE, CONFIG_FILE + ".broken")
                except OSError:
                    pass
                cfg = {}
        cfg = _fill(cfg, DEFAULTS)
        cfg["version"] = CONFIG_VERSION
        _cache = cfg
        return cfg


def save(cfg):
    """Atomic write: temporary file first, then replace."""
    global _cache
    with _lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, CONFIG_FILE)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        _cache = cfg
        return cfg


def password():
    return os.environ.get("REMOTE_WIN11_PASSWORD") or load()["password"]


def action_enabled(action_id, default=True):
    return bool(load()["actions"].get(action_id, {}).get("enabled", default))
