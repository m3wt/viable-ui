# SPDX-License-Identifier: GPL-2.0-or-later
"""
Combo protocol implementation using Viable 0xDF protocol.

Combo entry format (12 bytes):
    input[4]: 4 trigger keycodes (uint16 each)
    output: output keycode (uint16)
    custom_combo_term: bit 15 = enabled, bits 0-14 = custom timing (uint16)
"""
import struct

from keycodes.keycodes import Keycode, RESET_KEYCODE
from protocol.base_protocol import BaseProtocol
from protocol.constants import VIABLE_COMBO_GET, VIABLE_COMBO_SET
from unlocker import Unlocker


class ProtocolCombo(BaseProtocol):

    def reload_combo(self):
        """Load all combo entries from keyboard using Viable protocol."""
        self.combo_entries = []
        for idx in range(self.combo_count):
            data = self.wrapper.send_viable(
                struct.pack("BB", VIABLE_COMBO_GET, idx),
                retries=20
            )
            # Response: [0xDF] [0x03] [index] [12 bytes of combo_entry]
            entry = struct.unpack("<HHHHHH", data[3:15])
            # Serialize keycodes for GUI display
            self.combo_entries.append((
                Keycode.serialize(entry[0]),
                Keycode.serialize(entry[1]),
                Keycode.serialize(entry[2]),
                Keycode.serialize(entry[3]),
                Keycode.serialize(entry[4]),
                entry[5]  # custom_combo_term (bit 15 = enabled)
            ))

    def combo_get(self, idx):
        """Get a combo entry by index."""
        return self.combo_entries[idx]

    def combo_set(self, idx, entry):
        """Set a combo entry."""
        if self.combo_entries[idx] == entry:
            return
        # Check for RESET keycode in output (index 4)
        if entry[4] == RESET_KEYCODE:
            Unlocker.unlock(self)
        self.combo_entries[idx] = entry
        raw_entry = [
            Keycode.deserialize(entry[0]),
            Keycode.deserialize(entry[1]),
            Keycode.deserialize(entry[2]),
            Keycode.deserialize(entry[3]),
            Keycode.deserialize(entry[4]),
            entry[5]  # custom_combo_term
        ]
        serialized = struct.pack("<HHHHHH", *raw_entry)
        self.wrapper.send_viable(
            struct.pack("BB", VIABLE_COMBO_SET, idx) + serialized,
            retries=20
        )

    def _commit_combo(self, idx, entry):
        """Send a combo change to the device (used by ChangeManager)."""
        if entry[4] == RESET_KEYCODE:
            Unlocker.unlock(self)
        self.combo_entries[idx] = entry
        raw_entry = [
            Keycode.deserialize(entry[0]),
            Keycode.deserialize(entry[1]),
            Keycode.deserialize(entry[2]),
            Keycode.deserialize(entry[3]),
            Keycode.deserialize(entry[4]),
            entry[5]
        ]
        serialized = struct.pack("<HHHHHH", *raw_entry)
        self.wrapper.send_viable(
            struct.pack("BB", VIABLE_COMBO_SET, idx) + serialized,
            retries=20
        )
        return True

    def save_combo(self):
        """Save combo entries for layout file (.viable format)."""
        result = []
        for entry in self.combo_entries:
            term_raw = entry[5]
            result.append({
                "on": bool(term_raw & 0x8000),
                "keys": [entry[0], entry[1], entry[2], entry[3]],
                "output": entry[4],
                "combo_term": term_raw & 0x7FFF
            })
        return result

    def restore_combo(self, data, is_vil=False):
        """Restore combo entries from layout file.

        Args:
            data: List of combo entries (dict for .viable, tuple/list for .vil)
            is_vil: If True, assume entries are enabled when 'on' is not specified
        """
        for x, e in enumerate(data):
            if x >= self.combo_count:
                break

            if isinstance(e, dict):
                # New .viable format with explicit fields
                on = e.get("on", True if is_vil else False)
                term = e.get("combo_term", 0) & 0x7FFF
                if on:
                    term |= 0x8000
                keys = e.get("keys", ["KC_NO", "KC_NO", "KC_NO", "KC_NO"])
                entry = (
                    keys[0] if len(keys) > 0 else "KC_NO",
                    keys[1] if len(keys) > 1 else "KC_NO",
                    keys[2] if len(keys) > 2 else "KC_NO",
                    keys[3] if len(keys) > 3 else "KC_NO",
                    e.get("output", "KC_NO"),
                    term
                )
            else:
                # Old array format (from .vil files)
                if len(e) == 5:
                    # Old 5-element format without combo_term
                    # For .vil, assume enabled since vial-gui has no enable/disable
                    entry = (e[0], e[1], e[2], e[3], e[4], 0x8000)
                elif is_vil and len(e) == 6:
                    # 6-element format but from .vil - force enabled
                    term = (e[5] & 0x7FFF) | 0x8000
                    entry = (e[0], e[1], e[2], e[3], e[4], term)
                else:
                    entry = tuple(e)

            self.combo_set(x, entry)
