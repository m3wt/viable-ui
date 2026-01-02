import unittest

from keycodes.keycodes import Keycode, recreate_keyboard_keycodes


class FakeKeyboard:

    layers = 4
    macro_count = 16
    custom_keycodes = None
    tap_dance_count = 0
    midi = None

    def __init__(self, protocol):
        self.viable_protocol = protocol
        # VIA protocol 12 uses v6 keycodes, earlier versions use v5
        self.via_protocol = 12 if protocol >= 1 else 9
        self.supported_features = set([
            "persistent_default_layer", "caps_word", "layer_lock", "repeat_key",
        ])


class TestKeycode(unittest.TestCase):

    def _test_serialize_protocol(self, protocol):
        recreate_keyboard_keycodes(FakeKeyboard(protocol))
        covered = 0

        # at a minimum, we should be able to deserialize/serialize everything
        for x in range(2 ** 16):
            s = Keycode.serialize(x)
            d = Keycode.deserialize(s)
            self.assertEqual(d, x, "{} serialized into {} deserialized into {}".format(x, s, d))
            if s != hex(x):
                covered += 1
        print("[viable_protocol={}] {}/{} covered keycodes, which is {:.4f}%".format(protocol, covered, 2 ** 16, 100 * covered / 2 ** 16))

    def test_serialize(self):
        self._test_serialize_protocol(1)
