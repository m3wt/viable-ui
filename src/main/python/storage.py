# SPDX-License-Identifier: GPL-2.0-or-later
"""Unified settings persistence for desktop and web."""
import sys

if sys.platform == "emscripten":
    import vialglue
    _cache = {}  # Populated at startup from JS

    def init(settings_dict):
        """Called from webmain with settings read from localStorage."""
        global _cache
        _cache = settings_dict

    def get(key, default=None):
        return _cache.get(key, default)

    def set(key, value):
        _cache[key] = value
        vialglue.storage_set(key, str(value))
else:
    from PyQt5.QtCore import QSettings
    _settings = QSettings("Vial", "Vial")

    def init(settings_dict=None):
        pass  # No-op on desktop

    def get(key, default=None):
        return _settings.value(key, default)

    def set(key, value):
        _settings.setValue(key, value)
