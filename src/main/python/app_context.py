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


def _get_dist_dir():
    """Get the distribution directory (where resources are located)."""
    try:
        # Nuitka: try containing_dir first, fall back to executable directory
        dist_dir = __compiled__.containing_dir
        if not os.path.exists(os.path.join(dist_dir, 'build_settings.json')):
            # containing_dir can be wrong in some cases, use executable dir
            dist_dir = os.path.dirname(sys.executable)
        return dist_dir
    except NameError:
        # Development: resources are in src/main/resources/base
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(script_dir, '..', 'resources', 'base'))


def _get_build_settings_path():
    """Get the path to build settings."""
    try:
        __compiled__  # Check if we're compiled
        return os.path.join(_get_dist_dir(), 'build_settings.json')
    except NameError:
        # Development path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(script_dir, '..', '..', 'build', 'settings', 'base.json'))


def is_frozen():
    """Check if running as a Nuitka compiled executable."""
    try:
        return bool(__compiled__)
    except NameError:
        return False


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
        return os.path.join(_get_dist_dir(), name)
