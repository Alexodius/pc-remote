# -*- coding: utf-8 -*-
"""Windows notification area icon.

The remote is a windowless background service, so telling "running" from
"died quietly" used to require opening a browser. The icon answers that at a
glance, and a right-click gives the basic actions without reaching for a phone.

The colour is the indicator: blue when idle, orange while a shutdown counts
down. The context menu follows the Windows theme.

pystray must own the main thread on Windows, which is why the web server runs
in a background one (see server.main). Without pystray or Pillow the remote
simply runs without an icon.
"""

import ctypes
import os
import subprocess
import threading
import time
import webbrowser

from . import actions, autostart, config, state
from .i18n import default_language, t
from .logging_setup import log

_icon = None
_stop = threading.Event()

BLUE = (10, 132, 255, 255)     # idle
ORANGE = (255, 159, 10, 255)   # counting down


def _enable_dark_menus():
    """Allow this process to use the dark system menu.

    Win32 draws the tray context menu, and it stays light even on a fully dark
    system unless the application asks. The calls are undocumented and only
    reachable by ordinal in uxtheme.dll, hence the caution and the silent
    no-op on older Windows builds.

    Mode 1 is AllowDark: follow the system setting rather than force dark on
    top of a light Windows theme.
    """
    try:
        uxtheme = ctypes.WinDLL("uxtheme.dll")
        set_preferred_app_mode = uxtheme[135]
        set_preferred_app_mode.argtypes = [ctypes.c_int]
        set_preferred_app_mode.restype = ctypes.c_int
        set_preferred_app_mode(1)
        uxtheme[136]()  # FlushMenuThemes, otherwise only new menus pick it up
        return True
    except Exception as e:
        log.info("Dark tray menu is unavailable: %s", e)
        return False


def _image(color):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # The classic power glyph: a ring open at the top plus a stroke.
    d.arc([10, 10, 54, 54], start=295, end=245, fill=color, width=7)
    d.line([32, 8, 32, 30], fill=color, width=7)
    return img


def _url(path=""):
    return f"http://127.0.0.1:{config.load()['port']}{path}"


def _run_action(action_id):
    def handler(icon=None, item=None):
        action = actions.get(action_id)
        if action is None or not actions.is_enabled(action):
            return
        delay = config.load()["default_delay"] if action.delay else 0
        ok, text, _ = actions.execute(action, delay, default_language())
        log.info("tray -> %s (delay=%s): %s", action_id, delay, text)
        _notify(text if ok else t("tray.failed", default_language(), detail=text))
        _refresh()
        try:
            from . import mqtt_bridge
            mqtt_bridge.publish_state()
        except Exception:
            pass
    return handler


def _notify(text):
    if _icon is None:
        return
    try:
        _icon.notify(text, "pc-remote")
    except Exception:
        pass  # notifications may be disabled by policy, which is fine


def _pending_text():
    _, label_key, left = state.snapshot()
    if not left:
        return None
    lang = default_language()
    return t("res.state_pending", lang, what=t(label_key, lang), left=left)


def _title(item=None):
    """Icon tooltip: two lines, as is customary in the tray."""
    from . import __version__
    from .server import pc_name
    pending = _pending_text()
    return (f"pc-remote {__version__} · {pc_name()}\n"
            f"{pending or t('tray.online', default_language())}")


def _menu_title(item=None):
    """The first menu row, kept to a single line."""
    from .server import pc_name
    return f"{pc_name()} · {_pending_text() or t('tray.online', default_language())}"


def _build_menu():
    import pystray

    lang = default_language()

    groups = []
    for grp in actions.groups(default_language()):
        gid, gtitle = grp["id"], grp["title"]
        items = [
            pystray.MenuItem(a.label(default_language()), _run_action(a.id))
            for a in actions.all_actions()
            if a.group == gid and actions.is_enabled(a) and a.id != "cancel"
        ]
        if items:
            groups.append(pystray.MenuItem(gtitle, pystray.Menu(*items)))

    def toggle_autostart(icon, item):
        enabled = autostart.status()["installed"]
        ok, msg = autostart.uninstall() if enabled else autostart.install()
        _notify(msg)
        _refresh()

    def open_log(icon=None, item=None):
        try:
            os.startfile(config.LOG_FILE)
        except OSError:
            subprocess.Popen(["notepad.exe", config.LOG_FILE])

    return pystray.Menu(
        pystray.MenuItem(_menu_title, lambda icon, item: webbrowser.open(_url()),
                         default=True),
        pystray.Menu.SEPARATOR,
        # Cancel appears only when there is something to cancel.
        pystray.MenuItem(
            lambda item: t("tray.cancel", default_language(),
                           what=_pending_text() or ""),
            _run_action("cancel"),
            visible=lambda item: bool(_pending_text()),
        ),
        *groups,
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(t("tray.open", lang), lambda icon, item: webbrowser.open(_url())),
        pystray.MenuItem(t("tray.settings", lang),
                         lambda icon, item: webbrowser.open(_url("/admin"))),
        pystray.MenuItem(t("tray.log", lang), open_log),
        pystray.MenuItem(
            t("tray.autostart", lang),
            toggle_autostart,
            checked=lambda item: autostart.status()["installed"],
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(t("tray.quit", lang), _quit),
    )


def _quit(icon=None, item=None):
    log.warning("Quit requested from the tray menu")
    _stop.set()
    try:
        from . import mqtt_bridge
        mqtt_bridge.stop()
    except Exception:
        pass
    if _icon:
        _icon.stop()
    # waitress runs on a daemon thread and dies with the process.
    os._exit(0)


def refresh():
    """Refresh the tooltip and the menu. Safe to call with no icon."""
    if _icon is None:
        return
    try:
        _icon.title = _title()
        _icon.update_menu()
    except Exception:
        pass


_refresh = refresh  # internal alias


def _watcher():
    """Recolour the icon and refresh the tooltip while a countdown runs."""
    was = None
    while not _stop.wait(1):
        _, _, left = state.snapshot()
        now = bool(left)
        try:
            if now != was:
                _icon.icon = _image(ORANGE if now else BLUE)
                was = now
            if now:
                _icon.title = _title()
        except Exception:
            pass


def run():
    """Show the icon. Blocks the thread, so call it from the main one.
    Returns False when unavailable; the remote then runs without it."""
    global _icon
    if not config.load().get("tray", True):
        return False
    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as e:
        log.warning("Tray icon unavailable (%s), running without it", e)
        return False

    import pystray as ps

    _enable_dark_menus()
    try:
        _icon = ps.Icon("pc-remote", _image(BLUE), _title(), _build_menu())
        threading.Thread(target=_watcher, name="tray-watcher", daemon=True).start()
        log.info("Tray icon shown")
        _icon.run()
    except Exception as e:
        log.error("Tray icon failed to start: %s", e)
        return False
    return True
