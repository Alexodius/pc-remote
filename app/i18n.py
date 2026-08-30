# -*- coding: utf-8 -*-
"""Server-side strings.

The interface is translated in the browser (static/i18n.js), but part of the
text comes from the server and cannot be assembled there: action labels, group
titles and replies such as "Timer cancelled".

The language is decided per request — a phone and a desktop may well be set to
different ones. Whatever lives outside a browser (smart-home entity names, the
tray menu) uses the single language from the settings, because there is nobody
to ask.
"""

from . import config

DEFAULT = "en"
SUPPORTED = ("ru", "en")   # order matches the tuples below

STRINGS = {
    # ---- action labels: <id>.label / <id>.hint ----
    "shutdown.label": ("Выключить", "Shut down"),
    "shutdown.hint": ("Завершение работы", "Power off the computer"),
    "reboot.label": ("Перезагрузить", "Restart"),
    "reboot.hint": ("Рестарт системы", "Restart the system"),
    "cancel.label": ("Отменить", "Cancel"),
    "cancel.hint": ("Снять запланированное выключение", "Call off a scheduled shutdown"),
    "sleep.label": ("Сон", "Sleep"),
    "sleep.hint": ("Спящий режим", "Suspend to memory"),
    "hibernate.label": ("Гибернация", "Hibernate"),
    "hibernate.hint": ("Дамп памяти на диск и выключение", "Dump memory to disk and power off"),
    "lock.label": ("Заблокировать", "Lock"),
    "lock.hint": ("Экран блокировки Windows", "Windows lock screen"),
    "logoff.label": ("Выйти", "Sign out"),
    "logoff.hint": ("Завершить сеанс пользователя", "End the user session"),
    "monitors_off.label": ("Экраны выкл", "Displays off"),
    "monitors_off.hint": ("Погасить мониторы", "Turn the monitors off"),
    "monitors_on.label": ("Экраны вкл", "Displays on"),
    "monitors_on.hint": ("Разбудить мониторы", "Wake the monitors"),
    "mute.label": ("Тишина", "Mute"),
    "mute.hint": ("Переключить звук", "Toggle sound"),
    "vol_down.label": ("Тише", "Volume down"),
    "vol_down.hint": ("Убавить на 4 шага", "Down by 4 steps"),
    "vol_up.label": ("Громче", "Volume up"),
    "vol_up.hint": ("Прибавить на 4 шага", "Up by 4 steps"),
    "bigpicture.label": ("Big Picture", "Big Picture"),
    "bigpicture.hint": ("Steam в режиме телевизора", "Steam in TV mode"),

    # ---- groups ----
    "word.custom_button": ("Пользовательская кнопка", "Custom button"),
    "group.power": ("Питание", "Power"),
    "group.session": ("Сеанс", "Session"),
    "group.media": ("Звук", "Sound"),
    "group.apps": ("Программы", "Apps"),

    # ---- action replies ----
    "word.shutdown": ("Выключение", "Shutdown"),
    "word.reboot": ("Перезагрузка", "Restart"),
    "res.scheduled": ("{what} через {delay} с. Можно отменить.",
                      "{what} in {delay} s. You can still cancel."),
    "res.now": ("{what} прямо сейчас!", "{what} right now!"),
    "res.cancelled": ("Таймер отменён", "Timer cancelled"),
    "res.no_timer": ("Таймер и так не запущен", "No timer was running anyway"),
    "res.sleeping": ("Ухожу в сон", "Going to sleep"),
    "res.hibernating": ("Ухожу в гибернацию", "Going into hibernation"),
    "res.signing_out": ("Выхожу из системы", "Signing out"),
    "res.locked": ("Экран заблокирован", "Screen locked"),
    "res.monitors_off": ("Мониторы погашены", "Monitors turned off"),
    "res.monitors_on": ("Мониторы разбужены", "Monitors woken up"),
    "res.muted": ("Звук переключён", "Sound toggled"),
    "res.vol_down": ("Убавил", "Turned down"),
    "res.vol_up": ("Прибавил", "Turned up"),
    "res.launching": ("{name} запускается", "{name} is starting"),
    "res.state_online": ("В сети", "Online"),
    "res.state_pending": ("{what} через {left} с", "{what} in {left} s"),

    # ---- smart-home entity names ----
    "entity.countdown": ("До выключения", "Shutdown in"),
    "entity.uptime": ("Аптайм", "Uptime"),
    "entity.status": ("Состояние", "Status"),
    "entity.agent": ("Пульт", "Remote"),

    # ---- tray menu ----
    "tray.open": ("Открыть пульт", "Open the remote"),
    "tray.settings": ("Настройки", "Settings"),
    "tray.log": ("Журнал", "Log"),
    "tray.autostart": ("Запускать при входе", "Start at sign-in"),
    "tray.quit": ("Выход", "Quit"),
    "tray.cancel": ("Отменить: {what}", "Cancel: {what}"),
    "tray.online": ("в сети", "online"),
    "tray.failed": ("Не вышло: {detail}", "Failed: {detail}"),

    # ---- settings replies ----
    "adm.saved": ("Сохранено", "Saved"),
    "adm.token_issued": ("Токен выпущен", "Token issued"),
    "adm.token_revoked": ("Токен отозван", "Token revoked"),
    "adm.token_missing": ("Токен не найден", "Token not found"),
    "adm.password_changed": (
        "Пароль изменён. Интеграции, которые ходили с ним, "
        "нужно перевести на токены или обновить вручную.",
        "Password changed. Integrations that used it need to move to a token "
        "or be updated by hand."),
    "adm.password_short": ("Пароль короче 4 символов", "Password shorter than 4 characters"),
    "setup.done": ("Пароль сохранён", "Password saved"),
    "setup.taken": ("Пароль уже задан", "The password is already set"),
    "adm.restarting": ("Перезапускаюсь, вернусь через пару секунд",
                       "Restarting, back in a couple of seconds"),
    "adm.restart_failed": ("Не удалось перезапустить: {detail}",
                           "Could not restart: {detail}"),
    "adm.bridge_up": ("Мост поднят, проверьте состояние", "Bridge is up, check the status"),
    "adm.bridge_down": ("Не поднялся: {detail}", "Did not come up: {detail}"),
    "adm.bridge_off": ("выключен в настройках", "disabled in the settings"),
    "adm.unknown_op": ("Неизвестная операция", "Unknown operation"),

    # ---- units ----
    "unit.uptime": ("{h} ч {m} мин", "{h}h {m}m"),
    "unit.uptime_days": ("{d} д {h} ч {m} мин", "{d}d {h}h {m}m"),

    # ---- errors ----
    "err.timer_failed": ("не удалось запустить таймер", "could not start the timer"),
    "err.cancel_failed": ("не удалось отменить", "could not cancel"),
    "err.sleep_failed": ("не удалось усыпить", "could not suspend"),
    "err.lock_failed": ("не удалось заблокировать", "could not lock"),
    "err.generic_failed": ("не удалось", "failed"),
    "err.no_reply": ("система не приняла команду", "the system refused the command"),
    "err.wrong_password": ("Неверный пароль", "Wrong password"),
    "err.unknown_action": ("Неизвестная команда", "Unknown command"),
    "err.action_disabled": ("Действие отключено в настройках", "Action is disabled in settings"),
    "err.denied": ("Отказано", "Denied"),
    "err.locked_out": ("Заблокировано ещё {sec} с", "Locked out for another {sec} s"),
    "err.system": ("Ошибка системы: {detail}", "System error: {detail}"),
}


def normalize(lang):
    if not lang:
        return DEFAULT
    code = str(lang).strip().lower().replace("_", "-").split("-")[0]
    return code if code in SUPPORTED else DEFAULT


def default_language():
    """Language for everything outside a browser: smart home and tray menu."""
    return normalize(config.load().get("language", DEFAULT))


def from_request(request):
    """Language for a single request.

    Order: an explicit parameter, then what the browser asks for, then the
    global setting. Decided per request rather than once at startup.
    """
    data = request.get_json(silent=True) or {}
    explicit = data.get("lang") or request.args.get("lang")
    if explicit:
        return normalize(explicit)

    header = request.headers.get("Accept-Language", "")
    for part in header.split(","):
        code = normalize(part.split(";")[0])
        if code in SUPPORTED and part.strip():
            first = part.split(";")[0].strip().lower()
            if first.split("-")[0] in SUPPORTED:
                return code
    return default_language()


def t(key, lang=None, **fmt):
    """A string by key. An unknown key is returned as-is: visible in the
    interface, which beats silent emptiness."""
    lang = normalize(lang or default_language())
    pair = STRINGS.get(key)
    if pair is None:
        return key
    text = pair[SUPPORTED.index(lang)]
    return text.format(**fmt) if fmt else text
