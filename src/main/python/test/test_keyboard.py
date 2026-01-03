import unittest
import lzma
import struct
import os

from keycodes.keycodes import Keycode
from protocol.keyboard_comm import Keyboard
from protocol.constants import VIABLE_PREFIX, VIABLE_GET_PROTOCOL_INFO, VIABLE_DEFINITION_SIZE, \
    VIABLE_DEFINITION_CHUNK, VIABLE_DEFINITION_CHUNK_SIZE
from util import chunks, MSG_LEN


class FakeAppContext:
    def get_resource(self, name):
        # Return path to the test resource in the actual resources directory
        # Go from src/main/python/test to src/main/resources/base
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_path, "resources", "base", name)

LAYOUT_2x2 = """
{"name":"test","vendorId":"0x0000","productId":"0x1111","lighting":"none","matrix":{"rows":2,"cols":2},"layouts":{"keymap":[["0,0","0,1"],["1,0","1,1"]]}}
"""

LAYOUT_ENCODER = r"""
{"name":"test","vendorId":"0x0000","productId":"0x1111","lighting":"none","matrix":{"rows":1,"cols":1},"layouts":{"keymap":[["0,0\n\n\n\n\n\n\n\n\ne","0,1\n\n\n\n\n\n\n\n\ne"],["0,0"]]}}
"""


def s(kc):
    return Keycode.serialize(kc)


class SimulatedDevice:

    def __init__(self):
        # sequence of keyboard communications, pairs of (request, response)
        self.expect_data = []
        # current index in communications
        self.expect_idx = 0
        # For write/read interface
        self._pending_response = None
        # Client ID counter for bootstrap
        self._next_client_id = 0x12340001

    def write(self, data):
        """HID write - handles bootstrap and regular messages"""
        # Strip leading 0x00 report ID if present
        if data[0] == 0:
            data = data[1:]

        # Handle bootstrap (0xDD with client_id 0x00000000)
        if len(data) >= 5 and data[0] == 0xDD:
            client_id = struct.unpack("<I", data[1:5])[0]
            if client_id == 0:
                # Bootstrap request: [0xDD] [0x00000000] [nonce:20]
                # Response: [0xDD] [0x00000000] [nonce:20] [new_client_id:4] [ttl:2]
                nonce = data[5:25]
                new_id = self._next_client_id
                self._next_client_id += 1
                response = bytes([0xDD]) + struct.pack("<I", 0) + nonce
                response += struct.pack("<IH", new_id, 120)  # client_id, TTL
                response += b"\x00" * (MSG_LEN - len(response))
                self._pending_response = response
                return len(data) + 1
            else:
                # Wrapped command - unwrap and process
                protocol = data[5]
                if protocol == 0xDF:  # Viable
                    inner = data[5:]
                    inner_response = self._process_inner(inner)
                    # Wrap response
                    response = bytes([0xDD]) + struct.pack("<I", client_id) + inner_response
                    response = response[:MSG_LEN]
                    response += b"\x00" * (MSG_LEN - len(response))
                    self._pending_response = response
                    return len(data) + 1
                elif protocol == 0xFE:  # VIA
                    inner = data[6:]
                    inner_response = self._process_inner(inner)
                    # Wrap response
                    response = bytes([0xDD]) + struct.pack("<I", client_id) + bytes([0xFE]) + inner_response
                    response = response[:MSG_LEN]
                    response += b"\x00" * (MSG_LEN - len(response))
                    self._pending_response = response
                    return len(data) + 1

        # Non-wrapped (legacy) - process directly
        response = self._process_inner(data)
        self._pending_response = response
        return len(data) + 1

    def _process_inner(self, data):
        """Process inner command using expect_data"""
        if self.expect_idx >= len(self.expect_data):
            raise Exception("Trying to communicate more times ({}) than expected ({}); got data={}".format(
                self.expect_idx + 1,
                len(self.expect_data),
                data.hex()
            ))
        inp, out = self.expect_data[self.expect_idx]
        # Allow partial match for wrapped commands
        if not data.startswith(inp) and data != inp:
            raise Exception("Got unexpected data at index {}: expected={} got={}".format(
                self.expect_idx,
                inp.hex(),
                data.hex()
            ))
        self.expect_idx += 1
        return out

    def read(self, length, timeout_ms=0):
        """HID read - returns pending response"""
        if self._pending_response is None:
            return []
        response = self._pending_response
        self._pending_response = None
        return list(response[:length])

    def expect(self, inp, out):
        if isinstance(inp, str):
            inp = bytes.fromhex(inp)
        if isinstance(out, str):
            out = bytes.fromhex(out)
        out += b"\x00" * (MSG_LEN - len(out))
        self.expect_data.append((inp, out))

    def expect_via_protocol(self, via_protocol):
        self.expect("01", struct.pack(">BH", 1, via_protocol))

    def expect_viable_protocol(self, viable_protocol, td_count=0, combo_count=0, ko_count=0, ark_count=0, flags=0):
        # Request: [0xDF] [0x00]
        # Response: [0xDF] [0x00] [ver0-3] [td_count] [combo_count] [ko_count] [ark_count] [flags]
        self.expect(
            struct.pack("BB", VIABLE_PREFIX, VIABLE_GET_PROTOCOL_INFO),
            struct.pack("<BBIBBBBB", VIABLE_PREFIX, VIABLE_GET_PROTOCOL_INFO,
                       viable_protocol, td_count, combo_count, ko_count, ark_count, flags)
        )

    def expect_layout(self, layout):
        compressed = lzma.compress(layout.encode("utf-8"))
        # Request: [0xDF] [0x0D]
        # Response: [0xDF] [0x0D] [size0-3]
        self.expect(
            struct.pack("BB", VIABLE_PREFIX, VIABLE_DEFINITION_SIZE),
            struct.pack("<BBI", VIABLE_PREFIX, VIABLE_DEFINITION_SIZE, len(compressed))
        )
        # Fetch chunks using offset-based protocol
        offset = 0
        while offset < len(compressed):
            chunk = compressed[offset:offset + VIABLE_DEFINITION_CHUNK_SIZE]
            actual_size = len(chunk)
            # Request: [0xDF] [0x0E] [offset:2] [size:1]
            # Response: [0xDF] [0x0E] [offset:2] [actual_size:1] [data...]
            self.expect(
                struct.pack("<BBHB", VIABLE_PREFIX, VIABLE_DEFINITION_CHUNK, offset, VIABLE_DEFINITION_CHUNK_SIZE),
                struct.pack("<BBHB", VIABLE_PREFIX, VIABLE_DEFINITION_CHUNK, offset, actual_size) + chunk
            )
            offset += actual_size

    def expect_layers(self, layers):
        self.expect("11", struct.pack("BB", 0x11, layers))

    def expect_keymap(self, keymap):
        buffer = b""
        for layer in keymap:
            for row in layer:
                for col in row:
                    buffer += struct.pack(">H", col)
        # client will retrieve our keymap buffer in chunks of 28 bytes
        for x, chunk in enumerate(chunks(buffer, 28)):
            query = struct.pack(">BHB", 0x12, x, len(chunk))
            self.expect(query, query + chunk)

    def expect_encoders(self, encoders):
        # VIA3 encoder get: [0x14] [layer] [encoder_id] [direction]
        # Response: [0x14] [layer] [encoder_id] [keycode_hi] [keycode_lo]
        for l, layer in enumerate(encoders):
            for e, enc in enumerate(layer):
                # direction 0 (CW)
                self.expect(struct.pack("BBBB", 0x14, l, e, 0),
                           struct.pack(">BBBH", 0x14, l, e, enc[0]))
                # direction 1 (CCW)
                self.expect(struct.pack("BBBB", 0x14, l, e, 1),
                           struct.pack(">BBBH", 0x14, l, e, enc[1]))

    @staticmethod
    def sim_send(dev, data, retries=1):
        if dev.expect_idx >= len(dev.expect_data):
            raise Exception("Trying to communicate more times ({}) than expected ({}); got data={}".format(
                dev.expect_idx + 1,
                len(dev.expect_data),
                data.hex()
            ))
        inp, out = dev.expect_data[dev.expect_idx]
        if data != inp:
            raise Exception("Got unexpected data at index {}: expected={} with result={} got={}".format(
                dev.expect_idx,
                inp.hex(),
                out.hex(),
                data.hex()
            ))
        dev.expect_idx += 1
        return out

    def finish(self):
        if self.expect_idx != len(self.expect_data):
            raise Exception("Didn't communicate all the way, remaining data = {}".format(
                self.expect_data[self.expect_idx:]
            ))


class TestKeyboard(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from editor.qmk_settings import QmkSettings
        QmkSettings.initialize(FakeAppContext())

    @staticmethod
    def prepare_keyboard(layout, keymap, encoders=None):
        dev = SimulatedDevice()
        dev.expect_via_protocol(12)
        dev.expect_viable_protocol(1)  # Viable protocol version 1
        dev.expect_layout(layout)
        dev.expect_layers(len(keymap))

        # macro count
        dev.expect("0C", "0C00")
        # macro buffer size
        dev.expect("0D", "0D0000")

        # reload_dynamic queries viable protocol again
        dev.expect_viable_protocol(1)

        # QMK settings query via 0xDF protocol (return 0xFFFF to indicate no more settings)
        dev.expect("DF100000", "DF10FFFF")

        dev.expect_keymap(keymap)
        if encoders is not None:
            dev.expect_encoders(encoders)

        kb = Keyboard(dev, dev.sim_send)
        kb.reload()

        return kb, dev

    def test_keyboard_layout(self):
        """ Tests that loading a layout from a keyboard works """

        kb, dev = self.prepare_keyboard(LAYOUT_2x2, [[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
        self.assertEqual(kb.layers, 2)
        self.assertEqual(kb.layout[(0, 0, 0)], s(1))
        self.assertEqual(kb.layout[(0, 0, 1)], s(2))
        self.assertEqual(kb.layout[(0, 1, 0)], s(3))
        self.assertEqual(kb.layout[(0, 1, 1)], s(4))
        self.assertEqual(kb.layout[(1, 0, 0)], s(5))
        self.assertEqual(kb.layout[(1, 0, 1)], s(6))
        self.assertEqual(kb.layout[(1, 1, 0)], s(7))
        self.assertEqual(kb.layout[(1, 1, 1)], s(8))
        dev.finish()

    def test_set_key(self):
        """ Tests that setting a key works """

        kb, dev = self.prepare_keyboard(LAYOUT_2x2, [[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
        dev.expect("050101000009", "")
        kb.set_key(1, 1, 0, 9)
        self.assertEqual(kb.layout[(1, 1, 0)], 9)

        dev.finish()

    def test_set_key_twice(self):
        """ Tests that setting a key twice is optimized (doesn't send 2 cmds) """

        kb, dev = self.prepare_keyboard(LAYOUT_2x2, [[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
        dev.expect("050101000009", "")
        kb.set_key(1, 1, 0, 9)
        kb.set_key(1, 1, 0, 9)
        self.assertEqual(kb.layout[(1, 1, 0)], 9)

        dev.finish()

    def test_layout_save_restore(self):
        """ Tests that layout saving and restore works """

        kb, dev = self.prepare_keyboard(LAYOUT_2x2, [[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
        dev.expect("05010100000A", "")
        kb.set_key(1, 1, 0, Keycode.serialize(10))
        self.assertEqual(kb.layout[(1, 1, 0)], Keycode.serialize(10))
        data = kb.save_layout()
        dev.finish()

        kb, dev = self.prepare_keyboard(LAYOUT_2x2, [[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
        dev.expect("05010100000A", "")
        kb.restore_layout(data)
        self.assertEqual(kb.layout[(1, 1, 0)], Keycode.serialize(10))
        dev.finish()

    def test_encoder_simple(self):
        """ Tests that we try to retrieve encoder layout """

        kb, dev = self.prepare_keyboard(LAYOUT_ENCODER, [[[1]], [[2]], [[3]], [[4]]], [[(10, 11)], [(12, 13)], [(14, 15)], [(16, 17)]])
        self.assertEqual(kb.encoder_layout[(0, 0, 0)], Keycode.serialize(10))
        self.assertEqual(kb.encoder_layout[(0, 0, 1)], Keycode.serialize(11))
        self.assertEqual(kb.encoder_layout[(1, 0, 0)], Keycode.serialize(12))
        self.assertEqual(kb.encoder_layout[(1, 0, 1)], Keycode.serialize(13))
        self.assertEqual(kb.encoder_layout[(2, 0, 0)], Keycode.serialize(14))
        self.assertEqual(kb.encoder_layout[(2, 0, 1)], Keycode.serialize(15))
        self.assertEqual(kb.encoder_layout[(3, 0, 0)], Keycode.serialize(16))
        self.assertEqual(kb.encoder_layout[(3, 0, 1)], Keycode.serialize(17))
        dev.finish()

    def test_encoder_change(self):
        """ Test that changing encoder works """

        kb, dev = self.prepare_keyboard(LAYOUT_ENCODER, [[[1]], [[2]], [[3]], [[4]]], [[(10, 11)], [(12, 13)], [(14, 15)], [(16, 17)]])
        self.assertEqual(kb.encoder_layout[(1, 0, 0)], Keycode.serialize(12))
        self.assertEqual(kb.encoder_layout[(1, 0, 1)], Keycode.serialize(13))
        # VIA3 encoder set: [0x15] [layer] [encoder_id] [direction] [keycode_hi] [keycode_lo]
        dev.expect("150100010020", "")
        kb.set_encoder(1, 0, 1, Keycode.serialize(0x20))
        self.assertEqual(kb.encoder_layout[(1, 0, 1)], Keycode.serialize(0x20))
