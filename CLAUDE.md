# pc-remote — project notes

Web remote for a Windows PC. See [README.md](README.md) for the whole picture;
this file holds only the things that are easy to get burned by.

## Rules that must not be broken

**The `POST /api` contract is frozen.** The `password` / `action` / `delay`
fields, the 403/400/500 codes and the "no `delay` means 30 seconds" rule.
External integrations depend on it and they break silently. The `shutdown`,
`reboot` and `cancel` actions are marked `locked=True` and cannot be disabled
from the settings — that is not a bug.

**Run only the interpreter that has the dependencies.** The autostart task
stores the full path captured from `sys.executable`; the `#!python3` shebang in
`run.pyw` is the second layer. The project already lost the ability to start
once: a second Python appeared, became the default for `pyw.exe`, and autostart
failed on import for weeks without a trace. Never hardcode an interpreter path
in a script — `PC_REMOTE_PYTHON` is the override.

**No `print`.** There is no stdout or stderr under `pythonw`. Anything not
written to `data/server.log` is gone. Every new place that can fail gets
logging around it.

**Dependencies.** Two are required: `flask` and `waitress`. The rest
(`paho-mqtt`, `pystray`, `pillow`) are optional — the code checks the import
and works without them, just without that feature. Add new ones the same way:
with a check and a graceful downgrade, not a crash.

**Everything user-facing is written for a stranger.** No names of specific
entities, no addresses, no third-party service names in comments or in the
interface. Installation specifics belong in the settings, not in the code.

## Landmarks

- A new action is one entry in `CATALOG` in `app/actions.py`. The interface,
  the API and smart-home discovery build themselves from it.
- Labels and replies are keys, not text. English source strings live in
  `app/static/i18n.js` (interface) and `app/i18n.py` (server).
- Settings are `data/config.json`, edited through `/admin`, never in git. The
  config is cached in memory: editing the file from outside needs a restart.
- The tray icon must own the main thread, so the web server runs on a
  background one (`server.main`). Callables pystray uses as menu text receive
  `item` as an argument: the signature must be `def f(item=None)`.
- Styling follows `docs/design.md`; the tokens are in `:root` in `style.css`.
- Bump the version in `app/__init__.py` when touching the front end — it goes
  into the `?v=` on CSS and JS links, or clients serve stale files.
- `schtasks /query /xml` piped to a program emits single-byte OEM text while
  declaring UTF-16. Trust the BOM, not the declaration.

## After changing anything

```powershell
python -m unittest discover -s tests
schtasks /end /tn pc-remote; schtasks /run /tn pc-remote
Get-Content data\server.log -Encoding UTF8 -Tail 20
```
