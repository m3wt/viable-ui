# SPDX-License-Identifier: GPL-2.0-or-later
import struct


class BaseProtocol:
    viable_protocol = None  # Version of Viable 0xDF protocol, or None if not supported
    usb_send = NotImplemented
    wrapper = None  # ClientWrapper instance for protocol commands
    dev = None

    macro_count = 0
    macro_memory = 0
    macro = b""

    # Viable protocol feature counts (set by reload_viable_config from JSON)
    tap_dance_count = 0
    combo_count = 0
    key_override_count = 0
    alt_repeat_key_count = 0
    leader_count = 0

    def via_send(self, msg, retries=20):
        """Send a VIA command through the wrapper for client ID isolation."""
        return self.wrapper.send_via(msg, retries=retries)

    def _retrieve_dynamic_entries(self, cmd, count, fmt):
        """Retrieve entries using Viable 0xDF protocol via client wrapper."""
        out = []
        for x in range(count):
            data = self.wrapper.send_viable(
                struct.pack("BB", cmd, x),
                retries=20
            )
            # Response: [0xDF] [cmd] [index] [entry data...]
            # Data starts at byte 3 (after echoed command prefix)
            out.append(struct.unpack(fmt, data[3:3 + struct.calcsize(fmt)]))
        return out
