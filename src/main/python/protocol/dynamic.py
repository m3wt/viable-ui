# SPDX-License-Identifier: GPL-2.0-or-later
import struct

from protocol.base_protocol import BaseProtocol
from protocol.constants import (
    VIABLE_GET_PROTOCOL_INFO,
    VIABLE_FLAG_CAPS_WORD, VIABLE_FLAG_LAYER_LOCK, VIABLE_FLAG_ONESHOT, VIABLE_FLAG_LEADER
)


class ProtocolDynamic(BaseProtocol):

    def reload_dynamic(self):
        self.supported_features = set()
        self.oneshot_timeout = 0
        self.oneshot_tap_toggle = 0

        if not self.viable_protocol:
            self.tap_dance_count = 0
            self.tap_dance_entries = []
            self.combo_count = 0
            self.combo_entries = []
            self.key_override_count = 0
            self.key_override_entries = []
            self.alt_repeat_key_count = 0
            self.leader_count = 0
            self.leader_entries = []
            return

        # Get protocol info from Viable 0xDF
        # Request: [0xDF] [0x00]
        # Response: [0xDF] [0x00] [ver0-3] [uid0-7] [flags]
        # Entry counts now come from viable.json in keyboard definition
        data = self.wrapper.send_viable(struct.pack("B", VIABLE_GET_PROTOCOL_INFO), retries=20)

        # Parse version (4 bytes little-endian at offset 2)
        self.viable_version = struct.unpack("<I", bytes(data[2:6]))[0]

        # Parse keyboard UID (8 bytes at offset 6) for save file matching
        self.keyboard_uid = struct.unpack("<Q", bytes(data[6:14]))[0]

        # Feature flags at offset 14
        flags = data[14] if len(data) > 14 else 0

        if flags & VIABLE_FLAG_CAPS_WORD:
            self.supported_features.add("caps_word")
        if flags & VIABLE_FLAG_LAYER_LOCK:
            self.supported_features.add("layer_lock")
        if flags & VIABLE_FLAG_ONESHOT:
            self.supported_features.add("oneshot")
        if flags & VIABLE_FLAG_LEADER:
            self.supported_features.add("leader")

        # Viable always supports persistent default layer
        self.supported_features.add("persistent_default_layer")

        # Entry counts are set by reload_viable_config() during JSON parsing
        # which happens before reload_dynamic() is called. Don't reset them here.

        # Re-add repeat_key feature if alt_repeat_key_count was set by reload_viable_config
        # (we reset supported_features above, so need to restore this)
        if getattr(self, 'alt_repeat_key_count', 0) > 0:
            self.supported_features.add("repeat_key")

    def reload_viable_config(self, viable_config):
        """Load entry counts from viable.json config parsed from keyboard definition."""
        self.tap_dance_count = viable_config.get("tap_dance", 0)
        self.combo_count = viable_config.get("combo", 0)
        self.key_override_count = viable_config.get("key_override", 0)
        self.alt_repeat_key_count = viable_config.get("alt_repeat_key", 0)
        self.leader_count = viable_config.get("leader", 0)

        # Ensure supported_features exists (may not if reload_dynamic hasn't run yet)
        if not hasattr(self, 'supported_features'):
            self.supported_features = set()

        # Update supported features based on counts
        if self.alt_repeat_key_count:
            self.supported_features.add("repeat_key")

        # Load oneshot values if supported
        if "oneshot" in self.supported_features:
            self.oneshot_timeout, self.oneshot_tap_toggle = self.oneshot_get()
