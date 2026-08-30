# -*- coding: utf-8 -*-
"""Entry point with commands.

The same file works from source and as a frozen build:

    pc-remote.exe              run the remote
    pc-remote.exe --install    register autostart and start
    pc-remote.exe --uninstall  remove autostart
    pc-remote.exe --status     print status and exit

A build needs nothing installed: the interpreter and the libraries are
inside. That removes an entire class of failures — a second Python
appearing on the machine and becoming the default.
"""

import os
import sys
import traceback


def _panic(text):
    """Last resort. A silent crash is the only truly nasty failure in this
    project, so write the traceback somewhere no matter what."""
    try:
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "data", "CRASH.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        pass


def _say(text):
    """Printing only works when there is somewhere to print: a windowed
    build and pythonw have no stdout."""
    try:
        if sys.stdout:
            print(text)
    except Exception:
        pass


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])

    from app import config
    from app.logging_setup import setup

    log = setup(config.load()["log_level"])

    if "--install" in argv:
        from app import autostart
        ok, msg = autostart.install()
        _say(msg)
        if not ok:
            return 1
        argv = [a for a in argv if a != "--install"]  # then start right away

    if "--uninstall" in argv:
        from app import autostart
        ok, msg = autostart.uninstall()
        _say(msg)
        return 0 if ok else 1

    if "--status" in argv:
        import json
        from app import autostart
        _say(json.dumps({
            "version": __import__("app").__version__,
            "project_dir": config.PROJECT_DIR,
            "port": config.load()["port"],
            "autostart": autostart.status(),
        }, ensure_ascii=False, indent=2))
        return 0

    try:
        from app.server import main as serve
        return serve()
    except Exception:
        log.critical("CRASH ON STARTUP:\n%s", traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        _panic(traceback.format_exc())
        raise
