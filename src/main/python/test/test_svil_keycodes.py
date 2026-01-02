"""
Tests to verify all keycodes from test.svil are correctly handled.

This test file:
1. Extracts all unique keycodes from test.svil
2. Verifies each keycode deserializes to the correct integer value
3. Verifies each keycode serializes back to a valid representation
4. Cross-references with QMK keycode values
"""
import json
import os
import unittest

from keycodes.keycodes import Keycode, recreate_keyboard_keycodes


class FakeKeyboard:
    """Fake keyboard for keycode initialization."""
    layers = 16
    macro_count = 128
    custom_keycodes = None
    tap_dance_count = 50
    midi = None

    def __init__(self, protocol=1):
        self.viable_protocol = protocol
        # VIA protocol 12 uses v6 keycodes
        self.via_protocol = 12 if protocol >= 1 else 9
        self.supported_features = set([
            "persistent_default_layer", "caps_word", "layer_lock", "repeat_key",
        ])


# Expected QMK keycode values (v6 protocol)
# These are verified against qmk_firmware/quantum/keycodes.h
QMK_KEYCODES = {
    # Basic keycodes
    "KC_NO": 0x0000,
    "KC_TRNS": 0x0001,
    "KC_A": 0x0004,
    "KC_B": 0x0005,
    "KC_C": 0x0006,
    "KC_D": 0x0007,
    "KC_E": 0x0008,
    "KC_F": 0x0009,
    "KC_G": 0x000A,
    "KC_H": 0x000B,
    "KC_I": 0x000C,
    "KC_J": 0x000D,
    "KC_K": 0x000E,
    "KC_L": 0x000F,
    "KC_M": 0x0010,
    "KC_N": 0x0011,
    "KC_O": 0x0012,
    "KC_P": 0x0013,
    "KC_Q": 0x0014,
    "KC_R": 0x0015,
    "KC_S": 0x0016,
    "KC_T": 0x0017,
    "KC_U": 0x0018,
    "KC_V": 0x0019,
    "KC_W": 0x001A,
    "KC_X": 0x001B,
    "KC_Y": 0x001C,
    "KC_Z": 0x001D,
    "KC_1": 0x001E,
    "KC_2": 0x001F,
    "KC_3": 0x0020,
    "KC_4": 0x0021,
    "KC_5": 0x0022,
    "KC_6": 0x0023,
    "KC_7": 0x0024,
    "KC_8": 0x0025,
    "KC_9": 0x0026,
    "KC_0": 0x0027,
    "KC_ENTER": 0x0028,
    "KC_ESCAPE": 0x0029,
    "KC_BSPACE": 0x002A,
    "KC_TAB": 0x002B,
    "KC_SPACE": 0x002C,
    "KC_MINUS": 0x002D,
    "KC_EQUAL": 0x002E,
    "KC_LBRACKET": 0x002F,
    "KC_RBRACKET": 0x0030,
    "KC_BSLASH": 0x0031,
    "KC_SCOLON": 0x0033,
    "KC_QUOTE": 0x0034,
    "KC_GRAVE": 0x0035,
    "KC_COMMA": 0x0036,
    "KC_DOT": 0x0037,
    "KC_SLASH": 0x0038,
    "KC_CAPSLOCK": 0x0039,
    "KC_F1": 0x003A,
    "KC_F2": 0x003B,
    "KC_F3": 0x003C,
    "KC_F4": 0x003D,
    "KC_F5": 0x003E,
    "KC_F6": 0x003F,
    "KC_F7": 0x0040,
    "KC_F8": 0x0041,
    "KC_F9": 0x0042,
    "KC_F10": 0x0043,
    "KC_F11": 0x0044,
    "KC_F12": 0x0045,
    "KC_PSCREEN": 0x0046,
    "KC_SCROLLLOCK": 0x0047,
    "KC_PAUSE": 0x0048,
    "KC_INSERT": 0x0049,
    "KC_HOME": 0x004A,
    "KC_PGUP": 0x004B,
    "KC_DELETE": 0x004C,
    "KC_END": 0x004D,
    "KC_PGDOWN": 0x004E,
    "KC_RIGHT": 0x004F,
    "KC_LEFT": 0x0050,
    "KC_DOWN": 0x0051,
    "KC_UP": 0x0052,
    "KC_NUMLOCK": 0x0053,

    # Modifiers (from USB HID spec)
    "KC_LCTRL": 0x00E0,
    "KC_LSHIFT": 0x00E1,
    "KC_LALT": 0x00E2,
    "KC_LGUI": 0x00E3,
    "KC_RCTRL": 0x00E4,
    "KC_RSHIFT": 0x00E5,
    "KC_RALT": 0x00E6,
    "KC_RGUI": 0x00E7,

    # Mouse keycodes
    "KC_BTN1": 0x00D1,
    "KC_BTN2": 0x00D2,
    "KC_BTN3": 0x00D3,
    "KC_BTN4": 0x00D4,
    "KC_BTN5": 0x00D5,
    "KC_WH_U": 0x00D9,
    "KC_WH_D": 0x00DA,
    "KC_WH_L": 0x00DB,
    "KC_WH_R": 0x00DC,

    # Keypad
    "KC_KP_PLUS": 0x0057,

    # Layer keycodes (QK_* ranges from keycodes.h)
    "QK_TO": 0x5200,
    "QK_MOMENTARY": 0x5220,
    "QK_DEF_LAYER": 0x5240,
    "QK_TOGGLE_LAYER": 0x5260,
    "QK_ONE_SHOT_LAYER": 0x5280,
    "QK_ONE_SHOT_MOD": 0x52A0,
    "QK_LAYER_TAP_TOGGLE": 0x52C0,

    # Tap Dance
    "QK_TAP_DANCE": 0x5700,

    # Macro
    "QK_MACRO": 0x7700,

    # User keycodes (QK_USER_0 = 0x7E40)
    "QK_USER": 0x7E40,

    # RGB keycodes
    "RGB_VAI": 0x7827,  # QK_UNDERGLOW_VALUE_UP
    "RGB_VAD": 0x7828,  # QK_UNDERGLOW_VALUE_DOWN

    # Special quantum keycodes
    "QK_ALT_REPEAT_KEY": 0x7C7A,

    # Mod keycodes (QK_MODS = 0x0100)
    "QK_LCTL": 0x0100,
    "QK_LSFT": 0x0200,
    "QK_LALT": 0x0400,
    "QK_LGUI": 0x0800,
    "QK_RCTL": 0x1100,
    "QK_RSFT": 0x1200,
    "QK_RALT": 0x1400,
    "QK_RGUI": 0x1800,
}


def load_test_svil():
    """Load the test.svil file and return parsed data."""
    # Go from test directory up to workspace root
    test_dir = os.path.dirname(os.path.abspath(__file__))
    svil_path = os.path.join(test_dir, "..", "..", "..", "..", "..", "test.svil")
    svil_path = os.path.normpath(svil_path)

    with open(svil_path, "r") as f:
        return json.load(f)


def extract_keycodes_from_svil(data):
    """Extract all unique keycodes from a svil file."""
    keycodes = set()

    vil = data.get("vil", {})

    # Extract from layout
    layout = vil.get("layout", [])
    for layer in layout:
        for row in layer:
            for kc in row:
                if isinstance(kc, str):
                    keycodes.add(kc)

    # Extract from macros
    macros = vil.get("macro", [])
    for macro in macros:
        for action in macro:
            if len(action) >= 2:
                action_type = action[0]
                if action_type in ("tap", "down"):
                    keycodes.add(action[1])
                elif action_type == "up":
                    for kc in action[1:]:
                        keycodes.add(kc)

    # Extract from tap dance
    tap_dances = vil.get("tap_dance", [])
    for td in tap_dances:
        if len(td) >= 4:
            for kc in td[:4]:
                if isinstance(kc, str):
                    keycodes.add(kc)

    # Extract from combos
    combos = vil.get("combo", [])
    for combo in combos:
        for kc in combo:
            if isinstance(kc, str):
                keycodes.add(kc)

    # Extract from key overrides
    key_overrides = vil.get("key_override", [])
    for ko in key_overrides:
        if "trigger" in ko:
            keycodes.add(ko["trigger"])
        if "replacement" in ko:
            keycodes.add(ko["replacement"])

    # Extract from alt repeat key
    alt_repeat = vil.get("alt_repeat_key", [])
    for ark in alt_repeat:
        if "keycode" in ark:
            keycodes.add(ark["keycode"])
        if "alt_keycode" in ark:
            keycodes.add(ark["alt_keycode"])

    return keycodes


class TestSvilKeycodes(unittest.TestCase):
    """Test that all keycodes from test.svil are correctly handled."""

    @classmethod
    def setUpClass(cls):
        """Initialize keycodes with Viable protocol v1."""
        recreate_keyboard_keycodes(FakeKeyboard(1))
        cls.svil_data = load_test_svil()
        cls.all_keycodes = extract_keycodes_from_svil(cls.svil_data)

    def test_keycodes_extracted(self):
        """Verify we extracted keycodes from test.svil."""
        self.assertGreater(len(self.all_keycodes), 50,
                          f"Expected at least 50 keycodes, got {len(self.all_keycodes)}")

    def test_basic_keycodes_deserialize(self):
        """Test that basic keycodes deserialize correctly."""
        basic_tests = {
            "KC_A": 0x04,
            "KC_B": 0x05,
            "KC_Z": 0x1D,
            "KC_1": 0x1E,
            "KC_0": 0x27,
            "KC_ENTER": 0x28,
            "KC_ESCAPE": 0x29,
            "KC_TAB": 0x2B,
            "KC_SPACE": 0x2C,
            "KC_LCTRL": 0xE0,
            "KC_LSHIFT": 0xE1,
            "KC_LALT": 0xE2,
            "KC_LGUI": 0xE3,
        }
        for kc, expected in basic_tests.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} should deserialize to 0x{expected:04X}, got 0x{result:04X}")

    def test_layer_keycodes_deserialize(self):
        """Test that layer keycodes deserialize correctly per QMK."""
        layer_tests = {
            # MO(layer) = QK_MOMENTARY | layer = 0x5220 | layer
            "MO(3)": 0x5220 | 3,
            "MO(4)": 0x5220 | 4,
            "MO(15)": 0x5220 | 15,
            # TG(layer) = QK_TOGGLE_LAYER | layer = 0x5260 | layer
            "TG(8)": 0x5260 | 8,
            "TG(9)": 0x5260 | 9,
            "TG(10)": 0x5260 | 10,
            "TG(11)": 0x5260 | 11,
            # TO(layer) = QK_TO | layer = 0x5200 | layer
            "TO(0)": 0x5200 | 0,
            "TO(2)": 0x5200 | 2,
            "TO(3)": 0x5200 | 3,
            "TO(11)": 0x5200 | 11,
            "TO(12)": 0x5200 | 12,
            # DF(layer) = QK_DEF_LAYER | layer = 0x5240 | layer
            "DF(0)": 0x5240 | 0,
            "DF(1)": 0x5240 | 1,
        }
        for kc, expected in layer_tests.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} should deserialize to 0x{expected:04X}, got 0x{result:04X}")

    def test_user_keycodes_deserialize(self):
        """Test that USER keycodes deserialize correctly per QMK."""
        # QK_USER_0 = 0x7E40, USER00 = QK_USER + 0, etc.
        user_tests = {
            "USER00": 0x7E40,
            "USER01": 0x7E41,
            "USER02": 0x7E42,
            "USER03": 0x7E43,
            "USER04": 0x7E44,
            "USER05": 0x7E45,
            "USER07": 0x7E47,
            "USER08": 0x7E48,
            "USER09": 0x7E49,
            "USER10": 0x7E4A,
            "USER11": 0x7E4B,
            "USER17": 0x7E51,
            "USER18": 0x7E52,
            "USER19": 0x7E53,
        }
        for kc, expected in user_tests.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} should deserialize to 0x{expected:04X}, got 0x{result:04X}")

    def test_macro_keycodes_deserialize(self):
        """Test that macro keycodes deserialize correctly."""
        # QK_MACRO = 0x7700, M0 = QK_MACRO + 0, etc.
        macro_tests = {
            "M0": 0x7700,
            "M1": 0x7701,
            "M2": 0x7702,
            "M3": 0x7703,
            "M5": 0x7705,
            "M6": 0x7706,
            "M7": 0x7707,
            "M8": 0x7708,
        }
        for kc, expected in macro_tests.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} should deserialize to 0x{expected:04X}, got 0x{result:04X}")

    def test_modifier_wrapped_keycodes_deserialize(self):
        """Test that modifier-wrapped keycodes deserialize correctly."""
        # LSFT(kc) = 0x0200 | kc, LCTL(kc) = 0x0100 | kc, etc.
        mod_tests = {
            "LSFT(KC_ENTER)": 0x0200 | 0x28,  # 0x0228
            "LSFT(KC_1)": 0x0200 | 0x1E,      # 0x021E (!)
            "LSFT(KC_3)": 0x0200 | 0x20,      # 0x0220 (#)
            "LSFT(KC_4)": 0x0200 | 0x21,      # 0x0221 ($)
            "LSFT(KC_5)": 0x0200 | 0x22,      # 0x0222 (%)
            "LSFT(KC_6)": 0x0200 | 0x23,      # 0x0223 (^)
            "LSFT(KC_7)": 0x0200 | 0x24,      # 0x0224 (&)
            "LSFT(KC_8)": 0x0200 | 0x25,      # 0x0225 (*)
            "LSFT(KC_9)": 0x0200 | 0x26,      # 0x0226 (()
            "LSFT(KC_0)": 0x0200 | 0x27,      # 0x0227 ())
            "LCTL(KC_T)": 0x0100 | 0x17,      # 0x0117
            "LCTL(KC_0)": 0x0100 | 0x27,      # 0x0127
            "LALT(KC_F4)": 0x0400 | 0x3D,     # 0x043D
            "SGUI(KC_S)": 0x0A00 | 0x16,      # 0x0A16 (LGUI + LSFT + kc)
        }
        for kc, expected in mod_tests.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} should deserialize to 0x{expected:04X}, got 0x{result:04X}")

    def test_special_keycodes_deserialize(self):
        """Test that special keycodes deserialize correctly."""
        special_tests = {
            "KC_NO": 0x0000,
            "KC_TRNS": 0x0001,
            "QK_ALT_REPEAT_KEY": 0x7C7A,
            "RGB_VAI": 0x7827,
            "RGB_VAD": 0x7828,
        }
        for kc, expected in special_tests.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} should deserialize to 0x{expected:04X}, got 0x{result:04X}")

    def test_mouse_keycodes_deserialize(self):
        """Test that mouse keycodes deserialize correctly."""
        mouse_tests = {
            "KC_BTN1": 0xD1,
            "KC_BTN2": 0xD2,
            "KC_BTN3": 0xD3,
            "KC_BTN4": 0xD4,
            "KC_BTN5": 0xD5,
            "KC_WH_U": 0xD9,
            "KC_WH_D": 0xDA,
            "KC_WH_L": 0xDB,
            "KC_WH_R": 0xDC,
        }
        for kc, expected in mouse_tests.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} should deserialize to 0x{expected:04X}, got 0x{result:04X}")

    def test_function_keycodes_deserialize(self):
        """Test that function keycodes deserialize correctly."""
        fn_tests = {
            "KC_F1": 0x3A,
            "KC_F2": 0x3B,
            "KC_F3": 0x3C,
            "KC_F4": 0x3D,
            "KC_F5": 0x3E,
            "KC_F6": 0x3F,
            "KC_F7": 0x40,
            "KC_F8": 0x41,
            "KC_F9": 0x42,
            "KC_F10": 0x43,
            "KC_F11": 0x44,
            "KC_F12": 0x45,
        }
        for kc, expected in fn_tests.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} should deserialize to 0x{expected:04X}, got 0x{result:04X}")

    def test_all_svil_keycodes_deserialize(self):
        """Test that ALL keycodes from test.svil can be deserialized."""
        failures = []
        for kc in self.all_keycodes:
            try:
                result = Keycode.deserialize(kc)
                # Should return a non-zero int (or 0 for KC_NO)
                if result == 0 and kc not in ("KC_NO", "0x0000", "0x0"):
                    failures.append(f"{kc}: got 0 (unknown keycode)")
            except Exception as e:
                failures.append(f"{kc}: {e}")

        if failures:
            self.fail("Failed to deserialize keycodes:\n" + "\n".join(failures[:20]))

    def test_keycode_roundtrip(self):
        """Test that keycodes roundtrip correctly (deserialize -> serialize)."""
        # Test basic keycodes
        roundtrip_tests = [
            "KC_A", "KC_B", "KC_Z", "KC_1", "KC_0",
            "KC_ENTER", "KC_ESCAPE", "KC_TAB", "KC_SPACE",
            "KC_LCTRL", "KC_LSHIFT", "KC_LALT", "KC_LGUI",
            "KC_F1", "KC_F12", "KC_NO", "KC_TRNS",
            "KC_BTN1", "KC_BTN2", "KC_WH_U", "KC_WH_D",
        ]

        for kc in roundtrip_tests:
            with self.subTest(keycode=kc):
                integer_val = Keycode.deserialize(kc)
                serialized = Keycode.serialize(integer_val)
                # The serialized form might be the canonical name, not the exact input
                re_deserialized = Keycode.deserialize(serialized)
                self.assertEqual(integer_val, re_deserialized,
                               f"Roundtrip failed for {kc}: {integer_val} -> {serialized} -> {re_deserialized}")

    def test_layer_keycode_roundtrip(self):
        """Test that layer keycodes roundtrip correctly."""
        layer_tests = ["MO(3)", "TG(8)", "TO(0)", "DF(1)"]

        for kc in layer_tests:
            with self.subTest(keycode=kc):
                integer_val = Keycode.deserialize(kc)
                serialized = Keycode.serialize(integer_val)
                re_deserialized = Keycode.deserialize(serialized)
                self.assertEqual(integer_val, re_deserialized,
                               f"Roundtrip failed for {kc}: {integer_val} -> {serialized} -> {re_deserialized}")

    def test_macro_keycode_roundtrip(self):
        """Test that macro keycodes roundtrip correctly."""
        for i in range(10):
            kc = f"M{i}"
            with self.subTest(keycode=kc):
                integer_val = Keycode.deserialize(kc)
                serialized = Keycode.serialize(integer_val)
                re_deserialized = Keycode.deserialize(serialized)
                self.assertEqual(integer_val, re_deserialized,
                               f"Roundtrip failed for {kc}")

    def test_user_keycode_roundtrip(self):
        """Test that USER keycodes roundtrip correctly."""
        for i in range(20):
            kc = f"USER{i:02}"
            with self.subTest(keycode=kc):
                integer_val = Keycode.deserialize(kc)
                serialized = Keycode.serialize(integer_val)
                re_deserialized = Keycode.deserialize(serialized)
                self.assertEqual(integer_val, re_deserialized,
                               f"Roundtrip failed for {kc}")

    def test_mod_wrapped_keycode_roundtrip(self):
        """Test that modifier-wrapped keycodes roundtrip correctly."""
        mod_tests = [
            "LSFT(KC_A)", "LCTL(KC_C)", "LALT(KC_TAB)",
            "LGUI(KC_R)", "SGUI(KC_S)",
        ]

        for kc in mod_tests:
            with self.subTest(keycode=kc):
                integer_val = Keycode.deserialize(kc)
                serialized = Keycode.serialize(integer_val)
                re_deserialized = Keycode.deserialize(serialized)
                self.assertEqual(integer_val, re_deserialized,
                               f"Roundtrip failed for {kc}")


class TestQMKKeycodeAlignment(unittest.TestCase):
    """Verify vial-gui keycode values match QMK firmware."""

    @classmethod
    def setUpClass(cls):
        """Initialize keycodes with Viable protocol v1."""
        recreate_keyboard_keycodes(FakeKeyboard(1))

    def test_basic_keycodes_match_qmk(self):
        """Verify basic keycodes match QMK keycodes.h values."""
        qmk_basic = {
            "KC_A": 0x0004,
            "KC_B": 0x0005,
            "KC_C": 0x0006,
            "KC_D": 0x0007,
            "KC_E": 0x0008,
            "KC_F": 0x0009,
            "KC_G": 0x000A,
            "KC_H": 0x000B,
            "KC_I": 0x000C,
            "KC_J": 0x000D,
            "KC_K": 0x000E,
            "KC_L": 0x000F,
            "KC_M": 0x0010,
            "KC_N": 0x0011,
            "KC_O": 0x0012,
            "KC_P": 0x0013,
            "KC_Q": 0x0014,
            "KC_R": 0x0015,
            "KC_S": 0x0016,
            "KC_T": 0x0017,
            "KC_U": 0x0018,
            "KC_V": 0x0019,
            "KC_W": 0x001A,
            "KC_X": 0x001B,
            "KC_Y": 0x001C,
            "KC_Z": 0x001D,
        }
        for kc, expected in qmk_basic.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} mismatch: vial=0x{result:04X} vs QMK=0x{expected:04X}")

    def test_layer_ranges_match_qmk(self):
        """Verify layer keycode ranges match QMK keycodes.h values."""
        # From QMK keycodes.h:
        # QK_TO = 0x5200, QK_TO_MAX = 0x521F
        # QK_MOMENTARY = 0x5220, QK_MOMENTARY_MAX = 0x523F
        # QK_DEF_LAYER = 0x5240, QK_DEF_LAYER_MAX = 0x525F
        # QK_TOGGLE_LAYER = 0x5260, QK_TOGGLE_LAYER_MAX = 0x527F

        # Verify TO range
        for layer in range(16):
            kc = f"TO({layer})"
            expected = 0x5200 | layer
            result = Keycode.deserialize(kc)
            with self.subTest(keycode=kc):
                self.assertEqual(result, expected,
                               f"{kc} mismatch: vial=0x{result:04X} vs QMK=0x{expected:04X}")

        # Verify MO range
        for layer in range(16):
            kc = f"MO({layer})"
            expected = 0x5220 | layer
            result = Keycode.deserialize(kc)
            with self.subTest(keycode=kc):
                self.assertEqual(result, expected,
                               f"{kc} mismatch: vial=0x{result:04X} vs QMK=0x{expected:04X}")

        # Verify DF range
        for layer in range(16):
            kc = f"DF({layer})"
            expected = 0x5240 | layer
            result = Keycode.deserialize(kc)
            with self.subTest(keycode=kc):
                self.assertEqual(result, expected,
                               f"{kc} mismatch: vial=0x{result:04X} vs QMK=0x{expected:04X}")

        # Verify TG range
        for layer in range(16):
            kc = f"TG({layer})"
            expected = 0x5260 | layer
            result = Keycode.deserialize(kc)
            with self.subTest(keycode=kc):
                self.assertEqual(result, expected,
                               f"{kc} mismatch: vial=0x{result:04X} vs QMK=0x{expected:04X}")

    def test_user_range_matches_qmk(self):
        """Verify USER keycode range matches QMK keycodes.h values."""
        # From QMK keycodes.h:
        # QK_USER = 0x7E40, QK_USER_MAX = 0x7FFF
        # QK_USER_0 = 0x7E40, QK_USER_1 = 0x7E41, etc.

        for i in range(32):
            kc = f"USER{i:02}"
            expected = 0x7E40 + i
            result = Keycode.deserialize(kc)
            with self.subTest(keycode=kc):
                self.assertEqual(result, expected,
                               f"{kc} mismatch: vial=0x{result:04X} vs QMK=0x{expected:04X}")

    def test_macro_range_matches_qmk(self):
        """Verify macro keycode range matches QMK keycodes.h values."""
        # From QMK keycodes.h:
        # QK_MACRO = 0x7700, QK_MACRO_MAX = 0x777F

        for i in range(128):
            kc = f"M{i}"
            expected = 0x7700 + i
            result = Keycode.deserialize(kc)
            with self.subTest(keycode=kc):
                self.assertEqual(result, expected,
                               f"{kc} mismatch: vial=0x{result:04X} vs QMK=0x{expected:04X}")

    def test_mod_ranges_match_qmk(self):
        """Verify modifier keycode ranges match QMK keycodes.h values."""
        # From QMK keycodes.h:
        # QK_MODS = 0x0100, QK_MODS_MAX = 0x1FFF
        # Modifier bits: LCTL=0x01, LSFT=0x02, LALT=0x04, LGUI=0x08

        # Test LCTL(kc)
        result = Keycode.deserialize("LCTL(KC_A)")
        expected = 0x0100 | 0x04  # LCTL base + KC_A
        self.assertEqual(result, expected,
                        f"LCTL(KC_A) mismatch: vial=0x{result:04X} vs expected=0x{expected:04X}")

        # Test LSFT(kc)
        result = Keycode.deserialize("LSFT(KC_A)")
        expected = 0x0200 | 0x04  # LSFT base + KC_A
        self.assertEqual(result, expected,
                        f"LSFT(KC_A) mismatch: vial=0x{result:04X} vs expected=0x{expected:04X}")

        # Test LALT(kc)
        result = Keycode.deserialize("LALT(KC_A)")
        expected = 0x0400 | 0x04  # LALT base + KC_A
        self.assertEqual(result, expected,
                        f"LALT(KC_A) mismatch: vial=0x{result:04X} vs expected=0x{expected:04X}")

        # Test LGUI(kc)
        result = Keycode.deserialize("LGUI(KC_A)")
        expected = 0x0800 | 0x04  # LGUI base + KC_A
        self.assertEqual(result, expected,
                        f"LGUI(KC_A) mismatch: vial=0x{result:04X} vs expected=0x{expected:04X}")

    def test_quantum_keycodes_match_qmk(self):
        """Verify quantum keycodes match QMK keycodes.h values."""
        qmk_quantum = {
            "QK_ALT_REPEAT_KEY": 0x7C7A,
            # RGB keycodes (QK_UNDERGLOW_*)
            "RGB_VAI": 0x7827,  # QK_UNDERGLOW_VALUE_UP
            "RGB_VAD": 0x7828,  # QK_UNDERGLOW_VALUE_DOWN
        }
        for kc, expected in qmk_quantum.items():
            with self.subTest(keycode=kc):
                result = Keycode.deserialize(kc)
                self.assertEqual(result, expected,
                               f"{kc} mismatch: vial=0x{result:04X} vs QMK=0x{expected:04X}")


class TestSvilLoadingBugs(unittest.TestCase):
    """Tests for specific bugs found in svil loading."""

    @classmethod
    def setUpClass(cls):
        """Initialize keycodes with Viable protocol v1."""
        recreate_keyboard_keycodes(FakeKeyboard(1))

    def test_macro_not_confused_with_mod_tap(self):
        """
        Regression test: M0 was being incorrectly translated to MOD_TAP.

        Bug: When loading .svil files with via_protocol=9, string keycodes
        like "M0" were being deserialized to v6 values (0x7700), then
        incorrectly translated as if they were v5 MOD_TAP keycodes
        (0x6000-0x7FFF range), resulting in 0x3700 (a MOD_TAP keycode).

        Fix: String keycodes should NOT be translated because they get
        deserialized with the current protocol and are already correct.
        """
        # M0 in v6 is 0x7700
        m0_value = Keycode.deserialize("M0")
        self.assertEqual(m0_value, 0x7700,
                        f"M0 should be 0x7700, got 0x{m0_value:04X}")

        # After serialization, should still be M0, not a MOD_TAP
        m0_serialized = Keycode.serialize(m0_value)
        self.assertEqual(m0_serialized, "M0",
                        f"M0 should serialize back to 'M0', got '{m0_serialized}'")

        # The buggy translation would give 0x3700 (MOD_TAP range)
        buggy_value = (0x7700 - 0x6000) + 0x2000
        self.assertEqual(buggy_value, 0x3700)
        buggy_serialized = Keycode.serialize(buggy_value)
        # Make sure M0 doesn't serialize to the buggy value
        self.assertNotEqual(m0_serialized, buggy_serialized,
                           f"M0 should not serialize to '{buggy_serialized}'")

    def test_all_macro_keycodes_not_in_mod_tap_range(self):
        """Verify no macro keycodes fall into MOD_TAP range after deserialization."""
        for i in range(128):
            kc = f"M{i}"
            value = Keycode.deserialize(kc)
            # MOD_TAP range in v6 is 0x2000-0x3FFF
            self.assertFalse(0x2000 <= value <= 0x3FFF,
                           f"{kc} (0x{value:04X}) incorrectly in MOD_TAP range")
            # Macro range in v6 is 0x7700-0x777F
            self.assertTrue(0x7700 <= value <= 0x777F,
                          f"{kc} (0x{value:04X}) should be in MACRO range 0x7700-0x777F")


if __name__ == "__main__":
    unittest.main()
