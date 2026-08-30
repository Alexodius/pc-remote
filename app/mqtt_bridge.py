# -*- coding: utf-8 -*-
"""MQTT bridge with smart-home auto-discovery.

Polling is what you write in a hurry: the smart home asks /healthz every ten
seconds. It has three problems — the countdown moves in jumps, a dead machine
goes unnoticed for a while, and every entity has to be declared by hand.

Over MQTT the device announces itself instead:

* discovery messages create a ready device with every button and sensor;
* state is published the moment it changes, not when asked;
* a last will reports "offline" even if the machine loses power.

That is how Tasmota, ESPHome and Zigbee2MQTT work.

HTTP does not go away: its contract is frozen for integrations that are
already configured. MQTT is a second, optional channel.
"""

import json
import re
import socket
import threading
import time

from . import actions, config, state
from .i18n import default_language, t
from .logging_setup import log

_client = None
_thread = None
_stop = threading.Event()
_status = {"enabled": False, "connected": False, "error": None, "last_publish": None}


def node_id():
    """Device id used in topics: ASCII letters, digits and underscores only."""
    raw = config.load().get("pc_name") or socket.gethostname()
    return re.sub(r"[^a-z0-9_]+", "_", raw.lower()).strip("_") or "pc_remote"


def _cfg():
    return config.load().get("mqtt", {})


def _topics():
    base = f"pc-remote/{node_id()}"
    return {
        "base": base,
        "availability": f"{base}/availability",
        "state": f"{base}/state",
        "command": f"{base}/cmd",
    }


def _device():
    """Shared device record: it groups every entity under one computer
    instead of scattering them through the entity list."""
    from . import __version__
    return {
        "identifiers": [node_id()],
        "name": _cfg().get("device_name") or config.load().get("pc_name") or socket.gethostname(),
        "manufacturer": "pc-remote",
        "model": "Windows PC",
        "sw_version": __version__,
        "configuration_url": f"http://{_local_ip()}:{config.load()['port']}/admin",
    }


def _local_ip():
    """The address we are reachable at, used for the settings link."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return socket.gethostname()
    finally:
        s.close()


# --------------------------------------------------------------------------
# Auto-discovery
# --------------------------------------------------------------------------

def _discovery_messages():
    """What to publish so the smart home builds the device by itself."""
    topics = _topics()
    prefix = _cfg().get("discovery_prefix") or "homeassistant"
    lang = default_language()
    nid = node_id()
    dev = _device()
    out = []

    common = {
        "availability_topic": topics["availability"],
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": dev,
    }

    # One button per enabled action. Disable it in the settings and the
    # button disappears from the smart home too.
    for a in actions.all_actions():
        if not actions.is_enabled(a):
            continue
        safe = a.id.replace(":", "_")
        # entity_category is deliberately absent: these are controls, not
        # configuration or diagnostics. A category would move them to a
        # separate block, and an explicit null makes some configs be rejected.
        out.append((
            f"{prefix}/button/{nid}/{safe}/config",
            dict(common, **{
                "name": a.label(default_language()),
                "unique_id": f"{nid}_{safe}",
                "object_id": f"{nid}_{safe}",
                "command_topic": topics["command"],
                "payload_press": a.id,
                "icon": _MDI.get(a.icon, "mdi:gesture-tap-button"),
            }),
        ))

    out.append((
        f"{prefix}/sensor/{nid}/countdown/config",
        dict(common, **{
            "name": t("entity.countdown", lang),
            "unique_id": f"{nid}_countdown",
            "object_id": f"{nid}_countdown",
            "state_topic": topics["state"],
            "value_template": "{{ value_json.pending_left }}",
            "unit_of_measurement": "s",
            "icon": "mdi:timer-sand",
        }),
    ))
    out.append((
        f"{prefix}/sensor/{nid}/uptime/config",
        dict(common, **{
            "name": t("entity.uptime", lang),
            "unique_id": f"{nid}_uptime",
            "object_id": f"{nid}_uptime",
            "state_topic": topics["state"],
            "value_template": "{{ value_json.uptime }}",
            "icon": "mdi:timer-outline",
            "entity_category": "diagnostic",
        }),
    ))
    out.append((
        f"{prefix}/sensor/{nid}/status/config",
        dict(common, **{
            "name": t("entity.status", lang),
            "unique_id": f"{nid}_status",
            "object_id": f"{nid}_status",
            "state_topic": topics["state"],
            "value_template": "{{ value_json.status_text }}",
            "icon": "mdi:desktop-tower-monitor",
        }),
    ))
    out.append((
        f"{prefix}/binary_sensor/{nid}/online/config",
        dict(common, **{
            "name": t("entity.agent", lang),
            "unique_id": f"{nid}_online",
            "object_id": f"{nid}_online",
            "state_topic": topics["availability"],
            "payload_on": "online",
            "payload_off": "offline",
            "device_class": "connectivity",
            "entity_category": "diagnostic",
        }),
    ))
    return out


_MDI = {
    "power": "mdi:power",
    "restart": "mdi:restart",
    "cancel": "mdi:close-circle",
    "sleep": "mdi:power-sleep",
    "hibernate": "mdi:snowflake",
    "logout": "mdi:logout",
    "lock": "mdi:lock",
    "monitor-off": "mdi:monitor-off",
    "monitor-on": "mdi:monitor",
    "mute": "mdi:volume-mute",
    "volume-down": "mdi:volume-medium",
    "volume-up": "mdi:volume-high",
    "steam": "mdi:steam",
    "app": "mdi:application",
}


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

def _state_payload():
    from .server import START_TIME, pc_name
    act, label_key, left = state.snapshot()
    up = int(time.time() - START_TIME)
    lang = default_language()
    if left > 0:
        status = t("res.state_pending", lang, what=t(label_key, lang), left=left)
    else:
        status = t("res.state_online", lang)
    return {
        "host": pc_name(),
        "uptime": t("unit.uptime", lang, h=up // 3600, m=up % 3600 // 60),
        "uptime_sec": up,
        "pending": act,
        "pending_left": left,
        "status_text": status,
    }


def publish_state():
    """Publish state immediately. Called after every action so subscribers
    learn about the change at once rather than on the next poll."""
    if not (_client and _status["connected"]):
        return
    try:
        _client.publish(_topics()["state"], json.dumps(_state_payload(), ensure_ascii=False),
                        qos=0, retain=True)
        _status["last_publish"] = time.time()
    except Exception as e:
        log.warning("MQTT: could not publish state: %s", e)


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------

def _on_connect(client, userdata, flags, rc, properties=None):
    code = getattr(rc, "value", rc)
    if code != 0:
        _status.update(connected=False, error=f"broker refused (code {code})")
        log.error("MQTT: connection refused, code %s", code)
        return
    _status.update(connected=True, error=None)
    topics = _topics()
    log.info("MQTT: connected to %s:%s as %s", _cfg().get("host"), _cfg().get("port"), node_id())

    client.publish(topics["availability"], "online", qos=1, retain=True)
    for topic, payload in _discovery_messages():
        client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)
    client.subscribe(topics["command"], qos=1)
    publish_state()


def _on_disconnect(client, userdata, *args):
    _status["connected"] = False
    log.warning("MQTT: connection lost, paho will reconnect on its own")


def _on_message(client, userdata, msg):
    """An incoming command: either a bare action id (what a button sends via
    payload_press) or JSON carrying a delay."""
    raw = msg.payload.decode("utf-8", errors="replace").strip()
    delay = config.load()["default_delay"]
    action_id = raw
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            action_id = data.get("action", "")
            delay = int(data.get("delay", delay))
        except (ValueError, TypeError):
            log.warning("MQTT: could not parse command %r", raw)
            return

    action = actions.get(action_id)
    if action is None or not actions.is_enabled(action):
        log.warning("MQTT: command %r is unknown or disabled", action_id)
        return

    ok, text, rc = actions.execute(action, delay)
    log.info("MQTT -> %s (delay=%s): %s", action_id, delay, text)
    publish_state()


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------

def _heartbeat():
    """Once a second while a countdown runs, every thirty otherwise.
    That is what makes the timer tick live without a single poll."""
    last = 0
    while not _stop.wait(1):
        _, _, left = state.snapshot()
        now = time.time()
        if left > 0 or now - last >= 30:
            publish_state()
            last = now


def start():
    """Bring the bridge up if enabled. No failure here may disturb the
    remote itself: MQTT is an additional channel."""
    global _client, _thread
    cfg = _cfg()
    _status["enabled"] = bool(cfg.get("enabled"))
    if not cfg.get("enabled"):
        return False
    if not cfg.get("host"):
        _status["error"] = "broker address is not set"
        return False

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        _status["error"] = "paho-mqtt is not installed"
        log.warning("MQTT is enabled but paho-mqtt is missing, bridge not started")
        return False

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id=f"pc-remote-{node_id()}")
        if cfg.get("username"):
            client.username_pw_set(cfg["username"], cfg.get("password") or None)
        # Last will: the broker announces us offline if the link drops.
        # This is the main reason to use MQTT at all.
        client.will_set(_topics()["availability"], "offline", qos=1, retain=True)
        client.on_connect = _on_connect
        client.on_disconnect = _on_disconnect
        client.on_message = _on_message
        client.connect_async(cfg["host"], int(cfg.get("port", 1883)), keepalive=30)
        client.loop_start()
    except Exception as e:
        _status["error"] = str(e)
        log.error("MQTT: could not start the bridge: %s", e)
        return False

    _client = client
    _stop.clear()
    _thread = threading.Thread(target=_heartbeat, name="mqtt-heartbeat", daemon=True)
    _thread.start()
    return True


def stop():
    global _client
    _stop.set()
    if _client:
        try:
            _client.publish(_topics()["availability"], "offline", qos=1, retain=True)
            _client.loop_stop()
            _client.disconnect()
        except Exception:
            pass
        _client = None
    _status["connected"] = False


def restart():
    stop()
    time.sleep(0.3)
    return start()


def status():
    out = dict(_status)
    out["node_id"] = node_id()
    out["topics"] = _topics()
    return out
