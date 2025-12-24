# SPDX-License-Identifier: GPL-2.0-or-later
"""
Standalone application context - replaces fbs_runtime for Nuitka builds.
Provides the same interface as fbs ApplicationContext.
"""
import json
import os
import sys

from PySide6 import QtWidgets


def cached_property(func):
    """Simple cached property decorator."""
    attr_name = '_cached_' + func.__name__

    @property
    def wrapper(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, func(self))
        return getattr(self, attr_name)
    return wrapper


def _get_exe_dir():
    """Get directory containing the executable."""
    return os.path.dirname(sys.executable)


def _get_script_dir():
    """Get directory containing this script."""
    return os.path.dirname(os.path.abspath(__file__))


def _get_build_settings_path():
    """Get the path to build settings."""
    # Check frozen location first (next to executable)
    frozen_path = os.path.join(_get_exe_dir(), 'build_settings.json')
    if os.path.exists(frozen_path):
        return frozen_path
    # Development path
    return os.path.normpath(os.path.join(_get_script_dir(), '..', '..', 'build', 'settings', 'base.json'))


def _get_application_path():
    """Get the path to the application directory (resources)."""
    # Check frozen location first (resources next to executable)
    exe_dir = _get_exe_dir()
    # In frozen mode, resources are copied to exe directory
    if os.path.exists(os.path.join(exe_dir, 'build_settings.json')):
        return exe_dir
    # Development path
    return os.path.normpath(os.path.join(_get_script_dir(), '..', 'resources', 'base'))


def is_frozen():
    """Check if running as a frozen executable."""
    return os.path.exists(os.path.join(_get_exe_dir(), 'build_settings.json'))


class ApplicationContext:
    """
    Standalone application context that mimics fbs ApplicationContext.
    """

    def __init__(self):
        self._build_settings = None

    @cached_property
    def app(self):
        return QtWidgets.QApplication(sys.argv)

    @property
    def build_settings(self):
        if self._build_settings is None:
            settings_path = _get_build_settings_path()
            with open(settings_path, 'r') as f:
                self._build_settings = json.load(f)
        return self._build_settings

    def get_resource(self, name):
        """Get the path to a resource file."""
        return os.path.join(_get_application_path(), name)
