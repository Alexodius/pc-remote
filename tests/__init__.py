# -*- coding: utf-8 -*-
"""pc-remote tests.

    python -m unittest discover -s tests -v

Rule number one: **tests never execute system commands.** The border with
Windows is `actions.run_cmd`, `actions.run_detached` and a handful of direct
WinAPI calls; all of them are replaced with a recorder that logs the call and
returns a fixed code. That verifies an action builds the right command line
while the machine does not sleep, restart or shut down.

No live server either: the HTTP layer is exercised through Flask's test client
in the same process.
"""
