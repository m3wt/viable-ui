# SPDX-License-Identifier: GPL-2.0-or-later
import struct

from protocol.base_protocol import BaseProtocol
from protocol.constants import (
    VIABLE_GET_PROTOCOL_INFO,
    VIABLE_FLAG_CAPS_WORD, VIABLE_FLAG_LAYER_LOCK, VIABLE_FLAG_ONESHOT
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
            return

        # Get protocol info from Viable 0xDF (v2)
        # Request: [0xDF] [0x00]
        # Response: [0xDF] [0x00] [ver0-3] [td_count] [combo_count] [ko_count] [ark_count] [flags]
        data = self.wrapper.send_viable(struct.pack("B", VIABLE_GET_PROTOCOL_INFO), retries=20)

        # Parse version (4 bytes little-endian starting at offset 2)
        self.viable_version = struct.unpack("<I", bytes(data[2:6]))[0]

        # Entry counts
        self.tap_dance_count = data[6]
        self.combo_count = data[7]
        self.key_override_count = data[8]
        self.alt_repeat_key_count = data[9]

        # Feature flags
        flags = data[10] if len(data) > 10 else 0

        if flags & VIABLE_FLAG_CAPS_WORD:
            self.supported_features.add("caps_word")
        if flags & VIABLE_FLAG_LAYER_LOCK:
            self.supported_features.add("layer_lock")
        if flags & VIABLE_FLAG_ONESHOT:
            self.supported_features.add("oneshot")

        # Viable always supports persistent default layer
        self.supported_features.add("persistent_default_layer")

        if self.alt_repeat_key_count:
            self.supported_features.add("repeat_key")

        # Load oneshot values if supported
        if "oneshot" in self.supported_features:
            self.oneshot_timeout, self.oneshot_tap_toggle = self.oneshot_get()
