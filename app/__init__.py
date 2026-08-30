# -*- coding: utf-8 -*-
"""pc-remote — web remote for a Windows PC.

Entry points: run.pyw when running from source, main.py in the frozen build.

Modules:
    config    settings in data/config.json, edited from the web UI
    actions   action catalog; adding a button is one entry there
    security  network allow-list, password, integration tokens
    state     scheduled shutdown, thread-safe and survives a restart
    i18n      server-side strings
    server    Flask app and the HTTP contract
"""

__version__ = "1.1.0"
__all__ = ["__version__"]
