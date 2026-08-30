# -*- coding: utf-8 -*-
"""HTTP layer: routes, the API contract, server startup.

The POST /api contract is frozen: the password/action/delay fields, the
403/400/500 codes and the "no delay means 30 seconds" rule. External
integrations depend on it and they break silently — change it only together
with whatever calls it.
"""

import json
import mimetypes
import os
import socket
import sys
import threading
import time

from flask import Flask, jsonify, render_template, request

from . import (__version__, actions, autostart, backup, config, i18n,
               mqtt_bridge, security, state, tray)
from .logging_setup import log, tail

# Windows takes MIME types from the registry, where .js is often text/plain.
# A browser still runs such a script, but one nosniff header away the page
# stops working silently. Declaring the types is cheaper than debugging that.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

app = Flask(__name__)
START_TIME = time.time()


# --------------------------------------------------------------------------
# Shared
# --------------------------------------------------------------------------

def pc_name():
    return config.load().get("pc_name") or socket.gethostname()


@app.before_request
def guard():
    """Only the networks listed in the settings get through."""
    if request.path.startswith("/static/"):
        return None
    if not security.ip_allowed(request.remote_addr):
        log.warning("REFUSED by address: %s -> %s", request.remote_addr, request.path)
        return jsonify({"error": i18n.t("err.denied")}), 403
    return None


def _payload():
    """Accept JSON, form data and query strings alike: integrations send
    bodies in different shapes and none of them should be a failure mode."""
    return request.get_json(silent=True) or request.form or request.args or {}


def local_ip():
    """The address we are reachable at from the network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _system_info(lang=None):
    """Summary for the overview tab."""
    up = int(time.time() - START_TIME)
    days, rem = divmod(up, 86400)
    return {
        "host": pc_name(),
        "hostname": socket.gethostname(),
        "address": f"{local_ip()}:{config.load()['port']}",
        "uptime": i18n.t("unit.uptime_days" if days else "unit.uptime", lang,
                         d=days, h=rem // 3600, m=rem % 3600 // 60),
        "python": sys.version.split()[0],
        "project_dir": config.PROJECT_DIR,
        "log_file": config.LOG_FILE,
        "actions_total": len(actions.all_actions()),
        "actions_enabled": sum(1 for a in actions.all_actions() if actions.is_enabled(a)),
    }


def _secret(data):
    """The secret from the body or from an Authorization: Bearer header.

    The header suits integrations better: it stays out of the request body
    and out of proxy logs.
    """
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return data.get("password")


def _authorize(data):
    """(ip, error_or_None), where the error is a ready Flask response."""
    ip = request.remote_addr or "?"
    lang = i18n.from_request(request)
    left = security.lockout_left(ip)
    if left:
        return ip, (jsonify({"error": i18n.t("err.locked_out", lang, sec=left)}), 429)
    if not security.check_password(ip, _secret(data)):
        return ip, (jsonify({"error": i18n.t("err.wrong_password", lang)}), 403)
    return ip, None


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

@app.route("/")
def page_remote():
    cfg = config.load()
    return render_template(
        "remote.html",
        pc=pc_name(),
        version=__version__,
        delays=cfg["delay_choices"],
        default_delay=cfg["default_delay"],
    )


@app.route("/admin")
def page_admin():
    return render_template("admin.html", pc=pc_name(), version=__version__)


@app.route("/manifest.webmanifest")
def manifest():
    return jsonify({
        "name": f"pc-remote · {pc_name()}",
        "short_name": "pc-remote",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f5f5f7",
        "theme_color": "#f5f5f7",
        "icons": [{
            "src": "/static/icon.svg",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable",
        }],
    })


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@app.route("/healthz")
def healthz():
    """No password: monitoring and smart-home systems poll this. Exposes only
    the name, the uptime and any scheduled shutdown."""
    lang = i18n.from_request(request)
    up = int(time.time() - START_TIME)
    act, label_key, left = state.snapshot()
    return jsonify({
        "status": "ok",
        "host": pc_name(),
        "version": __version__,
        "uptime": i18n.t("unit.uptime", lang, h=up // 3600, m=up % 3600 // 60),
        "uptime_sec": up,
        "pending": act,
        "pending_label": i18n.t(label_key, lang) if label_key else None,
        "pending_left": left,
    })


@app.route("/actions")
def list_actions():
    """The catalog for the interface. No password: it exposes button labels
    only, and the network is already filtered by the allow-list."""
    lang = i18n.from_request(request)
    items = [actions.describe(a, lang) for a in actions.all_actions()
             if actions.is_enabled(a)]
    return jsonify({"lang": lang, "groups": actions.groups(lang), "actions": items})


@app.route("/api", methods=["POST"])
def api():
    data = _payload()
    ip, err = _authorize(data)
    if err:
        return err

    lang = i18n.from_request(request)
    act = actions.get(data.get("action"))
    if act is None:
        log.info("%s -> unknown command %r", ip, data.get("action"))
        return jsonify({"error": i18n.t("err.unknown_action", lang)}), 400
    if not actions.is_enabled(act):
        log.info("%s -> %s is disabled in the settings", ip, act.id)
        return jsonify({"error": i18n.t("err.action_disabled", lang)}), 403

    cfg = config.load()
    try:
        delay = max(0, min(600, int(data.get("delay", cfg["default_delay"]))))
    except (TypeError, ValueError):
        delay = cfg["default_delay"]

    ok, text, rc = actions.execute(act, delay, lang)
    _, _, left = state.snapshot()

    # Subscribers learn about the change at once, not on the next poll.
    mqtt_bridge.publish_state()
    tray.refresh()

    if not ok:
        log.error("%s -> %s FAILED (rc=%s): %s", ip, act.id, rc, text)
        return jsonify({"error": i18n.t("err.system", lang, detail=text)}), 500

    log.info("%s -> %s (delay=%s): %s", ip, act.id, delay, text)
    return jsonify({"result": text, "pending_left": left})


# --------------------------------------------------------------------------
# Settings API
# --------------------------------------------------------------------------

EDITABLE = {
    "port", "password", "pc_name", "default_delay", "delay_choices",
    "allowed_networks", "max_fails", "lockout_sec", "log_level",
    "actions", "launchers", "mqtt", "tray", "backups", "language",
}
NEEDS_RESTART = {"port", "host", "log_level", "tray"}


@app.route("/admin/api", methods=["POST"])
def admin_api():
    data = _payload()
    ip, err = _authorize(data)
    if err:
        return err

    lang = i18n.from_request(request)
    op = data.get("op")

    if op == "get":
        cfg = json.loads(json.dumps(config.load()))  # a copy, original untouched
        cfg.pop("password", None)  # secrets never travel back
        mq = cfg.get("mqtt", {})
        mq["password_set"] = bool(mq.get("password"))
        mq["password"] = ""
        return jsonify({
            "config": cfg,
            "catalog": [actions.describe(a, i18n.from_request(request))
                        for a in actions.all_actions()],
            "groups": actions.groups(i18n.from_request(request)),
            "env_password": bool(os.environ.get("REMOTE_WIN11_PASSWORD")),
            "log_file": config.LOG_FILE,
            "autostart": autostart.status(),
            "mqtt": mqtt_bridge.status(),
            "backups": backup.status(),
            "tokens": security.list_tokens(),
            "system": _system_info(i18n.from_request(request)),
            "version": __version__,
        })

    if op == "token_issue":
        value = security.issue_token(data.get("name"))
        log.warning("%s -> integration token issued", ip)
        # Handed out exactly once: showing it again would turn the list
        # into a key ring.
        return jsonify({"result": i18n.t("adm.token_issued", lang), "token": value,
                        "tokens": security.list_tokens()})

    if op == "token_revoke":
        found = security.revoke_token(data.get("id"))
        return jsonify({"result": i18n.t("adm.token_revoked" if found
                                         else "adm.token_missing", lang),
                        "tokens": security.list_tokens()})

    if op == "backup_export":
        include = bool(data.get("include_secrets"))
        log.info("%s -> settings backup exported (secrets: %s)", ip, include)
        return jsonify({"filename": backup.filename(), "payload": backup.snapshot(include)})

    if op == "backup_import":
        ok, text = backup.restore(data.get("payload"))
        if not ok:
            return jsonify({"error": text}), 400
        log.warning("%s -> settings restored from a backup", ip)
        return jsonify({"result": text, "restart_required": True})

    if op == "backup_push":
        results, summary = backup.push("manual")
        return jsonify({"result": summary, "targets": results,
                        "backups": backup.status()})

    if op == "mqtt_reconnect":
        # Broker settings are edited right here, so the bridge is brought
        # back up without restarting the whole remote.
        ok = mqtt_bridge.restart()
        st = mqtt_bridge.status()
        log.info("%s -> MQTT reconnect: %s", ip, "ok" if ok else st.get("error"))
        return jsonify({
            "result": i18n.t("adm.bridge_up", lang) if ok else i18n.t(
                "adm.bridge_down", lang,
                detail=st.get("error") or i18n.t("adm.bridge_off", lang)),
            "mqtt": st,
        })

    if op == "autostart":
        want = bool(data.get("enabled"))
        ok, msg = autostart.install() if want else autostart.uninstall()
        if not ok:
            return jsonify({"error": msg}), 500
        return jsonify({"result": msg, "autostart": autostart.status()})

    if op == "log":
        return jsonify({"lines": tail(int(data.get("lines", 200)))})

    if op == "save":
        patch = data.get("config") or {}
        cfg = config.load()
        restart = mqtt_dirty = False
        for key, value in patch.items():
            if key not in EDITABLE or key == "password":
                continue
            if key == "mqtt":
                # An empty password field means keep the current one: it is
                # never sent out, so it cannot come back either.
                value = dict(value or {})
                value.pop("password_set", None)
                if not value.get("password"):
                    value["password"] = cfg.get("mqtt", {}).get("password", "")
                mqtt_dirty = cfg.get("mqtt") != value
            if cfg.get(key) != value and key in NEEDS_RESTART:
                restart = True
            cfg[key] = value
        config.save(cfg)
        if mqtt_dirty:
            mqtt_bridge.restart()  # apply new credentials at once
        log.info("%s -> settings saved: %s", ip, ", ".join(sorted(patch)))
        return jsonify({"result": i18n.t("adm.saved", lang), "restart_required": restart,
                        "mqtt": mqtt_bridge.status()})

    if op == "password":
        new = str(data.get("new_password") or "")
        if len(new) < 4:
            return jsonify({"error": i18n.t("adm.password_short", lang)}), 400
        cfg = config.load()
        cfg["password"] = new
        config.save(cfg)
        log.warning("%s -> PASSWORD CHANGED", ip)
        return jsonify({
            "result": i18n.t("adm.password_changed", lang)
        })

    if op == "restart":
        try:
            autostart.restart_service()
        except OSError as e:
            return jsonify({"error": i18n.t("adm.restart_failed", lang, detail=e)}), 500
        log.warning("%s -> restart requested from the settings page", ip)
        return jsonify({"result": i18n.t("adm.restarting", lang)})

    return jsonify({"error": i18n.t("adm.unknown_op", lang)}), 400


# --------------------------------------------------------------------------
# Startup
# --------------------------------------------------------------------------

def already_running(port):
    """A second instance must not die quietly on a busy port."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.7):
            return True
    except OSError:
        return False


def _serve_forever(host, port):
    try:
        from waitress import serve
    except ImportError:
        # Fallback: the remote still starts if waitress is missing.
        log.warning("waitress not found, falling back to the Flask server")
        app.run(host=host, port=port, debug=False, threaded=True)
        return
    log.info("Listening on http://%s:%s (waitress)", host, port)
    serve(app, host=host, port=port, threads=6, ident="pc-remote")


def main():
    cfg = config.load()
    port, host = int(cfg["port"]), cfg["host"]

    if already_running(port):
        log.warning("Port %s is already in use, not starting a second instance", port)
        return 0

    left = state.restore()
    log.info("=" * 62)
    log.info("pc-remote %s starting on %s, python %s",
             __version__, pc_name(), sys.version.split()[0])
    if left:
        log.warning("Picked up a running timer after restart: %s s", left)

    if mqtt_bridge.start():
        log.info("MQTT bridge started, device %s", mqtt_bridge.node_id())
    backup.start_scheduler()

    # The tray icon must own the main thread on Windows, so the web server
    # moves to a background one. Without an icon we simply wait here.
    web = threading.Thread(target=_serve_forever, args=(host, port),
                           name="http", daemon=True)
    web.start()

    if not tray.run():
        web.join()
    return 0
