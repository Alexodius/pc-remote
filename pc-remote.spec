# -*- mode: python ; coding: utf-8 -*-
"""Build the executable.

    py -3 -m PyInstaller pc-remote.spec --noconfirm

Built as a folder rather than a single file, on purpose:

* a one-file exe unpacks itself into a temporary directory on every run
  and starts noticeably slower;
* more importantly, antivirus software is far more suspicious of packed
  single files, and a program that can shut the computer down would look
  particularly convincing in quarantine.

No console window: the remote is a background service and everything
worth seeing goes to the log.
"""

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    # Templates and static files are not imported, so they are added by
    # hand; without this Flask finds no pages at all
    datas=[
        ("app/templates", "app/templates"),
        ("app/static", "app/static"),
    ],
    hiddenimports=[
        # Optional features: PyInstaller cannot see them behind try/except
        "paho.mqtt.client",
        "pystray._win32",
        "PIL.Image",
        "PIL.ImageDraw",
        "waitress",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc", "doctest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pc-remote",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX upsets antivirus software even more
    console=False,      # background service, no window needed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="app/static/icon.ico" if __import__("os").path.exists("app/static/icon.ico") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="pc-remote",
)
