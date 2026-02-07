# SPDX-License-Identifier: GPL-2.0-or-later
"""
Viable protocol (0xDF) implementation for global settings and commands.

Tap dance, combos, key overrides, and alt repeat keys are handled by
their respective protocol modules which already use VIABLE_* constants.
This module provides one-shot settings, save, and reset commands.
"""
import struct

from protocol.base_protocol import BaseProtocol
from protocol.constants import (
    VIABLE_ONESHOT_GET, VIABLE_ONESHOT_SET,
    VIABLE_SAVE, VIABLE_RESET
)


class ProtocolViable(BaseProtocol):
    """
    Viable protocol (0xDF) handler for one-shot settings.
    """

    def oneshot_get(self):
        """
        Get one-shot settings from keyboard.

        Returns tuple: (timeout_ms, tap_toggle)
        """
        response = self.wrapper.send_viable(
            struct.pack("B", VIABLE_ONESHOT_GET),
            retries=20
        )
        # Response: [0xDF] [0x09] [timeout_lo] [timeout_hi] [tap_toggle]
        timeout, tap_toggle = struct.unpack("<HB", response[2:5])
        return (timeout, tap_toggle)

    def oneshot_set(self, timeout, tap_toggle):
        """Set one-shot settings."""
        data = struct.pack("<HB", timeout, tap_toggle)
        self.wrapper.send_viable(
            struct.pack("B", VIABLE_ONESHOT_SET) + data,
            retries=20
        )

    def _commit_oneshot(self, timeout, tap_toggle):
        """Send one-shot settings to the device (used by ChangeManager)."""
        self.oneshot_set(timeout, tap_toggle)
        return True

    def save_oneshot(self):
        """Save one-shot settings for layout file."""
        if "oneshot" not in getattr(self, "supported_features", set()):
            return None
        # Return cached values, not from keyboard (may have pending changes)
        return (self.oneshot_timeout, self.oneshot_tap_toggle)

    def restore_oneshot(self, data):
        """Restore one-shot settings from layout file."""
        if data is None:
            return
        if "oneshot" not in getattr(self, "supported_features", set()):
            return
        timeout, tap_toggle = data
        self.oneshot_set(timeout, tap_toggle)

    def viable_save(self):
        """Explicitly save all Viable data to EEPROM."""
        self.wrapper.send_viable(
            struct.pack("B", VIABLE_SAVE),
            retries=20
        )

    def viable_reset(self):
        """
        Reset all dynamic features to defaults.
        Clears all tap dances, combos, key overrides, and alt repeat keys.
        """
        self.wrapper.send_viable(
            struct.pack("B", VIABLE_RESET),
            retries=20
        )
        # Reload dynamic feature data from keyboard
        self.reload_dynamic()
