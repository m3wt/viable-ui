# SPDX-License-Identifier: GPL-2.0-or-later
"""
One-shot change tracking for ChangeManager.

The one-shot UI is integrated into QmkSettings as a tab.
"""


class OneShotChange:
    """Change object for one-shot settings."""

    def __init__(self, old_timeout, new_timeout, old_tap_toggle, new_tap_toggle):
        self.old_timeout = old_timeout
        self.new_timeout = new_timeout
        self.old_tap_toggle = old_tap_toggle
        self.new_tap_toggle = new_tap_toggle

    def key(self):
        return ('oneshot',)

    def apply(self, keyboard):
        keyboard._commit_oneshot(self.new_timeout, self.new_tap_toggle)

    def revert(self, keyboard):
        keyboard._commit_oneshot(self.old_timeout, self.old_tap_toggle)

    def restore_local(self, keyboard, use_old):
        if use_old:
            keyboard.oneshot_timeout = self.old_timeout
            keyboard.oneshot_tap_toggle = self.old_tap_toggle
        else:
            keyboard.oneshot_timeout = self.new_timeout
            keyboard.oneshot_tap_toggle = self.new_tap_toggle

    def merge(self, other):
        self.new_timeout = other.new_timeout
        self.new_tap_toggle = other.new_tap_toggle
        return True
