# SPDX-License-Identifier: GPL-2.0-or-later
"""
Tap dance protocol implementation using Viable 0xDF protocol.

Tap dance entry format (10 bytes):
    on_tap: keycode for single tap (uint16)
    on_hold: keycode for hold (uint16)
    on_double_tap: keycode for double tap (uint16)
    on_tap_hold: keycode for tap then hold (uint16)
    custom_tapping_term: bit 15 = enabled, bits 0-14 = custom timing (uint16)
"""
import struct

from keycodes.keycodes import Keycode, RESET_KEYCODE
from protocol.base_protocol import BaseProtocol
from protocol.constants import VIABLE_TAP_DANCE_GET, VIABLE_TAP_DANCE_SET
from unlocker import Unlocker


class ProtocolTapDance(BaseProtocol):

    def reload_tap_dance(self):
        """Load all tap dance entries from keyboard using Viable protocol."""
        self.tap_dance_entries = []
        for idx in range(self.tap_dance_count):
            data = self.wrapper.send_viable(
                struct.pack("BB", VIABLE_TAP_DANCE_GET, idx),
                retries=20
            )
            # Response: [0xDF] [0x01] [index] [10 bytes of tap_dance_entry]
            entry = struct.unpack("<HHHHH", data[3:13])
            # Serialize keycodes for GUI display
            self.tap_dance_entries.append((
                Keycode.serialize(entry[0]),
                Keycode.serialize(entry[1]),
                Keycode.serialize(entry[2]),
                Keycode.serialize(entry[3]),
                entry[4]  # custom_tapping_term (bit 15 = enabled)
            ))

    def tap_dance_get(self, idx):
        """Get a tap dance entry by index."""
        return self.tap_dance_entries[idx]

    def tap_dance_set(self, idx, entry):
        """Set a tap dance entry."""
        if self.tap_dance_entries[idx] == entry:
            return
        for x in range(4):
            if entry[x] == RESET_KEYCODE:
                Unlocker.unlock(self)
        self.tap_dance_entries[idx] = entry
        raw_entry = [
            Keycode.deserialize(entry[0]),
            Keycode.deserialize(entry[1]),
            Keycode.deserialize(entry[2]),
            Keycode.deserialize(entry[3]),
            entry[4]
        ]
        serialized = struct.pack("<HHHHH", *raw_entry)
        self.wrapper.send_viable(
            struct.pack("BB", VIABLE_TAP_DANCE_SET, idx) + serialized,
            retries=20
        )

    def _commit_tap_dance(self, idx, entry):
        """Send a tap dance change to the device (used by ChangeManager)."""
        for x in range(4):
            if entry[x] == RESET_KEYCODE:
                Unlocker.unlock(self)
        self.tap_dance_entries[idx] = entry
        raw_entry = [
            Keycode.deserialize(entry[0]),
            Keycode.deserialize(entry[1]),
            Keycode.deserialize(entry[2]),
            Keycode.deserialize(entry[3]),
            entry[4]
        ]
        serialized = struct.pack("<HHHHH", *raw_entry)
        self.wrapper.send_viable(
            struct.pack("BB", VIABLE_TAP_DANCE_SET, idx) + serialized,
            retries=20
        )
        return True

    def save_tap_dance(self):
        """Save tap dance entries for layout file (.viable format)."""
        result = []
        for entry in self.tap_dance_entries:
            term_raw = entry[4]
            result.append({
                "on": bool(term_raw & 0x8000),
                "on_tap": entry[0],
                "on_hold": entry[1],
                "on_double_tap": entry[2],
                "on_tap_hold": entry[3],
                "tapping_term": term_raw & 0x7FFF
            })
        return result

    def restore_tap_dance(self, data, is_vil=False):
        """Restore tap dance entries from layout file.

        Args:
            data: List of tap dance entries (dict for .viable, tuple/list for .vil)
            is_vil: If True, assume entries are enabled when 'on' is not specified
        """
        for x, e in enumerate(data):
            if x >= self.tap_dance_count:
                break

            if isinstance(e, dict):
                # New .viable format with explicit fields
                on = e.get("on", True if is_vil else False)
                term = e.get("tapping_term", 0) & 0x7FFF
                if on:
                    term |= 0x8000
                entry = (
                    e.get("on_tap", "KC_NO"),
                    e.get("on_hold", "KC_NO"),
                    e.get("on_double_tap", "KC_NO"),
                    e.get("on_tap_hold", "KC_NO"),
                    term
                )
            else:
                # Old array format (from .vil files)
                # For .vil, assume enabled since vial-gui has no enable/disable
                if is_vil and len(e) == 5:
                    term = (e[4] & 0x7FFF) | 0x8000  # Force enabled
                    entry = (e[0], e[1], e[2], e[3], term)
                else:
                    entry = tuple(e)

            self.tap_dance_set(x, entry)
