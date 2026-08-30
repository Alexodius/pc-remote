# -*- coding: utf-8 -*-
"""Settings backups: download as a file and push to external targets.

Settings are dozens of small decisions that pile up over months and vanish in
a single reinstall. A copy is taken in one request and sent wherever the rest
of the backups live: object storage, a NAS, a hypervisor — anything that
accepts a POST with JSON.

Secrets are stripped by default: the copy travels to a remote address, and
keys have no business being there. To move to another machine, enable
"include secrets" and take the copy as a file.
"""

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

from . import config
from .logging_setup import log

SECRET_KEYS = ("password", "api_tokens")

_stop = threading.Event()
_thread = None


def snapshot(include_secrets=False):
    """A settings snapshot. Password and tokens are stripped unless asked for."""
    from . import __version__

    cfg = json.loads(json.dumps(config.load()))  # deep copy
    if not include_secrets:
        cfg.pop("password", None)
        cfg["api_tokens"] = []
        if isinstance(cfg.get("mqtt"), dict):
            cfg["mqtt"]["password"] = ""
        for hook in cfg.get("backups", {}).get("webhooks", []):
            hook["auth_header"] = ""
    # Bookkeeping field, not part of a restore
    cfg.get("backups", {}).pop("last_result", None)

    return {
        "app": "pc-remote",
        "version": __version__,
        "created": datetime.now().isoformat(timespec="seconds"),
        "host": config.load().get("pc_name") or _hostname(),
        "includes_secrets": bool(include_secrets),
        "config": cfg,
    }


def _hostname():
    import socket
    return socket.gethostname()


def filename():
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"pc-remote-{_hostname().lower()}-{stamp}.json"


def _keep_nested_secrets(incoming, current):
    """Put back the secrets a stripped backup does not carry.

    Top-level password and api_tokens are simply not applied, but nested ones
    arrive as empty strings and would silently wipe working values such as the
    MQTT broker password. Restoring settings must not cut the smart home off.
    """
    mqtt = incoming.get("mqtt")
    if isinstance(mqtt, dict) and not mqtt.get("password"):
        mqtt["password"] = current.get("mqtt", {}).get("password", "")

    hooks = (incoming.get("backups") or {}).get("webhooks")
    if isinstance(hooks, list):
        by_url = {h.get("url"): h.get("auth_header", "")
                  for h in (current.get("backups") or {}).get("webhooks", [])}
        for hook in hooks:
            if not hook.get("auth_header"):
                hook["auth_header"] = by_url.get(hook.get("url"), "")
    return incoming


def restore(payload):
    """Apply a backup. Returns (ok, text).

    Keys absent from the backup keep their current value, so a stripped copy
    never overwrites the working password.
    """
    if not isinstance(payload, dict) or payload.get("app") != "pc-remote":
        return False, "This is not a pc-remote settings backup"
    incoming = payload.get("config")
    if not isinstance(incoming, dict):
        return False, "The backup has no config section"

    cfg = config.load()
    if not payload.get("includes_secrets"):
        incoming = _keep_nested_secrets(json.loads(json.dumps(incoming)), cfg)

    skipped = []
    for key, value in incoming.items():
        if key in SECRET_KEYS and not payload.get("includes_secrets"):
            skipped.append(key)
            continue
        if key == "version":
            continue
        cfg[key] = value
    config.save(cfg)

    log.warning("Settings restored from a backup made at %s", payload.get("created"))
    note = " The backup carried no password or tokens, so those are unchanged." if skipped else ""
    return True, f"Settings restored.{note} A restart is required."


# --------------------------------------------------------------------------
# Pushing to external targets
# --------------------------------------------------------------------------

def push(reason="manual"):
    """Send a copy to every enabled target. Returns the per-target results."""
    conf = config.load().get("backups", {})
    hooks = [h for h in conf.get("webhooks", []) if h.get("enabled") and h.get("url")]
    if not hooks:
        return [], "No targets are enabled"

    body = json.dumps(snapshot(conf.get("include_secrets", False)),
                      ensure_ascii=False, indent=2).encode("utf-8")
    results = []
    for hook in hooks:
        name = hook.get("name") or hook["url"]
        headers = {
            "Content-Type": "application/json",
            "X-PC-Remote-Filename": filename(),
        }
        if hook.get("auth_header"):
            headers["Authorization"] = hook["auth_header"]
        req = urllib.request.Request(hook["url"], data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                results.append({"name": name, "ok": True, "detail": f"HTTP {resp.status}"})
        except urllib.error.HTTPError as e:
            results.append({"name": name, "ok": False, "detail": f"HTTP {e.code}"})
        except Exception as e:
            results.append({"name": name, "ok": False, "detail": str(e)[:120]})

    good = sum(1 for r in results if r["ok"])
    summary = f"{good} of {len(results)} succeeded"
    log.info("Settings backup pushed (%s): %s", reason, summary)

    cfg = config.load()
    cfg["backups"]["last_run"] = datetime.now().isoformat(timespec="seconds")
    cfg["backups"]["last_result"] = summary
    config.save(cfg)
    return results, summary


def _loop():
    """Check hourly whether it is time. Not a day-long sleep: that would
    shift the schedule on every restart."""
    while not _stop.wait(3600):
        conf = config.load().get("backups", {})
        if not conf.get("auto_enabled"):
            continue
        last = conf.get("last_run")
        try:
            elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
        except (TypeError, ValueError):
            elapsed = float("inf")
        if elapsed >= int(conf.get("interval_hours", 24)) * 3600:
            try:
                push("scheduled")
            except Exception:
                log.exception("Scheduled backup push failed")


def start_scheduler():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="backup-scheduler", daemon=True)
    _thread.start()


def status():
    conf = config.load().get("backups", {})
    return {
        "auto_enabled": bool(conf.get("auto_enabled")),
        "interval_hours": conf.get("interval_hours", 24),
        "include_secrets": bool(conf.get("include_secrets")),
        "last_run": conf.get("last_run"),
        "last_result": conf.get("last_result"),
        "targets": len([h for h in conf.get("webhooks", []) if h.get("enabled")]),
    }
