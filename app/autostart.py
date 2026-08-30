# -*- coding: utf-8 -*-
"""Autostart: a Task Scheduler task the remote manages itself.

Why the scheduler and not the Startup folder or a Run registry key: only it
offers a start delay (letting the network come up), restart on failure and no
execution time limit. A task for the current user needs no administrator
rights.

The interpreter path is taken from sys.executable and baked into the task on
purpose: .pyw opens through pyw.exe, which picks the default Python, and the
remote once failed to start silently after a second Python was installed.
"""

import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from . import config
from .logging_setup import log

TASK_NAME = "pc-remote"
CREATE_NO_WINDOW = 0x08000000
DETACHED = 0x00000008 | CREATE_NO_WINDOW


def _run(args):
    p = subprocess.run(args, capture_output=True, creationflags=CREATE_NO_WINDOW)
    out = p.stdout.decode("cp866", errors="replace")
    err = p.stderr.decode("cp866", errors="replace")
    return p.returncode, out, err


def frozen():
    """Frozen build: interpreter and libraries are already inside."""
    return bool(getattr(sys, "frozen", False))


def interpreter():
    """What to launch: the exe itself when frozen, otherwise the pythonw of
    the environment we are running in."""
    exe = sys.executable
    if frozen():
        return exe
    if os.path.basename(exe).lower() == "python.exe":
        windowless = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(windowless):
            return windowless
    return exe


def script():
    """What to run. A frozen build takes no arguments: it is its own script."""
    return "" if frozen() else os.path.join(config.PROJECT_DIR, "run.pyw")


def _arguments():
    return f'"{script()}"' if script() else ""


def _xml():
    user = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>{user}</Author>
    <Description>pc-remote — web remote for this computer. Log: {config.LOG_FILE}</Description>
    <URI>\\{TASK_NAME}</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{user}</UserId>
      <Delay>PT15S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{interpreter()}</Command>
      <Arguments>{_arguments()}</Arguments>
      <WorkingDirectory>{config.PROJECT_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _query_xml():
    """The task definition as text, or None when it does not exist.

    A trap: piped schtasks emits single-byte OEM text while declaring
    encoding="UTF-16" inside. Trust the BOM, not the declaration — otherwise
    utf-16 "successfully" decodes the bytes into gibberish.
    """
    p = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME, "/xml", "ONE"],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
    if p.returncode != 0:
        return None
    raw = p.stdout
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    for enc in ("utf-8", "cp866", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def status():
    """What is currently registered in Task Scheduler."""
    text = _query_xml()
    if text is None:
        return {"installed": False, "enabled": False, "command": None,
                "stale": False, "task": TASK_NAME}

    # ElementTree refuses a str carrying an encoding declaration, and this
    # one always has it and always lies. Strip it.
    body = re.sub(r"^\s*<\?xml.*?\?>", "", text, count=1, flags=re.S)

    command = args = None
    enabled = True
    try:
        root = ET.fromstring(body)
        node = root.find(".//{*}Command")
        command = (node.text or "").strip() if node is not None else None
        node = root.find(".//{*}Arguments")
        args = (node.text or "").strip() if node is not None else None
        node = root.find(".//{*}Settings/{*}Enabled")
        enabled = (node is None) or (node.text or "true").strip().lower() == "true"
    except (ET.ParseError, ValueError):
        m = re.search(r"<Command>(.*?)</Command>", text, re.S)
        command = m.group(1).strip() if m else None
        m = re.search(r"<Arguments>(.*?)</Arguments>", text, re.S)
        args = m.group(1).strip() if m else None

    # The project may have moved or the interpreter changed: the task then
    # exists but points nowhere, which has to be surfaced.
    stale = (command or "").lower() != interpreter().lower()
    if script():
        stale = stale or script().lower() not in (args or "").lower()

    return {
        "installed": True,
        "enabled": enabled,
        "command": f"{command} {args}".strip() if command else None,
        "expected": f"{interpreter()} {_arguments()}".strip(),
        "stale": stale,
        "task": TASK_NAME,
    }


def install():
    """Create or update the task. Idempotent."""
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(_xml().encode("utf-16"))
        rc, out, err = _run(["schtasks", "/create", "/tn", TASK_NAME, "/xml", path, "/f"])
    finally:
        os.unlink(path)
    if rc != 0:
        log.error("Could not create the autostart task: %s", (err or out).strip())
        return False, (err or out).strip() or "schtasks returned an error"
    log.warning("Autostart enabled: %s %s", interpreter(), _arguments())
    return True, "Autostart enabled"


def uninstall():
    """Delete the task. The running process is left alone: turning autostart
    off must not take down a working remote."""
    rc, out, err = _run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"])
    if rc != 0:
        return False, (err or out).strip() or "schtasks returned an error"
    log.warning("Autostart disabled, task %s removed", TASK_NAME)
    return True, "Autostart disabled. The running process keeps working."


def restart_service():
    """Restart the remote. /end would kill us, so the command runs in a
    detached process that outlives its own parent."""
    if status()["installed"]:
        cmd = (f"schtasks /end /tn {TASK_NAME} & timeout /t 2 /nobreak >nul & "
               f"schtasks /run /tn {TASK_NAME}")
    else:
        # Autostart is off, so relaunch ourselves directly.
        tail = f' "{script()}"' if script() else ""
        cmd = (f'taskkill /pid {os.getpid()} /f & timeout /t 2 /nobreak >nul & '
               f'start "" "{interpreter()}"{tail}')
    subprocess.Popen(["cmd", "/c", cmd], creationflags=DETACHED, close_fds=True)


if __name__ == "__main__":
    # Used by install.ps1 so the task XML lives in exactly one place.
    sys.path.insert(0, os.path.dirname(config.PROJECT_DIR))
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "install":
        ok, msg = install()
    elif action == "uninstall":
        ok, msg = uninstall()
    else:
        ok, msg = True, str(status())
    print(msg)
    sys.exit(0 if ok else 1)
