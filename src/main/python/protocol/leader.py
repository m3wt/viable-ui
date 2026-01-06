# SPDX-License-Identifier: GPL-2.0-or-later
"""
Leader key protocol implementation using Viable 0xDF protocol.

Leader entry format (14 bytes):
    sequence[5]: 5 trigger keycodes in order (uint16 each, 0x0000 = unused/end)
    output: output keycode (uint16)
    options: bit 15 = enabled, bits 0-14 = reserved (uint16)
"""
import struct

from keycodes.keycodes import Keycode, RESET_KEYCODE
from protocol.base_protocol import BaseProtocol
from protocol.constants import VIABLE_LEADER_GET, VIABLE_LEADER_SET
from unlocker import Unlocker


class ProtocolLeader(BaseProtocol):

    def reload_leader(self):
        """Load all leader entries from keyboard using Viable protocol."""
        self.leader_entries = []
        for idx in range(self.leader_count):
            data = self.wrapper.send_viable(
                struct.pack("BB", VIABLE_LEADER_GET, idx),
                retries=20
            )
            # Response: [0xDF] [0x14] [index] [14 bytes of leader_entry]
            entry = struct.unpack("<HHHHHHH", data[3:17])
            # Serialize keycodes for GUI display
            self.leader_entries.append((
                Keycode.serialize(entry[0]),  # sequence[0]
                Keycode.serialize(entry[1]),  # sequence[1]
                Keycode.serialize(entry[2]),  # sequence[2]
                Keycode.serialize(entry[3]),  # sequence[3]
                Keycode.serialize(entry[4]),  # sequence[4]
                Keycode.serialize(entry[5]),  # output
                entry[6]  # options (bit 15 = enabled)
            ))

    def leader_get(self, idx):
        """Get a leader entry by index."""
        return self.leader_entries[idx]

    def leader_set(self, idx, entry):
        """Set a leader entry."""
        if self.leader_entries[idx] == entry:
            return
        # Check for RESET keycode in output (index 5)
        if entry[5] == RESET_KEYCODE:
            Unlocker.unlock(self)
        self.leader_entries[idx] = entry
        raw_entry = [
            Keycode.deserialize(entry[0]),  # sequence[0]
            Keycode.deserialize(entry[1]),  # sequence[1]
            Keycode.deserialize(entry[2]),  # sequence[2]
            Keycode.deserialize(entry[3]),  # sequence[3]
            Keycode.deserialize(entry[4]),  # sequence[4]
            Keycode.deserialize(entry[5]),  # output
            entry[6]  # options
        ]
        serialized = struct.pack("<HHHHHHH", *raw_entry)
        self.wrapper.send_viable(
            struct.pack("BB", VIABLE_LEADER_SET, idx) + serialized,
            retries=20
        )

    def _commit_leader(self, idx, entry):
        """Send a leader change to the device (used by ChangeManager)."""
        if entry[5] == RESET_KEYCODE:
            Unlocker.unlock(self)
        self.leader_entries[idx] = entry
        raw_entry = [
            Keycode.deserialize(entry[0]),
            Keycode.deserialize(entry[1]),
            Keycode.deserialize(entry[2]),
            Keycode.deserialize(entry[3]),
            Keycode.deserialize(entry[4]),
            Keycode.deserialize(entry[5]),
            entry[6]
        ]
        serialized = struct.pack("<HHHHHHH", *raw_entry)
        self.wrapper.send_viable(
            struct.pack("BB", VIABLE_LEADER_SET, idx) + serialized,
            retries=20
        )
        return True

    def save_leader(self):
        """Save leader entries for layout file (.viable format)."""
        result = []
        for entry in self.leader_entries:
            options_raw = entry[6]
            result.append({
                "on": bool(options_raw & 0x8000),
                "sequence": [entry[0], entry[1], entry[2], entry[3], entry[4]],
                "output": entry[5]
            })
        return result

    def restore_leader(self, data, is_vil=False):
        """Restore leader entries from layout file.

        Args:
            data: List of leader entries (dict for .viable, tuple/list for old format)
            is_vil: If True, assume entries are enabled when 'on' is not specified
        """
        for x, e in enumerate(data):
            if x >= self.leader_count:
                break

            if isinstance(e, dict):
                # New .viable format with explicit fields
                on = e.get("on", True if is_vil else False)
                options = 0x8000 if on else 0
                seq = e.get("sequence", ["KC_NO", "KC_NO", "KC_NO", "KC_NO", "KC_NO"])
                entry = (
                    seq[0] if len(seq) > 0 else "KC_NO",
                    seq[1] if len(seq) > 1 else "KC_NO",
                    seq[2] if len(seq) > 2 else "KC_NO",
                    seq[3] if len(seq) > 3 else "KC_NO",
                    seq[4] if len(seq) > 4 else "KC_NO",
                    e.get("output", "KC_NO"),
                    options
                )
            else:
                # Old array format
                # Leader is a Viable extension, so old format already has options
                if is_vil and len(e) == 7:
                    # Force enabled for .vil
                    options = (e[6] & 0x7FFF) | 0x8000
                    entry = (e[0], e[1], e[2], e[3], e[4], e[5], options)
                else:
                    entry = tuple(e)

            self.leader_set(x, entry)
