# -*- coding: utf-8 -*-
"""Access: network allow-list, password, integration tokens, brute-force guard.

Two kinds of secret, on purpose. The password is for a human and gets changed
when it leaks or simply gets old. A token is for a machine, is issued
separately and is revoked on its own — before tokens existed, every password
change quietly broke every integration at once.

There is no general rate limit here: with a handful of clients there is no
flood to defend against, and an extra dependency once cost the project its
ability to start at all. Password guessing is the real threat, so that is what
is guarded.
"""

import hmac
import secrets
import threading
import time
from datetime import date
from ipaddress import ip_address, ip_network

from . import config
from .logging_setup import log

_lock = threading.RLock()
_fails = {}  # {ip: [failures, lockout_until]}
_LAST_SWEEP = [0.0]


# --------------------------------------------------------------------------
# Networks
# --------------------------------------------------------------------------

def _networks():
    nets = []
    for raw in config.load()["allowed_networks"]:
        try:
            nets.append(ip_network(raw, strict=False))
        except ValueError:
            log.warning("Could not parse network %r from settings, skipping", raw)
    return nets


def ip_allowed(raw_ip):
    try:
        addr = ip_address(raw_ip or "")
    except ValueError:
        return False
    return any(addr in net for net in _networks())


# --------------------------------------------------------------------------
# Integration tokens
# --------------------------------------------------------------------------

def issue_token(name):
    """Issue a token. The value is shown once, at creation."""
    token = secrets.token_urlsafe(24)
    cfg = config.load()
    cfg["api_tokens"].append({
        # Separate id so a token can be revoked without exposing its value
        "id": secrets.token_hex(6),
        "name": (name or "integration").strip()[:40],
        "token": token,
        "created": date.today().isoformat(),
        "last_used": None,
    })
    config.save(cfg)
    log.warning("Integration token issued: %s", name)
    return token


def revoke_token(token_id):
    cfg = config.load()
    before = len(cfg["api_tokens"])
    cfg["api_tokens"] = [t for t in cfg["api_tokens"] if t.get("id") != token_id]
    config.save(cfg)
    if len(cfg["api_tokens"]) != before:
        log.warning("Integration token revoked")
        return True
    return False


def list_tokens():
    """Without the values: showing them a second time would turn the list
    into a key ring."""
    out = []
    for t in config.load()["api_tokens"]:
        raw = t.get("token", "")
        out.append({
            "id": t.get("id"),
            "name": t.get("name"),
            "hint": (raw[:4] + "…" + raw[-4:]) if len(raw) > 10 else "…",
            "created": t.get("created"),
            "last_used": t.get("last_used"),
        })
    return out


def _touch(token_value):
    """Record the date of use, at most once a day: every request would
    otherwise hit the disk."""
    today = date.today().isoformat()
    cfg = config.load()
    for t in cfg["api_tokens"]:
        if t.get("token") == token_value and t.get("last_used") != today:
            t["last_used"] = today
            config.save(cfg)
            return


# --------------------------------------------------------------------------
# Secret check
# --------------------------------------------------------------------------

def _sweep(now):
    """Drop expired lockouts, otherwise the dict grows forever."""
    if now - _LAST_SWEEP[0] < 600:
        return
    _LAST_SWEEP[0] = now
    for ip in [ip for ip, rec in _fails.items() if rec[1] < now]:
        _fails.pop(ip, None)


def lockout_left(ip):
    """Seconds this address is still locked out for (0 when it is not)."""
    cfg = config.load()
    now = time.time()
    with _lock:
        _sweep(now)
        rec = _fails.get(ip)
        if not rec or rec[0] < cfg["max_fails"]:
            return 0
        if now >= rec[1]:
            _fails.pop(ip, None)
            return 0
        return int(rec[1] - now)


def _same(a, b):
    """Constant-time compare; a plain == would leak length and prefix
    through timing.

    Compares bytes rather than strings: compare_digest raises TypeError on
    non-ASCII text, so a password with any accented character would break
    sign-in entirely and a guess containing one would return 500 instead of
    a refusal.
    """
    return hmac.compare_digest(str(a or "").encode("utf-8"),
                               str(b or "").encode("utf-8"))


def check_password(ip, given):
    """Accepts both the human password and an integration token."""
    cfg = config.load()
    given = str(given or "")

    ok = _same(given, config.password())
    matched_token = None
    if not ok:
        for t in cfg["api_tokens"]:
            if _same(given, t.get("token", "")):
                ok, matched_token = True, t.get("token")
                break

    with _lock:
        if ok:
            _fails.pop(ip, None)
        else:
            cnt = _fails.get(ip, [0, 0])[0] + 1
            _fails[ip] = [cnt, time.time() + cfg["lockout_sec"]]

    if ok:
        if matched_token:
            _touch(matched_token)
        return True

    log.warning("WRONG SECRET from %s (attempt %s/%s)", ip, cnt, cfg["max_fails"])
    time.sleep(1)  # slow guessing down
    return False
