# coding: utf-8

# SPDX-License-Identifier: GPL-2.0-or-later

import sys

from keycodes.keycodes_v5 import keycodes_v5
from keycodes.keycodes_v6 import keycodes_v6


def translate_keycode_v5_to_v6(code):
    """Translate a v5 keycode to v6 format.

    v5 (VIA protocol < 12) used different base addresses for many keycodes.
    v6 (VIA protocol >= 12) uses the current QMK keycode layout.
    """
    # Vial saved -1 for empty slots - translate to KC_NO
    if code == -1:
        return 0  # KC_NO

    # QK_MACRO: 0x5F12-0x5FFF (M0-M237) -> 0x7700-0x77ED
    # Note: v5 macros M238-M255 (0x6000-0x6011) overlap with MOD_TAP range.
    # Since mod-taps are more commonly used than high macro numbers,
    # we only translate the non-overlapping macro range here.
    if 0x5F12 <= code <= 0x5FFF:
        macro_idx = code - 0x5F12
        # v6 only has 128 macros (0-127), cap at max
        if macro_idx > 127:
            macro_idx = 127
        return 0x7700 + macro_idx

    # QK_MOD_TAP: 0x6000-0x7FFF -> 0x2000-0x3FFF
    if 0x6000 <= code <= 0x7FFF:
        return (code - 0x6000) + 0x2000

    # QK_LAYER_MOD: 0x5900-0x59FF -> 0x5000-0x51FF
    # v5 format: layer in bits 4-7, mod in bits 0-3 (4-bit mods, LHS only)
    # v6 format: layer in bits 5-8, mod in bits 0-4 (5-bit mods, LHS+RHS)
    if 0x5900 <= code <= 0x59FF:
        v5_offset = code - 0x5900
        layer = (v5_offset >> 4) & 0xF
        mod = v5_offset & 0xF
        return 0x5000 | (layer << 5) | mod

    # QK_LAYER_TAP_TOGGLE: 0x5800-0x58FF -> 0x52C0-0x52DF (only 32 entries)
    if 0x5800 <= code <= 0x58FF:
        layer = code & 0x1F  # Only 5 bits for layer
        return 0x52C0 + layer

    # QK_ONE_SHOT_MOD: 0x5500-0x55FF -> 0x52A0-0x52BF (only 32 entries)
    if 0x5500 <= code <= 0x55FF:
        mod = code & 0x1F
        return 0x52A0 + mod

    # QK_ONE_SHOT_LAYER: 0x5400-0x54FF -> 0x5280-0x529F (only 32 entries)
    if 0x5400 <= code <= 0x54FF:
        layer = code & 0x1F
        return 0x5280 + layer

    # QK_TOGGLE_LAYER: 0x5300-0x53FF -> 0x5260-0x527F (only 32 entries)
    if 0x5300 <= code <= 0x53FF:
        layer = code & 0x1F
        return 0x5260 + layer

    # QK_DEF_LAYER: 0x5200-0x52FF -> 0x5240-0x525F (only 32 entries)
    if 0x5200 <= code <= 0x52FF:
        layer = code & 0x1F
        return 0x5240 + layer

    # QK_MOMENTARY: 0x5100-0x51FF -> 0x5220-0x523F (only 32 entries)
    if 0x5100 <= code <= 0x51FF:
        layer = code & 0x1F
        return 0x5220 + layer

    # QK_TO: 0x5000-0x50FF -> 0x5200-0x521F (only 32 entries)
    if 0x5000 <= code <= 0x50FF:
        layer = code & 0x1F
        return 0x5200 + layer

    # No translation needed
    return code


class Keycode:

    masked_keycodes = set()
    recorder_alias_to_keycode = dict()
    qmk_id_to_keycode = dict()
    protocol = 0
    hidden = False

    def __init__(self, qmk_id, label, tooltip=None, masked=False, printable=None, recorder_alias=None, alias=None, requires_feature=None):
        self.qmk_id = qmk_id
        self.qmk_id_to_keycode[qmk_id] = self
        self.requires_feature = requires_feature
        self.label = label
        # Qt WASM can't render CJK or subscripts - fall back to readable names
        if sys.platform == "emscripten" and not label.isascii() and qmk_id != "KC_TRNS":
            web_labels = {
                "KC_KANA": "Kana",
                "KC_HENK": "Henkan",
                "KC_MHEN": "Muhen",
                "KC_LANG1": "Lang1\nKana",
                "KC_LANG2": "Lang2\nEisu",
                # Steno number keys
                "STN_N1": "#1", "STN_N2": "#2", "STN_N3": "#3",
                "STN_N4": "#4", "STN_N5": "#5", "STN_N6": "#6",
                "STN_N7": "#7", "STN_N8": "#8", "STN_N9": "#9",
                # Steno star keys
                "STN_ST1": "*1", "STN_ST2": "*2", "STN_ST3": "*3", "STN_ST4": "*4",
                # Steno S keys
                "STN_S1": "S-1", "STN_S2": "S-2",
            }
            self.label = web_labels.get(qmk_id, qmk_id.replace("KC_", "").replace("STN_", ""))
        self.tooltip = tooltip
        # whether this keycode requires another sub-keycode
        self.masked = masked

        # if this is printable keycode, what character does it normally output (i.e. non-shifted state)
        self.printable = printable

        self.alias = [self.qmk_id]
        if alias:
            self.alias += alias

        if recorder_alias:
            for alias in recorder_alias:
                if alias in self.recorder_alias_to_keycode:
                    raise RuntimeError("Misconfigured: two keycodes claim the same alias {}".format(alias))
                self.recorder_alias_to_keycode[alias] = self

        if masked:
            assert qmk_id.endswith("(kc)")
            self.masked_keycodes.add(qmk_id.replace("(kc)", ""))

    @classmethod
    def find(cls, qmk_id):
        # this is to handle cases of qmk_id LCTL(kc) propagated here from find_inner_keycode
        if qmk_id == "kc":
            qmk_id = "KC_NO"
        return KEYCODES_MAP.get(qmk_id)

    @classmethod
    def find_outer_keycode(cls, qmk_id):
        """
        Finds outer keycode, i.e. if it is masked like 0x5Fxx, just return the 0x5F00 portion
        """
        if cls.is_mask(qmk_id):
            qmk_id = qmk_id[:qmk_id.find("(")]
        return cls.find(qmk_id)

    @classmethod
    def find_inner_keycode(cls, qmk_id):
        """
        Finds inner keycode, i.e. if it is masked like 0x5F12, just return the 0x12 portion
        """
        if cls.is_mask(qmk_id):
            qmk_id = qmk_id[qmk_id.find("(")+1:-1]
        return cls.find(qmk_id)

    @classmethod
    def find_by_recorder_alias(cls, alias):
        return cls.recorder_alias_to_keycode.get(alias)

    @classmethod
    def find_by_qmk_id(cls, qmk_id):
        return cls.qmk_id_to_keycode.get(qmk_id)

    @classmethod
    def is_mask(cls, qmk_id):
        return "(" in qmk_id and qmk_id[:qmk_id.find("(")] in cls.masked_keycodes

    @classmethod
    def is_basic(cls, qmk_id):
        return cls.deserialize(qmk_id) < 0x00FF

    @classmethod
    def label(cls, qmk_id):
        keycode = cls.find_outer_keycode(qmk_id)
        if keycode is None:
            # Handle LM(layer, mod) specially
            if qmk_id.startswith("LM(") and qmk_id.endswith(")"):
                return cls._format_lm_label(qmk_id)
            return qmk_id
        return keycode.label

    @classmethod
    def _format_lm_label(cls, qmk_id):
        """Format LM(layer, mod) as a nice label like 'LM 1\\nShift'"""
        try:
            inner = qmk_id[3:-1]  # Extract "layer, mod"
            parts = inner.split(",", 1)
            if len(parts) != 2:
                return qmk_id
            layer = parts[0].strip()
            mod_str = parts[1].strip()

            # Convert mod string to short form
            mod_short = cls._mod_to_short(mod_str)
            return f"LM {layer}\n{mod_short}"
        except Exception:
            return qmk_id

    @classmethod
    def _mod_to_short(cls, mod_str):
        """Convert MOD_LSFT|MOD_LCTL to short form like 'LSft' or 'LCS'"""
        prefix = "R" if "MOD_R" in mod_str else "L"
        mods = []
        if "CTL" in mod_str:
            mods.append("Ctl")
        if "SFT" in mod_str:
            mods.append("Sft")
        if "ALT" in mod_str:
            mods.append("Alt")
        if "GUI" in mod_str:
            mods.append("Gui")
        if len(mods) == 1:
            return prefix + mods[0]
        elif len(mods) > 1:
            # Multiple mods: use short form like "LCS"
            return prefix + "".join(m[0] for m in mods)
        return mod_str

    @classmethod
    def _mod_value_to_string(cls, mod):
        """Convert numeric mod value to MOD_xxx string"""
        # Mod bits: CTL=0x01, SFT=0x02, ALT=0x04, GUI=0x08, right=0x10
        parts = []
        is_right = mod & 0x10
        prefix = "MOD_R" if is_right else "MOD_L"
        if mod & 0x01:
            parts.append(f"{prefix}CTL")
        if mod & 0x02:
            parts.append(f"{prefix}SFT")
        if mod & 0x04:
            parts.append(f"{prefix}ALT")
        if mod & 0x08:
            parts.append(f"{prefix}GUI")
        return "|".join(parts) if parts else "0"

    @classmethod
    def tooltip(cls, qmk_id):
        keycode = cls.find_outer_keycode(qmk_id)
        if keycode is None:
            return None
        tooltip = keycode.qmk_id
        if keycode.tooltip:
            tooltip = "{}: {}".format(tooltip, keycode.tooltip)
        return tooltip

    @classmethod
    def serialize(cls, code):
        """ Converts integer keycode to string """
        if cls.protocol == 6:
            masked = keycodes_v6.masked
        else:
            masked = keycodes_v5.masked

        if (code & 0xFF00) not in masked:
            kc = RAWCODES_MAP.get(code)
            if kc is not None:
                return kc.qmk_id
        else:
            outer = RAWCODES_MAP.get(code & 0xFF00)
            inner = RAWCODES_MAP.get(code & 0x00FF)
            if outer is not None and inner is not None:
                return outer.qmk_id.replace("kc", inner.qmk_id)

        # Handle LM (Layer Mod) keycodes: 0x5000-0x51FF
        if 0x5000 <= code <= 0x51FF:
            layer = (code >> 5) & 0xF
            mod = code & 0x1F
            mod_str = cls._mod_value_to_string(mod)
            return f"LM({layer}, {mod_str})"

        return hex(code)

    @classmethod
    def deserialize(cls, val, reraise=False):
        """ Converts string keycode to integer """

        from any_keycode import AnyKeycode

        if isinstance(val, int):
            return val
        if val in cls.qmk_id_to_keycode:
            return cls.resolve(cls.qmk_id_to_keycode[val].qmk_id)
        anykc = AnyKeycode()
        try:
            return anykc.decode(val)
        except Exception:
            if reraise:
                raise
        return 0

    @classmethod
    def normalize(cls, code):
        """ Changes e.g. KC_PERC to LSFT(KC_5) """

        return Keycode.serialize(Keycode.deserialize(code))

    @classmethod
    def resolve(cls, qmk_constant):
        """ Translates a qmk_constant into firmware-specific integer keycode or macro constant """
        if cls.protocol == 6:
            kc = keycodes_v6.kc
        else:
            kc = keycodes_v5.kc

        if qmk_constant not in kc:
            raise RuntimeError("unable to resolve qmk_id={}".format(qmk_constant))
        return kc[qmk_constant]

    def is_supported_by(self, keyboard):
      """ Whether the keycode is supported by the keyboard. """
      if self.requires_feature is None:
        return True
      return self.requires_feature in keyboard.supported_features


K = Keycode

KEYCODES_SPECIAL = [
    K("KC_NO", ""),
    K("KC_TRNS", "▽", alias=["KC_TRANSPARENT"]),
]

KEYCODES_BASIC_NUMPAD = [
    K("KC_NUMLOCK", "Num\nLock", recorder_alias=["num lock"], alias=["KC_NLCK"]),
    K("KC_KP_SLASH", "/", alias=["KC_PSLS"]),
    K("KC_KP_ASTERISK", "*", alias=["KC_PAST"]),
    K("KC_KP_MINUS", "-", alias=["KC_PMNS"]),
    K("KC_KP_PLUS", "+", alias=["KC_PPLS"]),
    K("KC_KP_ENTER", "Num\nEnter", alias=["KC_PENT"]),
    K("KC_KP_1", "1", alias=["KC_P1"]),
    K("KC_KP_2", "2", alias=["KC_P2"]),
    K("KC_KP_3", "3", alias=["KC_P3"]),
    K("KC_KP_4", "4", alias=["KC_P4"]),
    K("KC_KP_5", "5", alias=["KC_P5"]),
    K("KC_KP_6", "6", alias=["KC_P6"]),
    K("KC_KP_7", "7", alias=["KC_P7"]),
    K("KC_KP_8", "8", alias=["KC_P8"]),
    K("KC_KP_9", "9", alias=["KC_P9"]),
    K("KC_KP_0", "0", alias=["KC_P0"]),
    K("KC_KP_DOT", ".", alias=["KC_PDOT"]),
    K("KC_KP_EQUAL", "=", alias=["KC_PEQL"]),
    K("KC_KP_COMMA", ",", alias=["KC_PCMM"]),
]

KEYCODES_BASIC_NAV = [
    K("KC_PSCREEN", "Print\nScreen", alias=["KC_PSCR"]),
    K("KC_SCROLLLOCK", "Scroll\nLock", recorder_alias=["scroll lock"], alias=["KC_SLCK", "KC_BRMD"]),
    K("KC_PAUSE", "Pause", recorder_alias=["pause", "break"], alias=["KC_PAUS", "KC_BRK", "KC_BRMU"]),
    K("KC_INSERT", "Insert", recorder_alias=["insert"], alias=["KC_INS"]),
    K("KC_HOME", "Home", recorder_alias=["home"]),
    K("KC_PGUP", "Page\nUp", recorder_alias=["page up"]),
    K("KC_DELETE", "Del", recorder_alias=["delete"], alias=["KC_DEL"]),
    K("KC_END", "End", recorder_alias=["end"]),
    K("KC_PGDOWN", "Page\nDown", recorder_alias=["page down"], alias=["KC_PGDN"]),
    K("KC_RIGHT", "Right", recorder_alias=["right"], alias=["KC_RGHT"]),
    K("KC_LEFT", "Left", recorder_alias=["left"]),
    K("KC_DOWN", "Down", recorder_alias=["down"]),
    K("KC_UP", "Up", recorder_alias=["up"]),
]

KEYCODES_BASIC = [
    K("KC_A", "A", printable="a", recorder_alias=["a"]),
    K("KC_B", "B", printable="b", recorder_alias=["b"]),
    K("KC_C", "C", printable="c", recorder_alias=["c"]),
    K("KC_D", "D", printable="d", recorder_alias=["d"]),
    K("KC_E", "E", printable="e", recorder_alias=["e"]),
    K("KC_F", "F", printable="f", recorder_alias=["f"]),
    K("KC_G", "G", printable="g", recorder_alias=["g"]),
    K("KC_H", "H", printable="h", recorder_alias=["h"]),
    K("KC_I", "I", printable="i", recorder_alias=["i"]),
    K("KC_J", "J", printable="j", recorder_alias=["j"]),
    K("KC_K", "K", printable="k", recorder_alias=["k"]),
    K("KC_L", "L", printable="l", recorder_alias=["l"]),
    K("KC_M", "M", printable="m", recorder_alias=["m"]),
    K("KC_N", "N", printable="n", recorder_alias=["n"]),
    K("KC_O", "O", printable="o", recorder_alias=["o"]),
    K("KC_P", "P", printable="p", recorder_alias=["p"]),
    K("KC_Q", "Q", printable="q", recorder_alias=["q"]),
    K("KC_R", "R", printable="r", recorder_alias=["r"]),
    K("KC_S", "S", printable="s", recorder_alias=["s"]),
    K("KC_T", "T", printable="t", recorder_alias=["t"]),
    K("KC_U", "U", printable="u", recorder_alias=["u"]),
    K("KC_V", "V", printable="v", recorder_alias=["v"]),
    K("KC_W", "W", printable="w", recorder_alias=["w"]),
    K("KC_X", "X", printable="x", recorder_alias=["x"]),
    K("KC_Y", "Y", printable="y", recorder_alias=["y"]),
    K("KC_Z", "Z", printable="z", recorder_alias=["z"]),
    K("KC_1", "!\n1", printable="1", recorder_alias=["1"]),
    K("KC_2", "@\n2", printable="2", recorder_alias=["2"]),
    K("KC_3", "#\n3", printable="3", recorder_alias=["3"]),
    K("KC_4", "$\n4", printable="4", recorder_alias=["4"]),
    K("KC_5", "%\n5", printable="5", recorder_alias=["5"]),
    K("KC_6", "^\n6", printable="6", recorder_alias=["6"]),
    K("KC_7", "&\n7", printable="7", recorder_alias=["7"]),
    K("KC_8", "*\n8", printable="8", recorder_alias=["8"]),
    K("KC_9", "(\n9", printable="9", recorder_alias=["9"]),
    K("KC_0", ")\n0", printable="0", recorder_alias=["0"]),
    K("KC_ENTER", "Enter", recorder_alias=["enter"], alias=["KC_ENT"]),
    K("KC_ESCAPE", "Esc", recorder_alias=["esc"], alias=["KC_ESC"]),
    K("KC_BSPACE", "Bksp", recorder_alias=["backspace"], alias=["KC_BSPC"]),
    K("KC_TAB", "Tab", recorder_alias=["tab"]),
    K("KC_SPACE", "Space", recorder_alias=["space"], alias=["KC_SPC"]),
    K("KC_MINUS", "_\n-", printable="-", recorder_alias=["-"], alias=["KC_MINS"]),
    K("KC_EQUAL", "+\n=", printable="=", recorder_alias=["="], alias=["KC_EQL"]),
    K("KC_LBRACKET", "{\n[", printable="[", recorder_alias=["["], alias=["KC_LBRC"]),
    K("KC_RBRACKET", "}\n]", printable="]", recorder_alias=["]"], alias=["KC_RBRC"]),
    K("KC_BSLASH", "|\n\\", printable="\\", recorder_alias=["\\"], alias=["KC_BSLS"]),
    K("KC_SCOLON", ":\n;", printable=";", recorder_alias=[";"], alias=["KC_SCLN"]),
    K("KC_QUOTE", "\"\n'", printable="'", recorder_alias=["'"], alias=["KC_QUOT"]),
    K("KC_GRAVE", "~\n`", printable="`", recorder_alias=["`"], alias=["KC_GRV", "KC_ZKHK"]),
    K("KC_COMMA", "<\n,", printable=",", recorder_alias=[","], alias=["KC_COMM"]),
    K("KC_DOT", ">\n.", printable=".", recorder_alias=["."]),
    K("KC_SLASH", "?\n/", printable="/", recorder_alias=["/"], alias=["KC_SLSH"]),
    K("KC_CAPSLOCK", "Caps\nLock", recorder_alias=["caps lock"], alias=["KC_CLCK", "KC_CAPS"]),
    K("KC_F1", "F1", recorder_alias=["f1"]),
    K("KC_F2", "F2", recorder_alias=["f2"]),
    K("KC_F3", "F3", recorder_alias=["f3"]),
    K("KC_F4", "F4", recorder_alias=["f4"]),
    K("KC_F5", "F5", recorder_alias=["f5"]),
    K("KC_F6", "F6", recorder_alias=["f6"]),
    K("KC_F7", "F7", recorder_alias=["f7"]),
    K("KC_F8", "F8", recorder_alias=["f8"]),
    K("KC_F9", "F9", recorder_alias=["f9"]),
    K("KC_F10", "F10", recorder_alias=["f10"]),
    K("KC_F11", "F11", recorder_alias=["f11"]),
    K("KC_F12", "F12", recorder_alias=["f12"]),

    K("KC_APPLICATION", "Menu", recorder_alias=["menu", "left menu", "right menu"], alias=["KC_APP"]),
    K("KC_LCTRL", "LCtrl", recorder_alias=["left ctrl", "ctrl"], alias=["KC_LCTL"]),
    K("KC_LSHIFT", "LShift", recorder_alias=["left shift", "shift"], alias=["KC_LSFT"]),
    K("KC_LALT", "LAlt", recorder_alias=["alt"], alias=["KC_LOPT"]),
    K("KC_LGUI", "LGui", recorder_alias=["left windows", "windows"], alias=["KC_LCMD", "KC_LWIN"]),
    K("KC_RCTRL", "RCtrl", recorder_alias=["right ctrl"], alias=["KC_RCTL"]),
    K("KC_RSHIFT", "RShift", recorder_alias=["right shift"], alias=["KC_RSFT"]),
    K("KC_RALT", "RAlt", alias=["KC_ALGR", "KC_ROPT"]),
    K("KC_RGUI", "RGui", recorder_alias=["right windows"], alias=["KC_RCMD", "KC_RWIN"]),
]

KEYCODES_BASIC.extend(KEYCODES_BASIC_NUMPAD)
KEYCODES_BASIC.extend(KEYCODES_BASIC_NAV)

KEYCODES_SHIFTED = [
    K("KC_TILD", "~"),
    K("KC_EXLM", "!"),
    K("KC_AT", "@"),
    K("KC_HASH", "#"),
    K("KC_DLR", "$"),
    K("KC_PERC", "%"),
    K("KC_CIRC", "^"),
    K("KC_AMPR", "&"),
    K("KC_ASTR", "*"),
    K("KC_LPRN", "("),
    K("KC_RPRN", ")"),
    K("KC_UNDS", "_"),
    K("KC_PLUS", "+"),
    K("KC_LCBR", "{"),
    K("KC_RCBR", "}"),
    K("KC_LT", "<"),
    K("KC_GT", ">"),
    K("KC_COLN", ":"),
    K("KC_PIPE", "|"),
    K("KC_QUES", "?"),
    K("KC_DQUO", '"'),
]

KEYCODES_ISO = [
    K("KC_NONUS_HASH", "~\n#", "Non-US # and ~", alias=["KC_NUHS"]),
    K("KC_NONUS_BSLASH", "|\n\\", "Non-US \\ and |", alias=["KC_NUBS"]),
    K("KC_RO", "_\n\\", "JIS \\ and _", alias=["KC_INT1"]),
    K("KC_KANA", "カタカナ\nひらがな", "JIS Katakana/Hiragana", alias=["KC_INT2"]),
    K("KC_JYEN", "|\n¥", alias=["KC_INT3"]),
    K("KC_HENK", "変換", "JIS Henkan", alias=["KC_INT4"]),
    K("KC_MHEN", "無変換", "JIS Muhenkan", alias=["KC_INT5"]),
]

KEYCODES_ISO_KR = [
    K("KC_LANG1", "한영\nかな", "Korean Han/Yeong / JP Mac Kana", alias=["KC_HAEN"]),
    K("KC_LANG2", "漢字\n英数", "Korean Hanja / JP Mac Eisu", alias=["KC_HANJ"]),
]

KEYCODES_ISO.extend(KEYCODES_ISO_KR)

KEYCODES_LAYERS = []
RESET_KEYCODE = "QK_BOOT"

KEYCODES_BOOT = [
    K("QK_BOOT", "Boot-\nloader", "Put the keyboard into bootloader mode for flashing", alias=["RESET"]),
    K("QK_REBOOT", "Reboot", "Reboots the keyboard. Does not load the bootloader"),
    K("QK_CLEAR_EEPROM", "Clear\nEEPROM", "Reinitializes the keyboard's EEPROM (persistent memory)", alias=["EE_CLR"]),
]

KEYCODES_MODIFIERS = [
    K("OSM(MOD_LSFT)", "OSM\nLSft", "Enable Left Shift for one keypress"),
    K("OSM(MOD_LCTL)", "OSM\nLCtl", "Enable Left Control for one keypress"),
    K("OSM(MOD_LALT)", "OSM\nLAlt", "Enable Left Alt for one keypress"),
    K("OSM(MOD_LGUI)", "OSM\nLGUI", "Enable Left GUI for one keypress"),
    K("OSM(MOD_RSFT)", "OSM\nRSft", "Enable Right Shift for one keypress"),
    K("OSM(MOD_RCTL)", "OSM\nRCtl", "Enable Right Control for one keypress"),
    K("OSM(MOD_RALT)", "OSM\nRAlt", "Enable Right Alt for one keypress"),
    K("OSM(MOD_RGUI)", "OSM\nRGUI", "Enable Right GUI for one keypress"),
    K("OSM(MOD_LCTL|MOD_LSFT)", "OSM\nCS", "Enable Left Control and Shift for one keypress"),
    K("OSM(MOD_LCTL|MOD_LALT)", "OSM\nCA", "Enable Left Control and Alt for one keypress"),
    K("OSM(MOD_LCTL|MOD_LGUI)", "OSM\nCG", "Enable Left Control and GUI for one keypress"),
    K("OSM(MOD_LSFT|MOD_LALT)", "OSM\nSA", "Enable Left Shift and Alt for one keypress"),
    K("OSM(MOD_LSFT|MOD_LGUI)", "OSM\nSG", "Enable Left Shift and GUI for one keypress"),
    K("OSM(MOD_LALT|MOD_LGUI)", "OSM\nAG", "Enable Left Alt and GUI for one keypress"),
    K("OSM(MOD_RCTL|MOD_RSFT)", "OSM\nRCS", "Enable Right Control and Shift for one keypress"),
    K("OSM(MOD_RCTL|MOD_RALT)", "OSM\nRCA", "Enable Right Control and Alt for one keypress"),
    K("OSM(MOD_RCTL|MOD_RGUI)", "OSM\nRCG", "Enable Right Control and GUI for one keypress"),
    K("OSM(MOD_RSFT|MOD_RALT)", "OSM\nRSA", "Enable Right Shift and Alt for one keypress"),
    K("OSM(MOD_RSFT|MOD_RGUI)", "OSM\nRSG", "Enable Right Shift and GUI for one keypress"),
    K("OSM(MOD_RALT|MOD_RGUI)", "OSM\nRAG", "Enable Right Alt and GUI for one keypress"),
    K("OSM(MOD_LCTL|MOD_LSFT|MOD_LGUI)", "OSM\nCSG", "Enable Left Control, Shift, and GUI for one keypress"),
    K("OSM(MOD_LCTL|MOD_LALT|MOD_LGUI)", "OSM\nCAG", "Enable Left Control, Alt, and GUI for one keypress"),
    K("OSM(MOD_LSFT|MOD_LALT|MOD_LGUI)", "OSM\nSAG", "Enable Left Shift, Alt, and GUI for one keypress"),
    K("OSM(MOD_RCTL|MOD_RSFT|MOD_RGUI)", "OSM\nRCSG", "Enable Right Control, Shift, and GUI for one keypress"),
    K("OSM(MOD_RCTL|MOD_RALT|MOD_RGUI)", "OSM\nRCAG", "Enable Right Control, Alt, and GUI for one keypress"),
    K("OSM(MOD_RSFT|MOD_RALT|MOD_RGUI)", "OSM\nRSAG", "Enable Right Shift, Alt, and GUI for one keypress"),
    K("OSM(MOD_MEH)", "OSM\nMeh", "Enable Left Control, Shift, and Alt for one keypress"),
    K("OSM(MOD_HYPR)", "OSM\nHyper", "Enable Left Control, Shift, Alt, and GUI for one keypress"),
    K("OSM(MOD_RCTL|MOD_RSFT|MOD_RALT)", "OSM\nRMeh", "Enable Right Control, Shift, and Alt for one keypress"),
    K("OSM(MOD_RCTL|MOD_RSFT|MOD_RALT|MOD_RGUI)", "OSM\nRHyp", "Enable Right Control, Shift, Alt, and GUI for one keypress"),

    K("LSFT(kc)", "LSft\n(kc)", masked=True),
    K("LCTL(kc)", "LCtl\n(kc)", masked=True),
    K("LALT(kc)", "LAlt\n(kc)", masked=True),
    K("LGUI(kc)", "LGui\n(kc)", masked=True),
    K("RSFT(kc)", "RSft\n(kc)", masked=True),
    K("RCTL(kc)", "RCtl\n(kc)", masked=True),
    K("RALT(kc)", "RAlt\n(kc)", masked=True),
    K("RGUI(kc)", "RGui\n(kc)", masked=True),
    K("C_S(kc)", "LCS\n(kc)", "LCTL + LSFT", masked=True, alias=["LCS(kc)"]),
    K("LCA(kc)", "LCA\n(kc)", "LCTL + LALT", masked=True),
    K("LCG(kc)", "LCG\n(kc)", "LCTL + LGUI", masked=True),
    K("LSA(kc)", "LSA\n(kc)", "LSFT + LALT", masked=True),
    K("LAG(kc)", "LAG\n(kc)", "LALT + LGUI", masked=True),
    K("SGUI(kc)", "LSG\n(kc)", "LGUI + LSFT", masked=True, alias=["LSG(kc)"]),
    K("LCAG(kc)", "LCAG\n(kc)", "LCTL + LALT + LGUI", masked=True),
    K("RCG(kc)", "RCG\n(kc)", "RCTL + RGUI", masked=True),
    K("MEH(kc)", "Meh\n(kc)", "LCTL + LSFT + LALT", masked=True),
    K("HYPR(kc)", "Hyper\n(kc)", "LCTL + LSFT + LALT + LGUI", masked=True),

    K("LSFT_T(kc)", "LSft_T\n(kc)", "Left Shift when held, kc when tapped", masked=True),
    K("LCTL_T(kc)", "LCtl_T\n(kc)", "Left Control when held, kc when tapped", masked=True),
    K("LALT_T(kc)", "LAlt_T\n(kc)", "Left Alt when held, kc when tapped", masked=True),
    K("LGUI_T(kc)", "LGui_T\n(kc)", "Left GUI when held, kc when tapped", masked=True),
    K("RSFT_T(kc)", "RSft_T\n(kc)", "Right Shift when held, kc when tapped", masked=True),
    K("RCTL_T(kc)", "RCtl_T\n(kc)", "Right Control when held, kc when tapped", masked=True),
    K("RALT_T(kc)", "RAlt_T\n(kc)", "Right Alt when held, kc when tapped", masked=True),
    K("RGUI_T(kc)", "RGui_T\n(kc)", "Right GUI when held, kc when tapped", masked=True),
    K("C_S_T(kc)", "LCS_T\n(kc)", "Left Control + Left Shift when held, kc when tapped", masked=True, alias=["LCS_T(kc)"] ),
    K("LCA_T(kc)", "LCA_T\n(kc)", "LCTL + LALT when held, kc when tapped", masked=True),
    K("LCG_T(kc)", "LCG_T\n(kc)", "LCTL + LGUI when held, kc when tapped", masked=True),
    K("LSA_T(kc)", "LSA_T\n(kc)", "LSFT + LALT when held, kc when tapped", masked=True),
    K("LAG_T(kc)", "LAG_T\n(kc)", "LALT + LGUI when held, kc when tapped", masked=True),
    K("SGUI_T(kc)", "LSG_T\n(kc)", "LGUI + LSFT when held, kc when tapped", masked=True, alias=["LSG_T(kc)"]),
    K("LCAG_T(kc)", "LCAG_T\n(kc)", "LCTL + LALT + LGUI when held, kc when tapped", masked=True),
    K("LSCG_T(kc)", "LSCG_T\n(kc)", "LSFT + LCTL + LGUI when held, kc when tapped", masked=True),
    K("LSAG_T(kc)", "LSAG_T\n(kc)", "LSFT + LALT + LGUI when held, kc when tapped", masked=True),
    K("RSC_T(kc)", "RSC_T\n(kc)", "RSFT + RCTL when held, kc when tapped", masked=True),
    K("RCA_T(kc)", "RCA_T\n(kc)", "RCTL + RALT when held, kc when tapped", masked=True),
    K("RSA_T(kc)", "RSA_T\n(kc)", "RSFT + RALT when held, kc when tapped", masked=True),
    K("RCG_T(kc)", "RCG_T\n(kc)", "RCTL + RGUI when held, kc when tapped", masked=True),
    K("RSG_T(kc)", "RSG_T\n(kc)", "RSFT + RGUI when held, kc when tapped", masked=True),
    K("RSCG_T(kc)", "RSCG_T\n(kc)", "RSFT + RCTL + RGUI when held, kc when tapped", masked=True),
    K("RAG_T(kc)", "RAG_T\n(kc)", "RALT + RGUI when held, kc when tapped", masked=True),
    K("RCAG_T(kc)", "RCAG_T\n(kc)", "RCTL + RALT + RGUI when held, kc when tapped", masked=True),
    K("RSAG_T(kc)", "RSAG_T\n(kc)", "RSFT + RALT + RGUI when held, kc when tapped", masked=True),
    K("RSCA_T(kc)", "RSCA_T\n(kc)", "RSFT + RCTL + RALT when held, kc when tapped", masked=True),
    K("RSCAG_T(kc)", "RSCAG_T\n(kc)", "RSFT + RCTL + RALT + RGUI when held, kc when tapped", masked=True),
    K("MEH_T(kc)", "Meh_T\n(kc)", "LCTL + LSFT + LALT when held, kc when tapped", masked=True),
    K("ALL_T(kc)", "ALL_T\n(kc)", "LCTL + LSFT + LALT + LGUI when held, kc when tapped", masked=True),

    K("KC_GESC", "~\nEsc", "Esc normally, but ~ when Shift or GUI is pressed"),
    K("KC_LSPO", "LS\n(", "Left Shift when held, ( when tapped"),
    K("KC_RSPC", "RS\n)", "Right Shift when held, ) when tapped"),
    K("KC_LCPO", "LC\n(", "Left Control when held, ( when tapped"),
    K("KC_RCPC", "RC\n)", "Right Control when held, ) when tapped"),
    K("KC_LAPO", "LA\n(", "Left Alt when held, ( when tapped"),
    K("KC_RAPC", "RA\n)", "Right Alt when held, ) when tapped"),
    K("KC_SFTENT", "RS\nEnter", "Right Shift when held, Enter when tapped"),
]

KEYCODES_QUANTUM = [
    K("MAGIC_SWAP_CONTROL_CAPSLOCK", "Swap\nCtrl\nCaps", "Swap Caps Lock and Left Control", alias=["CL_SWAP"]),
    K("MAGIC_UNSWAP_CONTROL_CAPSLOCK", "Unswap\nCtrl\nCaps", "Unswap Caps Lock and Left Control", alias=["CL_NORM"]),
    K("MAGIC_CAPSLOCK_TO_CONTROL", "Caps\nto\nCtrl", "Treat Caps Lock as Control", alias=["CL_CTRL"]),
    K("MAGIC_UNCAPSLOCK_TO_CONTROL", "Caps\nnot to\nCtrl", "Stop treating Caps Lock as Control", alias=["CL_CAPS"]),
    K("MAGIC_SWAP_LCTL_LGUI", "Swap\nLCtl\nLGui", "Swap Left Control and GUI", alias=["LCG_SWP"]),
    K("MAGIC_UNSWAP_LCTL_LGUI", "Unswap\nLCtl\nLGui", "Unswap Left Control and GUI", alias=["LCG_NRM"]),
    K("MAGIC_SWAP_RCTL_RGUI", "Swap\nRCtl\nRGui", "Swap Right Control and GUI", alias=["RCG_SWP"]),
    K("MAGIC_UNSWAP_RCTL_RGUI", "Unswap\nRCtl\nRGui", "Unswap Right Control and GUI", alias=["RCG_NRM"]),
    K("MAGIC_SWAP_CTL_GUI", "Swap\nCtl\nGui", "Swap Control and GUI on both sides", alias=["CG_SWAP"]),
    K("MAGIC_UNSWAP_CTL_GUI", "Unswap\nCtl\nGui", "Unswap Control and GUI on both sides", alias=["CG_NORM"]),
    K("MAGIC_TOGGLE_CTL_GUI", "Toggle\nCtl\nGui", "Toggle Control and GUI swap on both sides", alias=["CG_TOGG"]),
    K("MAGIC_SWAP_LALT_LGUI", "Swap\nLAlt\nLGui", "Swap Left Alt and GUI", alias=["LAG_SWP"]),
    K("MAGIC_UNSWAP_LALT_LGUI", "Unswap\nLAlt\nLGui", "Unswap Left Alt and GUI", alias=["LAG_NRM"]),
    K("MAGIC_SWAP_RALT_RGUI", "Swap\nRAlt\nRGui", "Swap Right Alt and GUI", alias=["RAG_SWP"]),
    K("MAGIC_UNSWAP_RALT_RGUI", "Unswap\nRAlt\nRGui", "Unswap Right Alt and GUI", alias=["RAG_NRM"]),
    K("MAGIC_SWAP_ALT_GUI", "Swap\nAlt\nGui", "Swap Alt and GUI on both sides", alias=["AG_SWAP"]),
    K("MAGIC_UNSWAP_ALT_GUI", "Unswap\nAlt\nGui", "Unswap Alt and GUI on both sides", alias=["AG_NORM"]),
    K("MAGIC_TOGGLE_ALT_GUI", "Toggle\nAlt\nGui", "Toggle Alt and GUI swap on both sides", alias=["AG_TOGG"]),
    K("MAGIC_NO_GUI", "GUI\nOff", "Disable the GUI keys", alias=["GUI_OFF"]),
    K("MAGIC_UNNO_GUI", "GUI\nOn", "Enable the GUI keys", alias=["GUI_ON"]),
    K("MAGIC_TOGGLE_GUI", "GUI\nToggle", "Toggle the GUI keys on and off", alias=["GUI_TOGG"]),
    K("MAGIC_SWAP_GRAVE_ESC", "Swap\n`\nEsc", "Swap ` and Escape", alias=["GE_SWAP"]),
    K("MAGIC_UNSWAP_GRAVE_ESC", "Unswap\n`\nEsc", "Unswap ` and Escape", alias=["GE_NORM"]),
    K("MAGIC_SWAP_BACKSLASH_BACKSPACE", "Swap\n\\\nBS", "Swap \\ and Backspace", alias=["BS_SWAP"]),
    K("MAGIC_UNSWAP_BACKSLASH_BACKSPACE", "Unswap\n\\\nBS", "Unswap \\ and Backspace", alias=["BS_NORM"]),
    K("MAGIC_HOST_NKRO", "NKRO\nOn", "Enable N-key rollover", alias=["NK_ON"]),
    K("MAGIC_UNHOST_NKRO", "NKRO\nOff", "Disable N-key rollover", alias=["NK_OFF"]),
    K("MAGIC_TOGGLE_NKRO", "NKRO\nToggle", "Toggle N-key rollover", alias=["NK_TOGG"]),
    K("MAGIC_EE_HANDS_LEFT", "EEH\nLeft", "Set the master half of a split keyboard as the left hand (for EE_HANDS)",
      alias=["EH_LEFT"]),
    K("MAGIC_EE_HANDS_RIGHT", "EEH\nRight", "Set the master half of a split keyboard as the right hand (for EE_HANDS)",
      alias=["EH_RGHT"]),

    K("AU_ON", "Audio\nON", "Audio mode on"),
    K("AU_OFF", "Audio\nOFF", "Audio mode off"),
    K("AU_TOG", "Audio\nToggle", "Toggles Audio mode"),
    K("CLICKY_TOGGLE", "Clicky\nToggle", "Toggles Audio clicky mode", alias=["CK_TOGG"]),
    K("QK_AUDIO_CLICKY_ON", "Clicky\nOn", "Turn Audio clicky on", alias=["CK_ON"]),
    K("QK_AUDIO_CLICKY_OFF", "Clicky\nOff", "Turn Audio clicky off", alias=["CK_OFF"]),
    K("CLICKY_UP", "Clicky\nUp", "Increases frequency of the clicks", alias=["CK_UP"]),
    K("CLICKY_DOWN", "Clicky\nDown", "Decreases frequency of the clicks", alias=["CK_DOWN"]),
    K("CLICKY_RESET", "Clicky\nReset", "Resets frequency to default", alias=["CK_RST"]),
    K("MU_ON", "Music\nOn", "Turns on Music Mode"),
    K("MU_OFF", "Music\nOff", "Turns off Music Mode"),
    K("MU_TOG", "Music\nToggle", "Toggles Music Mode"),
    K("MU_MOD", "Music\nCycle", "Cycles through the music modes"),
    K("QK_AUDIO_VOICE_NEXT", "Voice\nNext", "Cycle to next audio voice"),
    K("QK_AUDIO_VOICE_PREVIOUS", "Voice\nPrev", "Cycle to previous audio voice"),

    K("HPT_ON", "Haptic\nOn", "Turn haptic feedback on"),
    K("HPT_OFF", "Haptic\nOff", "Turn haptic feedback off"),
    K("HPT_TOG", "Haptic\nToggle", "Toggle haptic feedback on/off"),
    K("HPT_RST", "Haptic\nReset", "Reset haptic feedback config to default"),
    K("HPT_FBK", "Haptic\nFeed\nback", "Toggle feedback to occur on keypress, release or both"),
    K("HPT_BUZ", "Haptic\nBuzz", "Toggle solenoid buzz on/off"),
    K("HPT_MODI", "Haptic\nNext", "Go to next DRV2605L waveform"),
    K("HPT_MODD", "Haptic\nPrev", "Go to previous DRV2605L waveform"),
    K("HPT_CONT", "Haptic\nCont.", "Toggle continuous haptic mode on/off"),
    K("HPT_CONI", "Haptic\n+", "Increase DRV2605L continous haptic strength"),
    K("HPT_COND", "Haptic\n-", "Decrease DRV2605L continous haptic strength"),
    K("HPT_DWLI", "Haptic\nDwell+", "Increase Solenoid dwell time"),
    K("HPT_DWLD", "Haptic\nDwell-", "Decrease Solenoid dwell time"),

    K("KC_ASDN", "Auto-\nshift\nDown", "Lower the Auto Shift timeout variable (down)"),
    K("KC_ASUP", "Auto-\nshift\nUp", "Raise the Auto Shift timeout variable (up)"),
    K("KC_ASRP", "Auto-\nshift\nReport", "Report your current Auto Shift timeout value"),
    K("KC_ASON", "Auto-\nshift\nOn", "Turns on the Auto Shift Function"),
    K("KC_ASOFF", "Auto-\nshift\nOff", "Turns off the Auto Shift Function"),
    K("KC_ASTG", "Auto-\nshift\nToggle", "Toggles the state of the Auto Shift feature"),

    K("CMB_ON", "Combo\nOn", "Turns on Combo feature"),
    K("CMB_OFF", "Combo\nOff", "Turns off Combo feature"),
    K("CMB_TOG", "Combo\nToggle", "Toggles Combo feature on and off"),

    K("QK_CAPS_WORD_TOGGLE", "Caps\nWord", "Capitalizes until end of current word", alias=["CW_TOGG"], requires_feature="caps_word"),
    K("QK_REPEAT_KEY", "Repeat", "Repeats the last pressed key", alias=["QK_REP"], requires_feature="repeat_key"),
    K("QK_ALT_REPEAT_KEY", "Alt\nRepeat", "Alt repeats the last pressed key", alias=["QK_AREP"], requires_feature="repeat_key"),

    K("QK_LEADER", "Leader", "Start a leader key sequence", alias=["QK_LEAD"]),
    K("QK_LOCK", "Key\nLock", "Hold down the next key pressed until pressed again"),
    K("QK_SECURE_LOCK", "Secure\nLock", "Lock the keyboard"),
    K("QK_SECURE_UNLOCK", "Secure\nUnlock", "Unlock the keyboard"),
    K("QK_SECURE_TOGGLE", "Secure\nToggle", "Toggle secure state"),
    K("QK_SECURE_REQUEST", "Secure\nRequest", "Request secure unlock"),

    K("QK_ONE_SHOT_ON", "OS\nOn", "Enable one-shot keys", alias=["OS_ON"]),
    K("QK_ONE_SHOT_OFF", "OS\nOff", "Disable one-shot keys", alias=["OS_OFF"]),
    K("QK_ONE_SHOT_TOGGLE", "OS\nToggle", "Toggle one-shot keys", alias=["OS_TOGG"]),

    K("SH_T(kc)", "SH_T\n(kc)", "Tap for keycode, hold for swap hands", masked=True),
    K("SH_TOGG", "Swap\nToggle", "Toggle swap hands on/off"),
    K("SH_TT", "Swap\nTT", "Tap-toggle swap hands"),
    K("SH_MON", "Swap\nMom On", "Momentary swap on"),
    K("SH_MOFF", "Swap\nMom Off", "Momentary swap off"),
    K("SH_ON", "Swap\nOn", "Turn swap hands on"),
    K("SH_OFF", "Swap\nOff", "Turn swap hands off"),
    K("SH_OS", "Swap\nOS", "One-shot swap hands"),
]

KEYCODES_JOYSTICK = [
    K("QK_JOYSTICK_BUTTON_0", "JS_0", "Joystick Button 0", alias=["JS_0"]),
    K("QK_JOYSTICK_BUTTON_1", "JS_1", "Joystick Button 1", alias=["JS_1"]),
    K("QK_JOYSTICK_BUTTON_2", "JS_2", "Joystick Button 2", alias=["JS_2"]),
    K("QK_JOYSTICK_BUTTON_3", "JS_3", "Joystick Button 3", alias=["JS_3"]),
    K("QK_JOYSTICK_BUTTON_4", "JS_4", "Joystick Button 4", alias=["JS_4"]),
    K("QK_JOYSTICK_BUTTON_5", "JS_5", "Joystick Button 5", alias=["JS_5"]),
    K("QK_JOYSTICK_BUTTON_6", "JS_6", "Joystick Button 6", alias=["JS_6"]),
    K("QK_JOYSTICK_BUTTON_7", "JS_7", "Joystick Button 7", alias=["JS_7"]),
    K("QK_JOYSTICK_BUTTON_8", "JS_8", "Joystick Button 8", alias=["JS_8"]),
    K("QK_JOYSTICK_BUTTON_9", "JS_9", "Joystick Button 9", alias=["JS_9"]),
    K("QK_JOYSTICK_BUTTON_10", "JS_10", "Joystick Button 10", alias=["JS_10"]),
    K("QK_JOYSTICK_BUTTON_11", "JS_11", "Joystick Button 11", alias=["JS_11"]),
    K("QK_JOYSTICK_BUTTON_12", "JS_12", "Joystick Button 12", alias=["JS_12"]),
    K("QK_JOYSTICK_BUTTON_13", "JS_13", "Joystick Button 13", alias=["JS_13"]),
    K("QK_JOYSTICK_BUTTON_14", "JS_14", "Joystick Button 14", alias=["JS_14"]),
    K("QK_JOYSTICK_BUTTON_15", "JS_15", "Joystick Button 15", alias=["JS_15"]),
    K("QK_JOYSTICK_BUTTON_16", "JS_16", "Joystick Button 16", alias=["JS_16"]),
    K("QK_JOYSTICK_BUTTON_17", "JS_17", "Joystick Button 17", alias=["JS_17"]),
    K("QK_JOYSTICK_BUTTON_18", "JS_18", "Joystick Button 18", alias=["JS_18"]),
    K("QK_JOYSTICK_BUTTON_19", "JS_19", "Joystick Button 19", alias=["JS_19"]),
    K("QK_JOYSTICK_BUTTON_20", "JS_20", "Joystick Button 20", alias=["JS_20"]),
    K("QK_JOYSTICK_BUTTON_21", "JS_21", "Joystick Button 21", alias=["JS_21"]),
    K("QK_JOYSTICK_BUTTON_22", "JS_22", "Joystick Button 22", alias=["JS_22"]),
    K("QK_JOYSTICK_BUTTON_23", "JS_23", "Joystick Button 23", alias=["JS_23"]),
    K("QK_JOYSTICK_BUTTON_24", "JS_24", "Joystick Button 24", alias=["JS_24"]),
    K("QK_JOYSTICK_BUTTON_25", "JS_25", "Joystick Button 25", alias=["JS_25"]),
    K("QK_JOYSTICK_BUTTON_26", "JS_26", "Joystick Button 26", alias=["JS_26"]),
    K("QK_JOYSTICK_BUTTON_27", "JS_27", "Joystick Button 27", alias=["JS_27"]),
    K("QK_JOYSTICK_BUTTON_28", "JS_28", "Joystick Button 28", alias=["JS_28"]),
    K("QK_JOYSTICK_BUTTON_29", "JS_29", "Joystick Button 29", alias=["JS_29"]),
    K("QK_JOYSTICK_BUTTON_30", "JS_30", "Joystick Button 30", alias=["JS_30"]),
    K("QK_JOYSTICK_BUTTON_31", "JS_31", "Joystick Button 31", alias=["JS_31"]),
]

KEYCODES_PROGRAMMABLE_BUTTON = [
    K("QK_PROGRAMMABLE_BUTTON_1", "PB_1", "Programmable Button 1", alias=["PB_1"]),
    K("QK_PROGRAMMABLE_BUTTON_2", "PB_2", "Programmable Button 2", alias=["PB_2"]),
    K("QK_PROGRAMMABLE_BUTTON_3", "PB_3", "Programmable Button 3", alias=["PB_3"]),
    K("QK_PROGRAMMABLE_BUTTON_4", "PB_4", "Programmable Button 4", alias=["PB_4"]),
    K("QK_PROGRAMMABLE_BUTTON_5", "PB_5", "Programmable Button 5", alias=["PB_5"]),
    K("QK_PROGRAMMABLE_BUTTON_6", "PB_6", "Programmable Button 6", alias=["PB_6"]),
    K("QK_PROGRAMMABLE_BUTTON_7", "PB_7", "Programmable Button 7", alias=["PB_7"]),
    K("QK_PROGRAMMABLE_BUTTON_8", "PB_8", "Programmable Button 8", alias=["PB_8"]),
    K("QK_PROGRAMMABLE_BUTTON_9", "PB_9", "Programmable Button 9", alias=["PB_9"]),
    K("QK_PROGRAMMABLE_BUTTON_10", "PB_10", "Programmable Button 10", alias=["PB_10"]),
    K("QK_PROGRAMMABLE_BUTTON_11", "PB_11", "Programmable Button 11", alias=["PB_11"]),
    K("QK_PROGRAMMABLE_BUTTON_12", "PB_12", "Programmable Button 12", alias=["PB_12"]),
    K("QK_PROGRAMMABLE_BUTTON_13", "PB_13", "Programmable Button 13", alias=["PB_13"]),
    K("QK_PROGRAMMABLE_BUTTON_14", "PB_14", "Programmable Button 14", alias=["PB_14"]),
    K("QK_PROGRAMMABLE_BUTTON_15", "PB_15", "Programmable Button 15", alias=["PB_15"]),
    K("QK_PROGRAMMABLE_BUTTON_16", "PB_16", "Programmable Button 16", alias=["PB_16"]),
    K("QK_PROGRAMMABLE_BUTTON_17", "PB_17", "Programmable Button 17", alias=["PB_17"]),
    K("QK_PROGRAMMABLE_BUTTON_18", "PB_18", "Programmable Button 18", alias=["PB_18"]),
    K("QK_PROGRAMMABLE_BUTTON_19", "PB_19", "Programmable Button 19", alias=["PB_19"]),
    K("QK_PROGRAMMABLE_BUTTON_20", "PB_20", "Programmable Button 20", alias=["PB_20"]),
    K("QK_PROGRAMMABLE_BUTTON_21", "PB_21", "Programmable Button 21", alias=["PB_21"]),
    K("QK_PROGRAMMABLE_BUTTON_22", "PB_22", "Programmable Button 22", alias=["PB_22"]),
    K("QK_PROGRAMMABLE_BUTTON_23", "PB_23", "Programmable Button 23", alias=["PB_23"]),
    K("QK_PROGRAMMABLE_BUTTON_24", "PB_24", "Programmable Button 24", alias=["PB_24"]),
    K("QK_PROGRAMMABLE_BUTTON_25", "PB_25", "Programmable Button 25", alias=["PB_25"]),
    K("QK_PROGRAMMABLE_BUTTON_26", "PB_26", "Programmable Button 26", alias=["PB_26"]),
    K("QK_PROGRAMMABLE_BUTTON_27", "PB_27", "Programmable Button 27", alias=["PB_27"]),
    K("QK_PROGRAMMABLE_BUTTON_28", "PB_28", "Programmable Button 28", alias=["PB_28"]),
    K("QK_PROGRAMMABLE_BUTTON_29", "PB_29", "Programmable Button 29", alias=["PB_29"]),
    K("QK_PROGRAMMABLE_BUTTON_30", "PB_30", "Programmable Button 30", alias=["PB_30"]),
    K("QK_PROGRAMMABLE_BUTTON_31", "PB_31", "Programmable Button 31", alias=["PB_31"]),
    K("QK_PROGRAMMABLE_BUTTON_32", "PB_32", "Programmable Button 32", alias=["PB_32"]),
]

KEYCODES_STENO_CONTROL = [
    K("QK_STENO_BOLT", "Bolt", "Set Steno protocol to TX Bolt", alias=["STN_BOLT"]),
    K("QK_STENO_GEMINI", "Gemini", "Set Steno protocol to GeminiPR", alias=["STN_GEMINI"]),
    K("STN_RES1", "RES1", "Steno Res1"),
    K("STN_RES2", "RES2", "Steno Res2"),
    K("STN_PWR", "PWR", "Steno Power"),
    K("STN_FN", "FN", "Steno Function"),
]

# Left hand - matches physical steno layout
KEYCODES_STENO_LEFT = [
    # Row 1: Number bar
    K("STN_N1", "#₁", "Steno Number 1"),
    K("STN_N2", "#₂", "Steno Number 2"),
    K("STN_N3", "#₃", "Steno Number 3"),
    K("STN_N4", "#₄", "Steno Number 4"),
    K("STN_N5", "#₅", "Steno Number 5"),
    # Row 2: Upper consonants
    K("STN_S1", "S-₁", "Steno Left S", alias=["STN_SL"]),
    K("STN_TL", "T-", "Steno Left T"),
    K("STN_PL", "P-", "Steno Left P"),
    K("STN_HL", "H-", "Steno Left H"),
    K("STN_ST1", "*₁", "Steno Star 1", alias=["STN_STR"]),
    # Row 3: Lower consonants
    K("STN_S2", "S-₂", "Steno Left S (lower)"),
    K("STN_KL", "K-", "Steno Left K"),
    K("STN_WL", "W-", "Steno Left W"),
    K("STN_RL", "R-", "Steno Left R"),
    K("STN_ST2", "*₂", "Steno Star 2"),
    # Row 4: Thumbs
    K("STN_A", "-A-", "Steno Thumb A"),
    K("STN_O", "-O-", "Steno Thumb O"),
]

# Right hand - matches physical steno layout
KEYCODES_STENO_RIGHT = [
    # Row 1: Number bar
    K("STN_N7", "#₇", "Steno Number 7"),
    K("STN_N8", "#₈", "Steno Number 8"),
    K("STN_N9", "#₉", "Steno Number 9"),
    K("STN_NA", "#A", "Steno Number A"),
    K("STN_NB", "#B", "Steno Number B"),
    K("STN_NC", "#C", "Steno Number C"),
    # Row 2: Upper consonants
    K("STN_ST3", "*₃", "Steno Star 3"),
    K("STN_FR", "-F", "Steno Right F"),
    K("STN_PR", "-P", "Steno Right P"),
    K("STN_LR", "-L", "Steno Right L"),
    K("STN_TR", "-T", "Steno Right T"),
    K("STN_DR", "-D", "Steno Right D"),
    # Row 3: Lower consonants
    K("STN_ST4", "*₄", "Steno Star 4"),
    K("STN_RR", "-R", "Steno Right R"),
    K("STN_BR", "-B", "Steno Right B"),
    K("STN_GR", "-G", "Steno Right G"),
    K("STN_SR", "-S", "Steno Right S"),
    K("STN_ZR", "-Z", "Steno Right Z"),
    # Row 4: Thumbs
    K("STN_E", "-E-", "Steno Thumb E"),
    K("STN_U", "-U-", "Steno Thumb U"),
]

# Center number (between left and right)
KEYCODES_STENO_CENTER = [
    K("STN_N6", "#₆", "Steno Number 6"),
]

# Combined for backwards compatibility
KEYCODES_STENO = KEYCODES_STENO_CONTROL + KEYCODES_STENO_LEFT + KEYCODES_STENO_CENTER + KEYCODES_STENO_RIGHT

KEYCODES_BACKLIGHT = [
    K("BL_TOGG", "BL\nToggle", "Turn the backlight on or off"),
    K("BL_STEP", "BL\nCycle", "Cycle through backlight levels"),
    K("BL_BRTG", "BL\nBreath", "Toggle backlight breathing"),
    K("BL_ON", "BL On", "Set the backlight to max brightness"),
    K("BL_OFF", "BL Off", "Turn the backlight off"),
    K("BL_INC", "BL +", "Increase the backlight level"),
    K("BL_DEC", "BL - ", "Decrease the backlight level"),

    K("RGB_TOG", "RGB\nToggle", "Toggle RGB lighting on or off"),
    K("RGB_MOD", "RGB\nMode +", "Next RGB mode"),
    K("RGB_RMOD", "RGB\nMode -", "Previous RGB mode"),
    K("RGB_HUI", "Hue +", "Increase hue"),
    K("RGB_HUD", "Hue -", "Decrease hue"),
    K("RGB_SAI", "Sat +", "Increase saturation"),
    K("RGB_SAD", "Sat -", "Decrease saturation"),
    K("RGB_VAI", "Bright +", "Increase value"),
    K("RGB_VAD", "Bright -", "Decrease value"),
    K("RGB_SPI", "Effect +", "Increase RGB effect speed"),
    K("RGB_SPD", "Effect -", "Decrease RGB effect speed"),
    K("RGB_M_P", "RGB\nMode P", "RGB Mode: Plain"),
    K("RGB_M_B", "RGB\nMode B", "RGB Mode: Breathe"),
    K("RGB_M_R", "RGB\nMode R", "RGB Mode: Rainbow"),
    K("RGB_M_SW", "RGB\nMode SW", "RGB Mode: Swirl"),
    K("RGB_M_SN", "RGB\nMode SN", "RGB Mode: Snake"),
    K("RGB_M_K", "RGB\nMode K", "RGB Mode: Knight Rider"),
    K("RGB_M_X", "RGB\nMode X", "RGB Mode: Christmas"),
    K("RGB_M_G", "RGB\nMode G", "RGB Mode: Gradient"),
    K("RGB_M_T", "RGB\nMode T", "RGB Mode: Test"),

    K("RM_ON", "RGBM\nOn", "Turn on RGB Matrix"),
    K("RM_OFF", "RGBM\nOff", "Turn off RGB Matrix"),
    K("RM_TOGG", "RGBM\nTogg", "Toggle RGB Matrix on or off"),
    K("RM_NEXT", "RGBM\nNext", "Cycle through animations"),
    K("RM_PREV", "RGBM\nPrev", "Cycle through animations in reverse"),
    K("RM_HUEU", "RGBM\nHue +", "Cycle through hue"),
    K("RM_HUED", "RGBM\nHue -", "Cycle through hue in reverse"),
    K("RM_SATU", "RGBM\nSat +", "Increase the saturation"),
    K("RM_SATD", "RGBM\nSat -", "Decrease the saturation"),
    K("RM_VALU", "RGBM\nBright +", "Increase the brightness level"),
    K("RM_VALD", "RGBM\nBright -", "Decrease the brightness level"),
    K("RM_SPDU", "RGBM\nSpeed +", "Increase the animation speed"),
    K("RM_SPDD", "RGBM\nSpeed -", "Decrease the animation speed"),
]

KEYCODES_MEDIA = [
    K("KC_F13", "F13"),
    K("KC_F14", "F14"),
    K("KC_F15", "F15"),
    K("KC_F16", "F16"),
    K("KC_F17", "F17"),
    K("KC_F18", "F18"),
    K("KC_F19", "F19"),
    K("KC_F20", "F20"),
    K("KC_F21", "F21"),
    K("KC_F22", "F22"),
    K("KC_F23", "F23"),
    K("KC_F24", "F24"),

    K("KC_PWR", "Power", "System Power Down", alias=["KC_SYSTEM_POWER"]),
    K("KC_SLEP", "Sleep", "System Sleep", alias=["KC_SYSTEM_SLEEP"]),
    K("KC_WAKE", "Wake", "System Wake", alias=["KC_SYSTEM_WAKE"]),
    K("KC_EXEC", "Exec", "Execute", alias=["KC_EXECUTE"]),
    K("KC_HELP", "Help"),
    K("KC_SLCT", "Select", alias=["KC_SELECT"]),
    K("KC_STOP", "Stop"),
    K("KC_AGIN", "Again", alias=["KC_AGAIN"]),
    K("KC_UNDO", "Undo"),
    K("KC_CUT", "Cut"),
    K("KC_COPY", "Copy"),
    K("KC_PSTE", "Paste", alias=["KC_PASTE"]),
    K("KC_FIND", "Find"),

    K("KC_CALC", "Calc", "Launch Calculator (Windows)", alias=["KC_CALCULATOR"]),
    K("KC_MAIL", "Mail", "Launch Mail (Windows)"),
    K("KC_MSEL", "Media\nPlayer", "Launch Media Player (Windows)", alias=["KC_MEDIA_SELECT"]),
    K("KC_MYCM", "My\nPC", "Launch My Computer (Windows)", alias=["KC_MY_COMPUTER"]),
    K("KC_WSCH", "Browser\nSearch", "Browser Search (Windows)", alias=["KC_WWW_SEARCH"]),
    K("KC_WHOM", "Browser\nHome", "Browser Home (Windows)", alias=["KC_WWW_HOME"]),
    K("KC_WBAK", "Browser\nBack", "Browser Back (Windows)", alias=["KC_WWW_BACK"]),
    K("KC_WFWD", "Browser\nForward", "Browser Forward (Windows)", alias=["KC_WWW_FORWARD"]),
    K("KC_WSTP", "Browser\nStop", "Browser Stop (Windows)", alias=["KC_WWW_STOP"]),
    K("KC_WREF", "Browser\nRefresh", "Browser Refresh (Windows)", alias=["KC_WWW_REFRESH"]),
    K("KC_WFAV", "Browser\nFav.", "Browser Favorites (Windows)", alias=["KC_WWW_FAVORITES"]),
    K("KC_BRIU", "Bright.\nUp", "Increase the brightness of screen (Laptop)", alias=["KC_BRIGHTNESS_UP"]),
    K("KC_BRID", "Bright.\nDown", "Decrease the brightness of screen (Laptop)", alias=["KC_BRIGHTNESS_DOWN"]),

    K("KC_MPRV", "Media\nPrev", "Previous Track", alias=["KC_MEDIA_PREV_TRACK"]),
    K("KC_MNXT", "Media\nNext", "Next Track", alias=["KC_MEDIA_NEXT_TRACK"]),
    K("KC_MUTE", "Mute", "Mute Audio", alias=["KC_AUDIO_MUTE"]),
    K("KC_VOLD", "Vol -", "Volume Down", alias=["KC_AUDIO_VOL_DOWN"]),
    K("KC_VOLU", "Vol +", "Volume Up", alias=["KC_AUDIO_VOL_UP"]),
    K("KC__VOLDOWN", "Vol -\nAlt", "Volume Down Alternate"),
    K("KC__VOLUP", "Vol +\nAlt", "Volume Up Alternate"),
    K("KC_MSTP", "Media\nStop", alias=["KC_MEDIA_STOP"]),
    K("KC_MPLY", "Media\nPlay", "Play/Pause", alias=["KC_MEDIA_PLAY_PAUSE"]),
    K("KC_MRWD", "Prev\nTrack\n(macOS)", "Previous Track / Rewind (macOS)", alias=["KC_MEDIA_REWIND"]),
    K("KC_MFFD", "Next\nTrack\n(macOS)", "Next Track / Fast Forward (macOS)", alias=["KC_MEDIA_FAST_FORWARD"]),
    K("KC_EJCT", "Eject", "Eject (macOS)", alias=["KC_MEDIA_EJECT"]),

    K("KC_MS_U", "Mouse\nUp", "Mouse Cursor Up", alias=["KC_MS_UP"]),
    K("KC_MS_D", "Mouse\nDown", "Mouse Cursor Down", alias=["KC_MS_DOWN"]),
    K("KC_MS_L", "Mouse\nLeft", "Mouse Cursor Left", alias=["KC_MS_LEFT"]),
    K("KC_MS_R", "Mouse\nRight", "Mouse Cursor Right", alias=["KC_MS_RIGHT"]),
    K("KC_BTN1", "Mouse\n1", "Mouse Button 1", alias=["KC_MS_BTN1"]),
    K("KC_BTN2", "Mouse\n2", "Mouse Button 2", alias=["KC_MS_BTN2"]),
    K("KC_BTN3", "Mouse\n3", "Mouse Button 3", alias=["KC_MS_BTN3"]),
    K("KC_BTN4", "Mouse\n4", "Mouse Button 4", alias=["KC_MS_BTN4"]),
    K("KC_BTN5", "Mouse\n5", "Mouse Button 5", alias=["KC_MS_BTN5"]),
    K("KC_BTN6", "Mouse\n6", "Mouse Button 6", alias=["KC_MS_BTN6"]),
    K("KC_BTN7", "Mouse\n7", "Mouse Button 7", alias=["KC_MS_BTN7"]),
    K("KC_BTN8", "Mouse\n8", "Mouse Button 8", alias=["KC_MS_BTN8"]),
    K("KC_WH_U", "Mouse\nWheel\nUp", alias=["KC_MS_WH_UP"]),
    K("KC_WH_D", "Mouse\nWheel\nDown", alias=["KC_MS_WH_DOWN"]),
    K("KC_WH_L", "Mouse\nWheel\nLeft", alias=["KC_MS_WH_LEFT"]),
    K("KC_WH_R", "Mouse\nWheel\nRight", alias=["KC_MS_WH_RIGHT"]),
    K("KC_ACL0", "Mouse\nAccel\n0", "Set mouse acceleration to 0", alias=["KC_MS_ACCEL0"]),
    K("KC_ACL1", "Mouse\nAccel\n1", "Set mouse acceleration to 1", alias=["KC_MS_ACCEL1"]),
    K("KC_ACL2", "Mouse\nAccel\n2", "Set mouse acceleration to 2", alias=["KC_MS_ACCEL2"]),

    K("KC_LCAP", "Locking\nCaps", "Locking Caps Lock", alias=["KC_LOCKING_CAPS"]),
    K("KC_LNUM", "Locking\nNum", "Locking Num Lock", alias=["KC_LOCKING_NUM"]),
    K("KC_LSCR", "Locking\nScroll", "Locking Scroll Lock", alias=["KC_LOCKING_SCROLL"]),
]

KEYCODES_TAP_DANCE = []

KEYCODES_USER = []

KEYCODES_MACRO = []

KEYCODES_MACRO_BASE = [
    K("DYN_REC_START1", "DM1\nRec", "Dynamic Macro 1 Rec Start", alias=["DM_REC1"]),
    K("DYN_REC_START2", "DM2\nRec", "Dynamic Macro 2 Rec Start", alias=["DM_REC2"]),
    K("DYN_REC_STOP", "DM Rec\nStop", "Dynamic Macro Rec Stop", alias=["DM_RSTP"]),
    K("DYN_MACRO_PLAY1", "DM1\nPlay", "Dynamic Macro 1 Play", alias=["DM_PLY1"]),
    K("DYN_MACRO_PLAY2", "DM2\nPlay", "Dynamic Macro 2 Play", alias=["DM_PLY2"]),
]

KEYCODES_MIDI = []

# Notes by octave
KEYCODES_MIDI_NOTES = [
    K("MI_C", "MI_C", "Midi send note C"),
    K("MI_Cs", "MI_Cs", "Midi send note C#/Db", alias=["MI_Db"]),
    K("MI_D", "MI_D", "Midi send note D"),
    K("MI_Ds", "MI_Ds", "Midi send note D#/Eb", alias=["MI_Eb"]),
    K("MI_E", "MI_E", "Midi send note E"),
    K("MI_F", "MI_F", "Midi send note F"),
    K("MI_Fs", "MI_Fs", "Midi send note F#/Gb", alias=["MI_Gb"]),
    K("MI_G", "MI_G", "Midi send note G"),
    K("MI_Gs", "MI_Gs", "Midi send note G#/Ab", alias=["MI_Ab"]),
    K("MI_A", "MI_A", "Midi send note A"),
    K("MI_As", "MI_As", "Midi send note A#/Bb", alias=["MI_Bb"]),
    K("MI_B", "MI_B", "Midi send note B"),

    K("MI_C_1", "MI_C_1", "Midi send note C1"),
    K("MI_Cs_1", "MI_Cs_1", "Midi send note C#1/Db1", alias=["MI_Db_1"]),
    K("MI_D_1", "MI_D_1", "Midi send note D1"),
    K("MI_Ds_1", "MI_Ds_1", "Midi send note D#1/Eb1", alias=["MI_Eb_1"]),
    K("MI_E_1", "MI_E_1", "Midi send note E1"),
    K("MI_F_1", "MI_F_1", "Midi send note F1"),
    K("MI_Fs_1", "MI_Fs_1", "Midi send note F#1/Gb1", alias=["MI_Gb_1"]),
    K("MI_G_1", "MI_G_1", "Midi send note G1"),
    K("MI_Gs_1", "MI_Gs_1", "Midi send note G#1/Ab1", alias=["MI_Ab_1"]),
    K("MI_A_1", "MI_A_1", "Midi send note A1"),
    K("MI_As_1", "MI_As_1", "Midi send note A#1/Bb1", alias=["MI_Bb_1"]),
    K("MI_B_1", "MI_B_1", "Midi send note B1"),

    K("MI_C_2", "MI_C_2", "Midi send note C2"),
    K("MI_Cs_2", "MI_Cs_2", "Midi send note C#2/Db2", alias=["MI_Db_2"]),
    K("MI_D_2", "MI_D_2", "Midi send note D2"),
    K("MI_Ds_2", "MI_Ds_2", "Midi send note D#2/Eb2", alias=["MI_Eb_2"]),
    K("MI_E_2", "MI_E_2", "Midi send note E2"),
    K("MI_F_2", "MI_F_2", "Midi send note F2"),
    K("MI_Fs_2", "MI_Fs_2", "Midi send note F#2/Gb2", alias=["MI_Gb_2"]),
    K("MI_G_2", "MI_G_2", "Midi send note G2"),
    K("MI_Gs_2", "MI_Gs_2", "Midi send note G#2/Ab2", alias=["MI_Ab_2"]),
    K("MI_A_2", "MI_A_2", "Midi send note A2"),
    K("MI_As_2", "MI_As_2", "Midi send note A#2/Bb2", alias=["MI_Bb_2"]),
    K("MI_B_2", "MI_B_2", "Midi send note B2"),

    K("MI_C_3", "MI_C_3", "Midi send note C3"),
    K("MI_Cs_3", "MI_Cs_3", "Midi send note C#3/Db3", alias=["MI_Db_3"]),
    K("MI_D_3", "MI_D_3", "Midi send note D3"),
    K("MI_Ds_3", "MI_Ds_3", "Midi send note D#3/Eb3", alias=["MI_Eb_3"]),
    K("MI_E_3", "MI_E_3", "Midi send note E3"),
    K("MI_F_3", "MI_F_3", "Midi send note F3"),
    K("MI_Fs_3", "MI_Fs_3", "Midi send note F#3/Gb3", alias=["MI_Gb_3"]),
    K("MI_G_3", "MI_G_3", "Midi send note G3"),
    K("MI_Gs_3", "MI_Gs_3", "Midi send note G#3/Ab3", alias=["MI_Ab_3"]),
    K("MI_A_3", "MI_A_3", "Midi send note A3"),
    K("MI_As_3", "MI_As_3", "Midi send note A#3/Bb3", alias=["MI_Bb_3"]),
    K("MI_B_3", "MI_B_3", "Midi send note B3"),

    K("MI_C_4", "MI_C_4", "Midi send note C4"),
    K("MI_Cs_4", "MI_Cs_4", "Midi send note C#4/Db4", alias=["MI_Db_4"]),
    K("MI_D_4", "MI_D_4", "Midi send note D4"),
    K("MI_Ds_4", "MI_Ds_4", "Midi send note D#4/Eb4", alias=["MI_Eb_4"]),
    K("MI_E_4", "MI_E_4", "Midi send note E4"),
    K("MI_F_4", "MI_F_4", "Midi send note F4"),
    K("MI_Fs_4", "MI_Fs_4", "Midi send note F#4/Gb4", alias=["MI_Gb_4"]),
    K("MI_G_4", "MI_G_4", "Midi send note G4"),
    K("MI_Gs_4", "MI_Gs_4", "Midi send note G#4/Ab4", alias=["MI_Ab_4"]),
    K("MI_A_4", "MI_A_4", "Midi send note A4"),
    K("MI_As_4", "MI_As_4", "Midi send note A#4/Bb4", alias=["MI_Bb_4"]),
    K("MI_B_4", "MI_B_4", "Midi send note B4"),

    K("MI_C_5", "MI_C_5", "Midi send note C5"),
    K("MI_Cs_5", "MI_Cs_5", "Midi send note C#5/Db5", alias=["MI_Db_5"]),
    K("MI_D_5", "MI_D_5", "Midi send note D5"),
    K("MI_Ds_5", "MI_Ds_5", "Midi send note D#5/Eb5", alias=["MI_Eb_5"]),
    K("MI_E_5", "MI_E_5", "Midi send note E5"),
    K("MI_F_5", "MI_F_5", "Midi send note F5"),
    K("MI_Fs_5", "MI_Fs_5", "Midi send note F#5/Gb5", alias=["MI_Gb_5"]),
    K("MI_G_5", "MI_G_5", "Midi send note G5"),
    K("MI_Gs_5", "MI_Gs_5", "Midi send note G#5/Ab5", alias=["MI_Ab_5"]),
    K("MI_A_5", "MI_A_5", "Midi send note A5"),
    K("MI_As_5", "MI_As_5", "Midi send note A#5/Bb5", alias=["MI_Bb_5"]),
    K("MI_B_5", "MI_B_5", "Midi send note B5"),

    K("MI_ALLOFF", "MI_ALLOFF", "Midi send all notes OFF"),
]

KEYCODES_MIDI_OCTAVE = [
    K("MI_OCT_N2", "MI_OCN2", "Midi set octave to -2"),
    K("MI_OCT_N1", "MI_OCN1", "Midi set octave to -1"),
    K("MI_OCT_0", "MI_OC0", "Midi set octave to 0"),
    K("MI_OCT_1", "MI_OC1", "Midi set octave to 1"),
    K("MI_OCT_2", "MI_OC2", "Midi set octave to 2"),
    K("MI_OCT_3", "MI_OC3", "Midi set octave to 3"),
    K("MI_OCT_4", "MI_OC4", "Midi set octave to 4"),
    K("MI_OCT_5", "MI_OC5", "Midi set octave to 5"),
    K("MI_OCT_6", "MI_OC6", "Midi set octave to 6"),
    K("MI_OCT_7", "MI_OC7", "Midi set octave to 7"),
    K("MI_OCTD", "MI_OCTD", "Midi move down an octave"),
    K("MI_OCTU", "MI_OCTU", "Midi move up an octave"),
]

KEYCODES_MIDI_TRANSPOSE = [
    K("MI_TRNS_N6", "MI_TRN-6", "Midi set transposition to -6 semitones"),
    K("MI_TRNS_N5", "MI_TRN-5", "Midi set transposition to -5 semitones"),
    K("MI_TRNS_N4", "MI_TRN-4", "Midi set transposition to -4 semitones"),
    K("MI_TRNS_N3", "MI_TRN-3", "Midi set transposition to -3 semitones"),
    K("MI_TRNS_N2", "MI_TRN-2", "Midi set transposition to -2 semitones"),
    K("MI_TRNS_N1", "MI_TRN-1", "Midi set transposition to -1 semitones"),
    K("MI_TRNS_0", "MI_TRN0", "Midi set no transposition"),
    K("MI_TRNS_1", "MI_TRN+1", "Midi set transposition to +1 semitones"),
    K("MI_TRNS_2", "MI_TRN+2", "Midi set transposition to +2 semitones"),
    K("MI_TRNS_3", "MI_TRN+3", "Midi set transposition to +3 semitones"),
    K("MI_TRNS_4", "MI_TRN+4", "Midi set transposition to +4 semitones"),
    K("MI_TRNS_5", "MI_TRN+5", "Midi set transposition to +5 semitones"),
    K("MI_TRNS_6", "MI_TRN+6", "Midi set transposition to +6 semitones"),
    K("MI_TRNSD", "MI_TRNSD", "Midi decrease transposition"),
    K("MI_TRNSU", "MI_TRNSU", "Midi increase transposition"),
]

KEYCODES_MIDI_VELOCITY = [
    K("MI_VEL_1", "MI_VEL1", "Midi set velocity to 0", alias=["MI_VEL_0"]),
    K("MI_VEL_2", "MI_VEL2", "Midi set velocity to 25"),
    K("MI_VEL_3", "MI_VEL3", "Midi set velocity to 38"),
    K("MI_VEL_4", "MI_VEL4", "Midi set velocity to 51"),
    K("MI_VEL_5", "MI_VEL5", "Midi set velocity to 64"),
    K("MI_VEL_6", "MI_VEL6", "Midi set velocity to 76"),
    K("MI_VEL_7", "MI_VEL7", "Midi set velocity to 89"),
    K("MI_VEL_8", "MI_VEL8", "Midi set velocity to 102"),
    K("MI_VEL_9", "MI_VEL9", "Midi set velocity to 114"),
    K("MI_VEL_10", "MI_VEL10", "Midi set velocity to 127"),
    K("MI_VELD", "MI_VELD", "Midi decrease velocity"),
    K("MI_VELU", "MI_VELU", "Midi increase velocity"),
]

KEYCODES_MIDI_CHANNEL = [
    K("MI_CH1", "MI_CH1", "Midi set channel to 1"),
    K("MI_CH2", "MI_CH2", "Midi set channel to 2"),
    K("MI_CH3", "MI_CH3", "Midi set channel to 3"),
    K("MI_CH4", "MI_CH4", "Midi set channel to 4"),
    K("MI_CH5", "MI_CH5", "Midi set channel to 5"),
    K("MI_CH6", "MI_CH6", "Midi set channel to 6"),
    K("MI_CH7", "MI_CH7", "Midi set channel to 7"),
    K("MI_CH8", "MI_CH8", "Midi set channel to 8"),
    K("MI_CH9", "MI_CH9", "Midi set channel to 9"),
    K("MI_CH10", "MI_CH10", "Midi set channel to 10"),
    K("MI_CH11", "MI_CH11", "Midi set channel to 11"),
    K("MI_CH12", "MI_CH12", "Midi set channel to 12"),
    K("MI_CH13", "MI_CH13", "Midi set channel to 13"),
    K("MI_CH14", "MI_CH14", "Midi set channel to 14"),
    K("MI_CH15", "MI_CH15", "Midi set channel to 15"),
    K("MI_CH16", "MI_CH16", "Midi set channel to 16"),
    K("MI_CHD", "MI_CHD", "Midi decrease channel"),
    K("MI_CHU", "MI_CHU", "Midi increase channel"),
]

KEYCODES_MIDI_PEDAL = [
    K("MI_SUS", "MI_SUS", "Midi Sustain"),
    K("MI_PORT", "MI_PORT", "Midi Portmento"),
    K("MI_SOST", "MI_SOST", "Midi Sostenuto"),
    K("MI_SOFT", "MI_SOFT", "Midi Soft Pedal"),
    K("MI_LEG", "MI_LEG", "Midi Legato"),
    K("MI_MOD", "MI_MOD", "Midi Modulation"),
    K("MI_MODSD", "MI_MODSD", "Midi decrease modulation speed"),
    K("MI_MODSU", "MI_MODSU", "Midi increase modulation speed"),
    K("MI_BENDD", "MI_BENDD", "Midi bend pitch down"),
    K("MI_BENDU", "MI_BENDU", "Midi bend pitch up"),
]

# Backwards compatibility aliases
KEYCODES_MIDI_BASIC = KEYCODES_MIDI_NOTES
KEYCODES_MIDI_ADVANCED = (KEYCODES_MIDI_OCTAVE + KEYCODES_MIDI_TRANSPOSE +
                          KEYCODES_MIDI_VELOCITY + KEYCODES_MIDI_CHANNEL + KEYCODES_MIDI_PEDAL)

KEYCODES_HIDDEN = []
for x in range(256):
    KEYCODES_HIDDEN.append(K("TD({})".format(x), "TD({})".format(x)))

KEYCODES = []
KEYCODES_MAP = dict()
RAWCODES_MAP = dict()

K = None


def recreate_keycodes():
    """ Regenerates global KEYCODES array """

    KEYCODES.clear()
    KEYCODES.extend(KEYCODES_SPECIAL + KEYCODES_BASIC + KEYCODES_SHIFTED + KEYCODES_ISO + KEYCODES_LAYERS +
                    KEYCODES_BOOT + KEYCODES_MODIFIERS + KEYCODES_QUANTUM + KEYCODES_BACKLIGHT + KEYCODES_MEDIA +
                    KEYCODES_TAP_DANCE + KEYCODES_MACRO + KEYCODES_USER + KEYCODES_HIDDEN + KEYCODES_MIDI +
                    KEYCODES_JOYSTICK + KEYCODES_PROGRAMMABLE_BUTTON + KEYCODES_STENO)
    KEYCODES_MAP.clear()
    RAWCODES_MAP.clear()
    for keycode in KEYCODES:
        KEYCODES_MAP[keycode.qmk_id.replace("(kc)", "")] = keycode
        RAWCODES_MAP[Keycode.deserialize(keycode.qmk_id)] = keycode


def create_user_keycodes():
    """Create hidden USER keycodes for decoding purposes when no custom keycodes are defined."""
    KEYCODES_USER.clear()
    for x in range(64):
        kc = Keycode(
            "USER{:02}".format(x),
            "USER{:02}".format(x),
            "User keycode {}".format(x)
        )
        kc.hidden = True
        KEYCODES_USER.append(kc)


def create_custom_user_keycodes(custom_keycodes):
    KEYCODES_USER.clear()
    # Create keycodes for custom entries - only show those with actual names
    for x, c_keycode in enumerate(custom_keycodes):
        default_name = "USER{:02}".format(x)
        short_name = c_keycode.get("shortName") or default_name
        kc = Keycode(
            default_name,
            short_name,
            c_keycode.get("title") or default_name,
            alias=[c_keycode.get("name") or default_name]
        )
        # Hide keycodes that don't have a meaningful custom name
        if short_name == default_name:
            kc.hidden = True
        KEYCODES_USER.append(kc)
    # Create hidden keycodes for remaining slots (for decoding, not shown in UI)
    for x in range(len(custom_keycodes), 64):
        kc = Keycode(
            "USER{:02}".format(x),
            "USER{:02}".format(x),
            "User keycode {}".format(x)
        )
        kc.hidden = True
        KEYCODES_USER.append(kc)


def create_macro_keycodes(count=128):
    """Create default macro keycodes for .vil loading compatibility"""
    KEYCODES_MACRO.clear()
    for x in range(count):
        qmk_id = "M{}".format(x)
        KEYCODES_MACRO.append(Keycode(qmk_id, qmk_id))
    for x, kc in enumerate(KEYCODES_MACRO_BASE):
        KEYCODES_MACRO.append(kc)


def create_midi_keycodes(midiSettingLevel):
    KEYCODES_MIDI.clear()

    if midiSettingLevel == "basic" or midiSettingLevel == "advanced":
        KEYCODES_MIDI.extend(KEYCODES_MIDI_BASIC)

    if midiSettingLevel == "advanced":
        KEYCODES_MIDI.extend(KEYCODES_MIDI_ADVANCED)


def recreate_keyboard_keycodes(keyboard):
    """ Generates keycodes based on information the keyboard provides (e.g. layer keycodes, macros) """

    # VIA protocol 12+ uses v6 keycode format (QK_MOD_TAP at 0x2000)
    # Earlier protocols used v5 format (QK_MOD_TAP at 0x6000)
    Keycode.protocol = 6 if keyboard.via_protocol >= 12 else 5

    layers = keyboard.layers

    def generate_keycodes_for_mask(label, description, requires_feature=None):
        keycodes = []
        for layer in range(layers):
            lbl = "{}({})".format(label, layer)
            keycodes.append(Keycode(lbl, lbl, description, requires_feature=requires_feature))
        return keycodes

    KEYCODES_LAYERS.clear()
    KEYCODES_LAYERS.append(Keycode("QK_LAYER_LOCK", "Layer\nLock",
            "Locks the current layer", alias=["QK_LLCK"], requires_feature="layer_lock"))

    if layers >= 4:
        KEYCODES_LAYERS.append(Keycode("TL_LOWR", "Tri\nLower", "Tri-layer lower (MO(1), activates layer 3 with TL_UPPR)", alias=["FN_MO13"]))
        KEYCODES_LAYERS.append(Keycode("TL_UPPR", "Tri\nUpper", "Tri-layer upper (MO(2), activates layer 3 with TL_LOWR)", alias=["FN_MO23"]))

    KEYCODES_LAYERS.extend(
        generate_keycodes_for_mask("MO",
                                   "Momentarily turn on layer when pressed (requires KC_TRNS on destination layer)"))
    KEYCODES_LAYERS.extend(
        generate_keycodes_for_mask("DF",
                                   "Set the base (default) layer"))
    KEYCODES_LAYERS.extend(
        generate_keycodes_for_mask("PDF",
                                   "Persistently set the base (default) layer",
                                   requires_feature="persistent_default_layer"))
    KEYCODES_LAYERS.extend(
        generate_keycodes_for_mask("TG",
                                   "Toggle layer on or off"))
    KEYCODES_LAYERS.extend(
        generate_keycodes_for_mask("TT",
                                   "Normally acts like MO unless it's tapped multiple times, which toggles layer on"))
    KEYCODES_LAYERS.extend(
        generate_keycodes_for_mask("OSL",
                                   "Momentarily activates layer until a key is pressed"))
    KEYCODES_LAYERS.extend(
        generate_keycodes_for_mask("TO",
                                   "Turns on layer and turns off all other layers, except the default layer"))

    for x in range(min(layers, 16)):
        KEYCODES_LAYERS.append(Keycode("LT{}(kc)".format(x), "LT {}\n(kc)".format(x),
                                       "kc on tap, switch to layer {} while held".format(x), masked=True))

    KEYCODES_MACRO.clear()
    for x in range(keyboard.macro_count):
        qmk_id = "M{}".format(x)
        # Try to get macro preview text if available
        preview = keyboard.get_macro_preview(x) if hasattr(keyboard, 'get_macro_preview') else qmk_id
        KEYCODES_MACRO.append(Keycode(qmk_id, preview))

    for x, kc in enumerate(KEYCODES_MACRO_BASE):
        KEYCODES_MACRO.append(kc)

    KEYCODES_TAP_DANCE.clear()
    for x in range(keyboard.tap_dance_count):
        lbl = "TD({})".format(x)
        KEYCODES_TAP_DANCE.append(Keycode(lbl, lbl, "Tap dance keycode"))

    # Check if custom keycodes are defined in keyboard, and if so add them to user keycodes
    if keyboard.custom_keycodes is not None and len(keyboard.custom_keycodes) > 0:
        create_custom_user_keycodes(keyboard.custom_keycodes)
    else:
        create_user_keycodes()

    create_midi_keycodes(keyboard.midi)

    recreate_keycodes()

    # Hide keycodes where .requires_feature isn't supported by the keyboard.
    # Preserve keycodes that were already marked hidden (e.g., unused USER slots).
    for kc in KEYCODES:
        if not kc.is_supported_by(keyboard):
            kc.hidden = True


# Initialize USER and MACRO keycodes at module load for .vil loading compatibility
create_user_keycodes()
create_macro_keycodes()
recreate_keycodes()
