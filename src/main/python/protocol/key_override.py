# SPDX-License-Identifier: GPL-2.0-or-later
"""
Key override protocol implementation using Viable 0xDF protocol.

Key override entry format (12 bytes):
    trigger: trigger keycode (uint16)
    replacement: replacement keycode (uint16)
    layers: layer mask (uint32) - supports all 32 QMK layers
    trigger_mods: required modifiers (uint8)
    negative_mod_mask: modifiers that cancel override (uint8)
    suppressed_mods: modifiers to suppress (uint8)
    options: option flags (uint8) - bit 7 = enabled
"""
import struct

from keycodes.keycodes import Keycode, RESET_KEYCODE
from protocol.base_protocol import BaseProtocol
from protocol.constants import (
    VIABLE_PREFIX,
    VIABLE_KEY_OVERRIDE_GET,
    VIABLE_KEY_OVERRIDE_SET,
)
from unlocker import Unlocker


class KeyOverrideOptions:
    """Options for key override entries."""

    def __init__(self, data=0):
        self.activation_trigger_down = bool(data & (1 << 0))
        self.activation_required_mod_down = bool(data & (1 << 1))
        self.activation_negative_mod_up = bool(data & (1 << 2))
        self.one_mod = bool(data & (1 << 3))
        self.no_reregister_trigger = bool(data & (1 << 4))
        self.no_unregister_on_other_key_down = bool(data & (1 << 5))
        # Bit 6 reserved
        self.enabled = bool(data & (1 << 7))

    def serialize(self):
        return (
            (int(self.activation_trigger_down) << 0)
            | (int(self.activation_required_mod_down) << 1)
            | (int(self.activation_negative_mod_up) << 2)
            | (int(self.one_mod) << 3)
            | (int(self.no_reregister_trigger) << 4)
            | (int(self.no_unregister_on_other_key_down) << 5)
            | (int(self.enabled) << 7)
        )

    def __repr__(self):
        return "KeyOverrideOptions<{}>".format(self.serialize())


class KeyOverrideEntry:
    """
    Key override entry for Viable protocol.

    12 bytes: trigger(2) + replacement(2) + layers(4) + trigger_mods(1)
              + negative_mod_mask(1) + suppressed_mods(1) + options(1)
    """

    def __init__(self, args=None):
        if args is None:
            args = [0] * 7
        self.trigger, self.replacement, self.layers, self.trigger_mods, \
            self.negative_mod_mask, self.suppressed_mods, opt = args
        self.options = KeyOverrideOptions(opt)

    def serialize(self):
        """Serializes into a viable key_override_entry (12 bytes)."""
        return struct.pack(
            "<HHIBBBB",
            Keycode.deserialize(self.trigger),
            Keycode.deserialize(self.replacement),
            self.layers,  # 32-bit layer mask
            self.trigger_mods,
            self.negative_mod_mask,
            self.suppressed_mods,
            self.options.serialize()
        )

    def __repr__(self):
        return (
            "KeyOverride<trigger={} replacement={} layers=0x{:08X} trigger_mods={} "
            "negative_mod_mask={} suppressed_mods={} options={}>".format(
                self.trigger, self.replacement, self.layers, self.trigger_mods,
                self.negative_mod_mask, self.suppressed_mods, self.options
            )
        )

    def __eq__(self, other):
        return isinstance(other, KeyOverrideEntry) and self.serialize() == other.serialize()

    def save(self):
        """Serializes into layout file format."""
        return {
            "trigger": self.trigger,
            "replacement": self.replacement,
            "layers": self.layers,
            "trigger_mods": self.trigger_mods,
            "negative_mod_mask": self.negative_mod_mask,
            "suppressed_mods": self.suppressed_mods,
            "options": self.options.serialize()
        }

    def restore(self, data):
        """Restores from layout file format."""
        self.trigger = data["trigger"]
        self.replacement = data["replacement"]
        # Handle old 16-bit layer format
        layers = data["layers"]
        if layers < 0x10000:
            # Old format was 16-bit, keep as-is (lower 16 layers)
            self.layers = layers
        else:
            self.layers = layers
        self.trigger_mods = data["trigger_mods"]
        self.negative_mod_mask = data["negative_mod_mask"]
        self.suppressed_mods = data["suppressed_mods"]
        self.options = KeyOverrideOptions(data["options"])


class ProtocolKeyOverride(BaseProtocol):

    def reload_key_override(self):
        """Load all key override entries from keyboard using Viable protocol."""
        self.key_override_entries = []
        for idx in range(self.key_override_count):
            data = self.usb_send(
                self.dev,
                struct.pack("BBB", VIABLE_PREFIX, VIABLE_KEY_OVERRIDE_GET, idx),
                retries=20
            )
            # Response: [0xDF] [0x05] [index] [12 bytes of key_override_entry]
            entry = struct.unpack("<HHIBBBB", data[3:15])
            # Serialize keycodes for GUI display
            e = (
                Keycode.serialize(entry[0]),
                Keycode.serialize(entry[1]),
                entry[2],  # layers (32-bit)
                entry[3],  # trigger_mods
                entry[4],  # negative_mod_mask
                entry[5],  # suppressed_mods
                entry[6]   # options
            )
            self.key_override_entries.append(KeyOverrideEntry(e))

    def key_override_get(self, idx):
        """Get a key override entry by index."""
        return self.key_override_entries[idx]

    def key_override_set(self, idx, entry):
        """Set a key override entry."""
        if entry == self.key_override_entries[idx]:
            return
        if entry.replacement == RESET_KEYCODE:
            Unlocker.unlock(self)
        self.key_override_entries[idx] = entry
        self.usb_send(
            self.dev,
            struct.pack("BBB", VIABLE_PREFIX, VIABLE_KEY_OVERRIDE_SET, idx) + entry.serialize(),
            retries=20
        )

    def _commit_key_override(self, idx, entry):
        """Send a key override change to the device (used by ChangeManager)."""
        if entry.replacement == RESET_KEYCODE:
            Unlocker.unlock(self)
        self.key_override_entries[idx] = entry
        self.usb_send(
            self.dev,
            struct.pack("BBB", VIABLE_PREFIX, VIABLE_KEY_OVERRIDE_SET, idx) + entry.serialize(),
            retries=20
        )
        return True

    def save_key_override(self):
        """Save key override entries for layout file."""
        return [e.save() for e in self.key_override_entries]

    def restore_key_override(self, data):
        """Restore key override entries from layout file."""
        for x, e in enumerate(data):
            if x < self.key_override_count:
                ko = KeyOverrideEntry()
                ko.restore(e)
                self.key_override_set(x, ko)
