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
        """Save combo entries for layout file."""
        return [
            (entry[0], entry[1], entry[2], entry[3], entry[4], entry[5])
            for entry in self.combo_entries
        ]

    def restore_combo(self, data):
        """Restore combo entries from layout file."""
        for x, e in enumerate(data):
            if x < self.combo_count:
                # Handle old 5-element format (without custom_combo_term)
                if len(e) == 5:
                    e = list(e) + [0x8000]  # Add default enabled, no custom term
                self.combo_set(x, e)
