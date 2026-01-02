# SPDX-License-Identifier: GPL-2.0-or-later
import struct

from protocol.constants import VIABLE_PREFIX


class BaseProtocol:
    viable_protocol = None  # Version of Viable 0xDF protocol, or None if not supported
    usb_send = NotImplemented
    dev = None

    macro_count = 0
    macro_memory = 0
    macro = b""

    def _retrieve_dynamic_entries(self, cmd, count, fmt):
        """Retrieve entries using Viable 0xDF protocol."""
        out = []
        for x in range(count):
            data = self.usb_send(
                self.dev,
                struct.pack("BBB", VIABLE_PREFIX, cmd, x),
                retries=20
            )
            # Response: [0xDF] [cmd] [index] [entry data...]
            # Data starts at byte 3 (after echoed command prefix)
            out.append(struct.unpack(fmt, data[3:3 + struct.calcsize(fmt)]))
        return out
