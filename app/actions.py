# -*- coding: utf-8 -*-
"""Action catalog.

Adding a button is one entry in CATALOG. The remote, the settings page, the
API and smart-home discovery all build themselves from this list.

Labels and replies are stored as keys, not text: the translation is picked in
the language the request arrived in (see i18n.py).

`locked` means the action cannot be disabled: external integrations usually
depend on these, and their disappearance breaks automations silently.
"""

import ctypes
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

from . import config, state
from .i18n import t
from .logging_setup import log

CREATE_NO_WINDOW = 0x08000000  # without it pythonw flashes a console window

# Media key virtual codes
VK_MUTE, VK_VOL_DOWN, VK_VOL_UP = 0xAD, 0xAE, 0xAF


# --------------------------------------------------------------------------
# Low-level helpers
# --------------------------------------------------------------------------

def run_cmd(args, timeout=15):
    """Run a command without a console window. Returns (code, stderr)."""
    try:
        p = subprocess.run(
            args, capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=timeout
        )
        return p.returncode, p.stderr.decode("cp866", errors="replace").strip()
    except Exception as e:  # reported as text; the server stays up
        return -1, str(e)


def run_detached(args):
    """Start and do not wait. Returns (0, "") or (-1, error text).

    Sleep, hibernation and sign-out take the machine down along with the
    calling process, so there is no result to wait for: a normal run would
    hang until the timeout and then report failure where everything worked.
    """
    try:
        subprocess.Popen(args, creationflags=CREATE_NO_WINDOW | 0x00000008,
                         close_fds=True)
        return 0, ""
    except Exception as e:
        return -1, str(e)


def _tap_key(vk, times=1):
    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)  # down
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # up
    return 0, ""


def _monitor_power(on):
    """SendMessageTimeout rather than SendMessage: a broadcast message hangs
    forever if any window in the system stops responding."""
    HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER = 0xFFFF, 0x0112, 0xF170
    res = ctypes.c_ulong()
    ok = ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER,
        -1 if on else 2, 0x0002, 2000, ctypes.byref(res),
    )
    if on:
        # One message is not enough: Windows only wakes displays on input,
        # so nudge the cursor a pixel and back.
        ctypes.windll.user32.mouse_event(0x0001, 1, 0, 0, 0)
        ctypes.windll.user32.mouse_event(0x0001, -1, 0, 0, 0)
    return (0, "") if ok else (-1, t("err.no_reply"))


def _start(target):
    """Launch a program, or hand a URI to whatever handles it.

    A program starts in its own folder. Without that it inherits the working
    directory of the remote, and a launcher that expects to sit next to the
    files it loads — a game, a portable app — finds nothing and fails in a
    way that looks like the button did nothing at all.
    """
    try:
        folder = os.path.dirname(target)
        if os.path.isfile(target) and os.path.isdir(folder):
            os.startfile(target, cwd=folder)
        else:
            os.startfile(target)   # a URI has no folder to start in
        return 0, ""
    except Exception as e:
        return -1, str(e)


# --------------------------------------------------------------------------
# Action implementations. Each returns (ok, text, code).
# --------------------------------------------------------------------------

def _schedule(flag, word_key, delay, lang):
    # Windows implies /f when /t is above zero, but at /t 0 a single unsaved
    # document would stall the shutdown.
    rc, err = run_cmd(["shutdown", flag, "/t", str(delay), "/f"])
    if rc != 0:
        return False, err or t("err.timer_failed", lang), rc
    what = t(word_key, lang)
    if delay > 0:
        # Store the key, not the translation: the countdown may be watched
        # from devices set to different languages.
        state.set_pending("shutdown" if flag == "/s" else "reboot", word_key, delay)
        return True, t("res.scheduled", lang, what=what, delay=delay), None
    state.clear()
    return True, t("res.now", lang, what=what), None


def do_shutdown(delay, lang=None):
    return _schedule("/s", "word.shutdown", delay, lang)


def do_reboot(delay, lang=None):
    return _schedule("/r", "word.reboot", delay, lang)


def do_cancel(_delay, lang=None):
    rc, err = run_cmd(["shutdown", "/a"])
    state.clear()
    # 1116 means no shutdown was scheduled. Not a failure: an early version
    # returned 500 for it and showed a scary red error.
    if rc == 1116 or "1116" in err:
        return True, t("res.no_timer", lang), None
    if rc != 0:
        return False, err or t("err.cancel_failed", lang), rc
    return True, t("res.cancelled", lang), None


def _simple(args, ok_key, fail_key):
    """A command that completes and returns control."""
    def run(_delay, lang=None):
        rc, err = run_cmd(args)
        if rc != 0:
            return False, err or t(fail_key, lang), rc
        return True, t(ok_key, lang), None
    return run


def do_sleep(_delay, lang=None):
    # Hibernates instead of sleeping when hibernation is enabled.
    # For real sleep: powercfg /hibernate off
    rc, err = run_detached(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    if rc != 0:
        return False, err or t("err.sleep_failed", lang), rc
    return True, t("res.sleeping", lang), None


def _detached(args, ok_key, fail_key):
    """An action after which the machine or the session goes down."""
    def run(_delay, lang=None):
        rc, err = run_detached(args)
        if rc != 0:
            return False, err or t(fail_key, lang), rc
        return True, t(ok_key, lang), None
    return run


def _wrap(fn, ok_key):
    """A direct WinAPI call or a program launch."""
    def run(_delay, lang=None):
        rc, err = fn()
        return (True, t(ok_key, lang), None) if rc == 0 else (False, err, rc)
    return run


# --------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Action:
    id: str
    icon: str
    group: str
    run: Callable
    tone: str = "neutral"       # "danger" for irreversible, otherwise accent
    delay: bool = False         # accepts a delay
    confirm: bool = False       # ask for confirmation in the UI
    locked: bool = False        # cannot be disabled: integrations depend on it
    default_on: bool = True
    # Custom buttons: the name came from a person, nothing to translate
    fixed_label: str = ""
    fixed_hint: str = ""
    # The hint is a path on this disk: it goes to the settings page, which
    # asks for a password, and never to the open catalog
    private_hint: bool = False

    def label(self, lang=None):
        return self.fixed_label or t(f"{self.id}.label", lang)

    def hint(self, lang=None):
        return self.fixed_hint or t(f"{self.id}.hint", lang)


GROUPS = ["power", "session", "media", "apps"]

CATALOG = [
    Action("shutdown", "power", "power", do_shutdown,
           tone="danger", delay=True, confirm=True, locked=True),
    Action("reboot", "restart", "power", do_reboot,
           tone="danger", delay=True, confirm=True, locked=True),
    Action("cancel", "cancel", "power", do_cancel, locked=True),
    Action("sleep", "sleep", "power", do_sleep, confirm=True),
    Action("hibernate", "hibernate", "power",
           _detached(["shutdown", "/h"], "res.hibernating", "err.generic_failed"),
           tone="danger", confirm=True, default_on=False),

    Action("lock", "lock", "session",
           _simple(["rundll32.exe", "user32.dll,LockWorkStation"],
                   "res.locked", "err.lock_failed")),
    Action("logoff", "logout", "session",
           _detached(["shutdown", "/l"], "res.signing_out", "err.generic_failed"),
           tone="danger", confirm=True, default_on=False),
    Action("monitors_off", "monitor-off", "session",
           _wrap(lambda: _monitor_power(False), "res.monitors_off")),
    Action("monitors_on", "monitor-on", "session",
           _wrap(lambda: _monitor_power(True), "res.monitors_on")),

    Action("mute", "mute", "media", _wrap(lambda: _tap_key(VK_MUTE), "res.muted")),
    Action("vol_down", "volume-down", "media",
           _wrap(lambda: _tap_key(VK_VOL_DOWN, 4), "res.vol_down")),
    Action("vol_up", "volume-up", "media",
           _wrap(lambda: _tap_key(VK_VOL_UP, 4), "res.vol_up")),

    Action("bigpicture", "steam", "apps",
           _wrap(lambda: _start("steam://open/bigpicture"), "res.launching")),
]

BY_ID = {a.id: a for a in CATALOG}


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}


def _slug(name):
    """ASCII slug for any name.

    Without transliteration non-Latin names were stripped entirely and every
    such button collapsed onto the same id, so only the first one worked.
    """
    text = "".join(_TRANSLIT.get(ch, ch) for ch in name.lower())
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "app"


def _launchers():
    """Custom buttons from the settings. Their ids always carry a launch:
    prefix so they can never collide with the built-in ones."""
    out = []
    used = set()
    for item in config.load().get("launchers", []):
        name = str(item.get("name", "")).strip()
        target = str(item.get("target", "")).strip()
        if not name or not target:
            continue
        slug = base = _slug(name)
        n = 2
        while slug in used:          # duplicate names happen too
            slug, n = f"{base}_{n}", n + 1
        used.add(slug)
        out.append(Action(
            f"launch:{slug}", item.get("icon") or "app", "apps",
            _wrap(lambda tg=target: _start(tg), "res.launching"),
            fixed_label=name, fixed_hint=target[:60], private_hint=True,
        ))
    return out


def all_actions():
    return CATALOG + _launchers()


def get(action_id):
    for a in all_actions():
        if a.id == action_id:
            return a
    return None


def is_enabled(action):
    if action.locked:
        return True  # integrations depend on it, nothing to disable
    return config.action_enabled(action.id, action.default_on)


def groups(lang=None):
    return [{"id": g, "title": t(f"group.{g}", lang)} for g in GROUPS]


def describe(action, lang=None, reveal=False):
    """What goes to the interface. `reveal` is for authenticated callers."""
    return {
        "id": action.id,
        "label": action.label(lang),
        "hint": action.hint(lang) if reveal or not action.private_hint
                else t("word.custom_button", lang),
        "icon": action.icon,
        "group": action.group,
        "tone": action.tone,
        "delay": action.delay,
        "confirm": action.confirm,
        "locked": action.locked,
        "enabled": is_enabled(action),
    }


def execute(action, delay, lang=None):
    """(ok, text, code). An exception inside an action must not kill the server."""
    try:
        ok, text, rc = action.run(delay, lang)
        # A launch button reports the name a person gave it
        if "{name}" in text:
            text = text.replace("{name}", action.label(lang))
        return ok, text, rc
    except Exception as e:
        log.exception("Action %s crashed", action.id)
        return False, str(e), -1
