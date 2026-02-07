# coding: utf-8

# SPDX-License-Identifier: GPL-2.0-or-later

"""
Compatibility layer for exporting layouts in vial-gui (.vil) format.

This module handles the keycode and format differences between Viable (.viable)
and vial-gui (.vil) file formats to enable interoperability.

Key Differences:
1. VIA Protocol: GUI uses v12 (v6 keycodes), vial-gui uses v9 (v5 keycodes)
2. USER keycodes: GUI uses 0x7E40-0x7E7F (QK_USER), vial-gui uses 0x7E00-0x7E3F (QK_KB)
3. STN_FN: GUI uses 0x74C0, vial-gui uses 0x74EA
4. File structure: vial-gui uses 'vial_protocol' instead of 'viable_protocol'
5. GUI has additional features vial-gui doesn't support (leader, oneshot config, custom_values)

Keycode Range Differences (v6 -> v5):
- QK_MACRO: 0x7700-0x77FF -> 0x5F12-0x6011
- QK_MOD_TAP: 0x2000-0x3FFF -> 0x6000-0x7FFF
- QK_LAYER_MOD: 0x5000-0x51FF -> 0x5900-0x59FF
- QK_TO: 0x5200-0x521F -> 0x5000-0x501F
- QK_MOMENTARY: 0x5220-0x523F -> 0x5100-0x511F
- QK_DEF_LAYER: 0x5240-0x525F -> 0x5200-0x521F
- QK_TOGGLE_LAYER: 0x5260-0x527F -> 0x5300-0x531F
- QK_ONE_SHOT_LAYER: 0x5280-0x529F -> 0x5400-0x541F
- QK_ONE_SHOT_MOD: 0x52A0-0x52BF -> 0x5500-0x551F
- QK_LAYER_TAP_TOGGLE: 0x52C0-0x52DF -> 0x5800-0x581F
"""

# Protocol versions
VIA_PROTOCOL_V5 = 9   # vial-qmk uses VIA protocol 9 (v5 keycodes)
VIA_PROTOCOL_V6 = 12  # Current QMK uses VIA protocol 12 (v6 keycodes)
VIAL_PROTOCOL_MAX = 6  # Maximum vial protocol version supported by vial-gui

# GUI-only keycode strings that vial-gui doesn't have definitions for.
# These will be converted to KC_NO when exporting to .vil format.
#
# Note: Many keycodes have fake 0x999... values in vial-gui's keycodes_v5.py,
# but they still have STRING definitions and can be stored/loaded from .vil files.
# Only keycodes WITHOUT definitions in vial-gui should be listed here.
UNSUPPORTED_KEYCODE_STRINGS = {
    # Leader key (GUI extension - vial-gui doesn't have QK_LEADER)
    "QK_LEADER",
    # One-shot toggles (GUI extension - vial-gui doesn't have these)
    "QK_ONE_SHOT_ON",
    "QK_ONE_SHOT_OFF",
    "QK_ONE_SHOT_TOGGLE",
    # Swap hands keycodes (not defined in vial-gui's keycodes.py)
    "SH_TOGG",
    "SH_TT",
    "SH_MON",
    "SH_MOFF",
    "SH_OFF",
    "SH_ON",
    "SH_OS",
}

# Prefixes for parametric keycodes that vial-gui doesn't support
UNSUPPORTED_KEYCODE_PREFIXES = (
    "SH_T(",  # Swap hands tap - SH_T(KC_A), etc. - not in vial-gui
)


def translate_keycode_string_to_vil(kc_string):
    """
    Translate a keycode string to vial-gui compatible format.

    Args:
        kc_string: Keycode string like "KC_A", "MO(1)", "SH_TOGG", etc.

    Returns:
        tuple: (translated_string, was_changed)
    """
    if not isinstance(kc_string, str):
        return kc_string, False

    # Check exact matches
    if kc_string in UNSUPPORTED_KEYCODE_STRINGS:
        return "KC_NO", True

    # Check prefix matches (for parametric keycodes like SH_T(KC_A))
    for prefix in UNSUPPORTED_KEYCODE_PREFIXES:
        if kc_string.startswith(prefix):
            return "KC_NO", True

    return kc_string, False


def serialize_keycode_v5(code):
    """
    Serialize an integer keycode to string using v5 protocol.

    Args:
        code: Integer keycode in v5 format

    Returns:
        String keycode if found, otherwise the integer unchanged
    """
    from keycodes.keycodes import Keycode

    # Temporarily switch to v5 protocol for serialization
    old_protocol = Keycode.protocol
    try:
        Keycode.protocol = 5
        return Keycode.serialize(code)
    finally:
        Keycode.protocol = old_protocol


def translate_keycode_for_vil(kc):
    """
    Translate a keycode (string or integer) to vial-gui compatible format.

    For strings: checks if unsupported and converts to KC_NO
    For integers: serialize to string first (portable), only translate v6->v5
                  if no string representation exists

    Args:
        kc: Keycode as string ("KC_A") or integer (0x04)

    Returns:
        tuple: (translated_keycode, was_changed, original_if_changed)
    """
    from keycodes.keycodes import Keycode

    if isinstance(kc, str):
        translated, changed = translate_keycode_string_to_vil(kc)
        return translated, changed, kc if changed else None

    # Integer keycode - first try to serialize with current protocol to get string
    # String keycodes like "STN_N1", "MO(1)", "KC_A" are portable between protocols
    serialized = Keycode.serialize(kc)

    if isinstance(serialized, str):
        # Successfully converted to string - check if unsupported in vial-gui
        translated, changed = translate_keycode_string_to_vil(serialized)
        if changed:
            return translated, True, serialized
        return translated, False, None

    # No string representation - translate integer v6->v5 for vial-gui compatibility
    v5_code = translate_keycode_to_vil(kc)
    changed = v5_code != kc
    return v5_code, changed, kc if changed else None


def translate_layout_keycodes_to_vil(layout_data):
    """
    Translate all keycodes in a layout to vial-gui compatible format.

    Handles both string keycodes ("KC_A") and integer keycodes (0x04).
    Integers are serialized to strings where possible, otherwise translated v6->v5.

    Args:
        layout_data: 3D list of keycodes [layers][rows][cols]

    Returns:
        tuple: (translated_layout, set of dropped keycode names)
    """
    dropped = set()
    result = []

    for layer in layout_data:
        new_layer = []
        result.append(new_layer)
        for row in layer:
            new_row = []
            new_layer.append(new_row)
            for kc in row:
                translated, was_changed, original = translate_keycode_for_vil(kc)
                if was_changed and original is not None:
                    dropped.add(str(original))
                new_row.append(translated)

    return result, dropped


def translate_encoder_keycodes_to_vil(encoder_data):
    """
    Translate all keycodes in encoder layout to vial-gui compatible format.

    Handles both string keycodes ("KC_A") and integer keycodes (0x04).
    Integers are serialized to strings where possible, otherwise translated v6->v5.

    Args:
        encoder_data: 3D list of encoder keycode pairs [layers][encoders][[cw, ccw]]

    Returns:
        tuple: (translated_layout, set of dropped keycode names)
    """
    dropped = set()
    result = []

    for layer in encoder_data:
        new_layer = []
        result.append(new_layer)
        for encoder_pair in layer:
            new_pair = []
            for kc in encoder_pair:
                translated, was_changed, original = translate_keycode_for_vil(kc)
                if was_changed and original is not None:
                    dropped.add(str(original))
                new_pair.append(translated)
            new_layer.append(new_pair)

    return result, dropped

# Keycode translation from GUI format to vial-gui format
# Maps: GUI keycode value -> vial-gui keycode value

# USER keycodes: shift from QK_USER (0x7E40) to QK_KB (0x7E00)
QK_USER_GUI = 0x7E40
QK_KB_VIAL = 0x7E00
QK_USER_MAX_OFFSET = 0x3F  # 64 user keycodes (USER00-USER63)

# STN_FN difference
STN_FN_GUI = 0x74C0
STN_FN_VIAL = 0x74EA

# Swap Hands keycodes (only in GUI, not in vial-gui)
# These will be converted to KC_NO (0x00) as vial-gui doesn't support them
SWAP_HANDS_KEYCODES = {
    0x56F0,  # SH_TOGG
    0x56F1,  # SH_TT
    0x56F2,  # SH_MON
    0x56F3,  # SH_MOFF
    0x56F4,  # SH_OFF
    0x56F5,  # SH_ON
    0x56F6,  # SH_OS
}

# Swap Hands Tap keycodes (0x5600-0x56EF)
QK_SWAP_HANDS_TAP = 0x5600
QK_SWAP_HANDS_TAP_MAX = 0x56EF

# One-shot toggle keycodes (only in GUI)
ONESHOT_TOGGLE_KEYCODES = {
    0x7C5A,  # QK_ONE_SHOT_ON
    0x7C5B,  # QK_ONE_SHOT_OFF
    0x7C5C,  # QK_ONE_SHOT_TOGGLE
}

# Leader key (only in GUI with extended support)
QK_LEADER = 0x7C58


def translate_keycode_v6_to_v5(code):
    """
    Translate a v6 keycode (VIA protocol 12) to v5 format (VIA protocol 9).

    This is the inverse of translate_keycode_v5_to_v6 in keycodes.py.

    Args:
        code: Integer keycode in v6 format

    Returns:
        Integer keycode in v5 format
    """
    if not isinstance(code, int):
        return code

    if code == -1:
        return -1

    # QK_MACRO: 0x7700-0x77FF -> 0x5F12-0x6011
    # v6 has up to 256 macros, v5 has up to 238 in non-overlapping range
    if 0x7700 <= code <= 0x77FF:
        macro_idx = code - 0x7700
        return 0x5F12 + macro_idx

    # QK_MOD_TAP: 0x2000-0x3FFF -> 0x6000-0x7FFF
    if 0x2000 <= code <= 0x3FFF:
        return (code - 0x2000) + 0x6000

    # QK_LAYER_MOD: 0x5000-0x51FF -> 0x5900-0x59FF
    # v6 format: layer in bits 5-8, mod in bits 0-4 (5-bit mods)
    # v5 format: layer in bits 4-7, mod in bits 0-3 (4-bit mods, LHS only)
    if 0x5000 <= code <= 0x51FF:
        v6_offset = code - 0x5000
        layer = (v6_offset >> 5) & 0xF
        mod = v6_offset & 0xF  # Only keep 4 bits of mod for v5
        return 0x5900 | (layer << 4) | mod

    # QK_TO: 0x5200-0x521F -> 0x5000-0x501F
    if 0x5200 <= code <= 0x521F:
        layer = code & 0x1F
        return 0x5000 + layer

    # QK_MOMENTARY: 0x5220-0x523F -> 0x5100-0x511F
    if 0x5220 <= code <= 0x523F:
        layer = code & 0x1F
        return 0x5100 + layer

    # QK_DEF_LAYER: 0x5240-0x525F -> 0x5200-0x521F
    if 0x5240 <= code <= 0x525F:
        layer = code & 0x1F
        return 0x5200 + layer

    # QK_TOGGLE_LAYER: 0x5260-0x527F -> 0x5300-0x531F
    if 0x5260 <= code <= 0x527F:
        layer = code & 0x1F
        return 0x5300 + layer

    # QK_ONE_SHOT_LAYER: 0x5280-0x529F -> 0x5400-0x541F
    if 0x5280 <= code <= 0x529F:
        layer = code & 0x1F
        return 0x5400 + layer

    # QK_ONE_SHOT_MOD: 0x52A0-0x52BF -> 0x5500-0x551F
    if 0x52A0 <= code <= 0x52BF:
        mod = code & 0x1F
        return 0x5500 + mod

    # QK_LAYER_TAP_TOGGLE: 0x52C0-0x52DF -> 0x5800-0x581F
    if 0x52C0 <= code <= 0x52DF:
        layer = code & 0x1F
        return 0x5800 + layer

    # No translation needed
    return code


def translate_keycode_to_vil(code):
    """
    Translate a GUI keycode to vial-gui format.

    This applies both:
    1. v6 to v5 keycode translation (for VIA protocol compatibility)
    2. GUI-specific keycode translations (USER, STN_FN, etc.)

    Args:
        code: Integer keycode in GUI format (v6)

    Returns:
        Integer keycode in vial-gui format (v5)
    """
    if not isinstance(code, int):
        return code

    # First handle GUI-specific keycodes that don't exist in vial-gui

    # Swap Hands special keycodes -> KC_NO
    if code in SWAP_HANDS_KEYCODES:
        return 0x00  # KC_NO

    # Swap Hands Tap keycodes (SH_T(kc)) -> KC_NO
    if QK_SWAP_HANDS_TAP <= code <= QK_SWAP_HANDS_TAP_MAX:
        return 0x00  # KC_NO

    # One-shot toggles -> KC_NO
    if code in ONESHOT_TOGGLE_KEYCODES:
        return 0x00  # KC_NO

    # Leader key -> KC_NO (vial-gui doesn't have dynamic leader support)
    if code == QK_LEADER:
        return 0x00  # KC_NO

    # Apply v6 to v5 keycode translation
    code = translate_keycode_v6_to_v5(code)

    # USER keycodes: 0x7E40-0x7E7F -> 0x7E00-0x7E3F
    if QK_USER_GUI <= code <= (QK_USER_GUI + QK_USER_MAX_OFFSET):
        return code - QK_USER_GUI + QK_KB_VIAL

    # STN_FN: 0x74C0 -> 0x74EA
    if code == STN_FN_GUI:
        return STN_FN_VIAL

    return code


def translate_keycode_from_vil(code):
    """
    Translate a vial-gui keycode to GUI format.

    This is the inverse of translate_keycode_to_vil, used when loading .vil files.
    Note: Some translations are lossy (swap hands, leader, etc.), so this is
    primarily for USER and STN_FN keycodes.

    Args:
        code: Integer keycode in vial-gui format

    Returns:
        Integer keycode in GUI format
    """
    if not isinstance(code, int):
        return code

    # USER keycodes: 0x7E00-0x7E3F -> 0x7E40-0x7E7F
    if QK_KB_VIAL <= code <= (QK_KB_VIAL + QK_USER_MAX_OFFSET):
        return code - QK_KB_VIAL + QK_USER_GUI

    # STN_FN: 0x74EA -> 0x74C0
    if code == STN_FN_VIAL:
        return STN_FN_GUI

    # No translation needed
    return code


def get_unsupported_keycodes(layout_data):
    """
    Scan a layout for keycodes that will be lost when converting to .vil format.

    Args:
        layout_data: 3D list of keycodes [layers][rows][cols]

    Returns:
        set of unsupported keycode values found in the layout
    """
    unsupported = set()

    for layer in layout_data:
        for row in layer:
            for code in row:
                if not isinstance(code, int):
                    continue

                # Check for swap hands
                if code in SWAP_HANDS_KEYCODES:
                    unsupported.add(code)
                elif QK_SWAP_HANDS_TAP <= code <= QK_SWAP_HANDS_TAP_MAX:
                    unsupported.add(code)

                # Check for oneshot toggles
                if code in ONESHOT_TOGGLE_KEYCODES:
                    unsupported.add(code)

                # Check for leader
                if code == QK_LEADER:
                    unsupported.add(code)

    return unsupported


def keycode_to_name(code):
    """
    Get a human-readable name for an unsupported keycode.

    Args:
        code: Integer keycode

    Returns:
        String name of the keycode
    """
    names = {
        0x56F0: "SH_TOGG",
        0x56F1: "SH_TT",
        0x56F2: "SH_MON",
        0x56F3: "SH_MOFF",
        0x56F4: "SH_OFF",
        0x56F5: "SH_ON",
        0x56F6: "SH_OS",
        0x7C5A: "QK_ONE_SHOT_ON",
        0x7C5B: "QK_ONE_SHOT_OFF",
        0x7C5C: "QK_ONE_SHOT_TOGGLE",
        0x7C58: "QK_LEADER",
    }

    if code in names:
        return names[code]

    if QK_SWAP_HANDS_TAP <= code <= QK_SWAP_HANDS_TAP_MAX:
        inner = code & 0xFF
        return f"SH_T(0x{inner:02X})"

    return f"0x{code:04X}"


def convert_tap_dance_to_vil(tap_dance_data):
    """
    Convert tap dance entries from GUI dict format to vial-gui tuple format.

    GUI format: [{"on": bool, "on_tap": kc, "on_hold": kc, "on_double_tap": kc,
                  "on_tap_hold": kc, "tapping_term": int}, ...]
    vial-gui format: [(on_tap, on_hold, on_double_tap, on_tap_hold, term), ...]

    Note: The 'on' (enabled) flag is encoded in the high bit of term in vial-gui.

    Returns:
        tuple: (converted_data, set of dropped keycodes)
    """
    result = []
    dropped = set()
    for entry in tap_dance_data:
        if isinstance(entry, dict):
            on = entry.get("on", False)
            term = entry.get("tapping_term", 0) & 0x7FFF
            if on:
                term |= 0x8000

            # Translate keycodes
            on_tap, changed = translate_keycode_string_to_vil(entry.get("on_tap", "KC_NO"))
            if changed:
                dropped.add(entry.get("on_tap"))
            on_hold, changed = translate_keycode_string_to_vil(entry.get("on_hold", "KC_NO"))
            if changed:
                dropped.add(entry.get("on_hold"))
            on_double_tap, changed = translate_keycode_string_to_vil(entry.get("on_double_tap", "KC_NO"))
            if changed:
                dropped.add(entry.get("on_double_tap"))
            on_tap_hold, changed = translate_keycode_string_to_vil(entry.get("on_tap_hold", "KC_NO"))
            if changed:
                dropped.add(entry.get("on_tap_hold"))

            result.append((on_tap, on_hold, on_double_tap, on_tap_hold, term))
        else:
            # Already in tuple format - translate keycodes in tuple
            translated = []
            for i, kc in enumerate(entry[:4]):
                kc_new, changed = translate_keycode_string_to_vil(kc)
                if changed:
                    dropped.add(kc)
                translated.append(kc_new)
            translated.append(entry[4] if len(entry) > 4 else 0)
            result.append(tuple(translated))
    return result, dropped


def convert_combo_to_vil(combo_data):
    """
    Convert combo entries from GUI dict format to vial-gui tuple format.

    GUI format: [{"on": bool, "keys": [k1,k2,k3,k4], "output": kc, "combo_term": int}, ...]
    vial-gui format: [(k1, k2, k3, k4, output), ...]

    WARNING: combo_term is LOST in this conversion as vial-gui doesn't support it.

    Returns:
        tuple: (converted_data, has_custom_terms, dropped_keycodes)
    """
    result = []
    has_custom_terms = False
    dropped = set()

    for entry in combo_data:
        if isinstance(entry, dict):
            keys = entry.get("keys", ["KC_NO", "KC_NO", "KC_NO", "KC_NO"])
            output = entry.get("output", "KC_NO")
            # Check if there's a custom combo term that will be lost
            term = entry.get("combo_term", 0)
            if term != 0:
                has_custom_terms = True

            # Translate keycodes
            translated_keys = []
            for i in range(4):
                kc = keys[i] if i < len(keys) else "KC_NO"
                kc_new, changed = translate_keycode_string_to_vil(kc)
                if changed:
                    dropped.add(kc)
                translated_keys.append(kc_new)

            output_new, changed = translate_keycode_string_to_vil(output)
            if changed:
                dropped.add(output)

            result.append((*translated_keys, output_new))
        else:
            # Already in tuple format - strip 6th element if present, translate keycodes
            if len(entry) >= 6:
                has_custom_terms = True
            translated = []
            for kc in entry[:5]:
                kc_new, changed = translate_keycode_string_to_vil(kc)
                if changed:
                    dropped.add(kc)
                translated.append(kc_new)
            result.append(tuple(translated))

    return result, has_custom_terms, dropped


def convert_key_override_to_vil(key_override_data):
    """
    Convert key override entries from GUI dict format to vial-gui dict format.

    GUI format: {"on": bool, "trigger": kc, ..., "options": int (without enable bit)}
    vial-gui format: {"trigger": kc, ..., "options": int (WITH enable bit at bit 7)}

    The GUI stores enabled state separately in "on" field and strips it from options.
    vial-gui encodes enabled in bit 7 of options and has no "on" field.

    Returns:
        tuple: (converted_data, dropped_keycodes)
    """
    result = []
    dropped = set()
    for entry in key_override_data:
        if isinstance(entry, dict):
            # Get the enabled state from "on" field (default True for compatibility)
            enabled = entry.get("on", True)
            # Get options without enable bit
            options = entry.get("options", 0) & 0x7F  # Ensure bit 7 is clear
            # Re-combine enable bit into options
            if enabled:
                options |= 0x80  # Set bit 7

            # Translate keycodes
            trigger = entry.get("trigger", "KC_NO")
            trigger_new, changed = translate_keycode_string_to_vil(trigger)
            if changed:
                dropped.add(trigger)

            replacement = entry.get("replacement", "KC_NO")
            replacement_new, changed = translate_keycode_string_to_vil(replacement)
            if changed:
                dropped.add(replacement)

            result.append({
                "trigger": trigger_new,
                "replacement": replacement_new,
                "layers": entry.get("layers", 0xFFFF),
                "trigger_mods": entry.get("trigger_mods", 0),
                "negative_mod_mask": entry.get("negative_mod_mask", 0),
                "suppressed_mods": entry.get("suppressed_mods", 0),
                "options": options
            })
        else:
            # Already in expected format
            result.append(entry)
    return result, dropped


def convert_alt_repeat_key_to_vil(alt_repeat_key_data):
    """
    Convert alt repeat key entries from GUI dict format to vial-gui dict format.

    GUI format: {"on": bool, "keycode": kc, ..., "options": int (without enable bit)}
    vial-gui format: {"keycode": kc, ..., "options": int (WITH enable bit at bit 3)}

    The GUI stores enabled state separately in "on" field and strips it from options.
    vial-gui encodes enabled in bit 3 of options and has no "on" field.

    Returns:
        tuple: (converted_data, dropped_keycodes)
    """
    result = []
    dropped = set()
    for entry in alt_repeat_key_data:
        if isinstance(entry, dict):
            # Get the enabled state from "on" field (default True for compatibility)
            enabled = entry.get("on", True)
            # Get options without enable bit (bits 0-2 only)
            options = entry.get("options", 0) & 0x07  # Ensure bit 3 is clear
            # Re-combine enable bit into options
            if enabled:
                options |= 0x08  # Set bit 3

            # Translate keycodes
            keycode = entry.get("keycode", "KC_NO")
            keycode_new, changed = translate_keycode_string_to_vil(keycode)
            if changed:
                dropped.add(keycode)

            alt_keycode = entry.get("alt_keycode", "KC_NO")
            alt_keycode_new, changed = translate_keycode_string_to_vil(alt_keycode)
            if changed:
                dropped.add(alt_keycode)

            result.append({
                "keycode": keycode_new,
                "alt_keycode": alt_keycode_new,
                "allowed_mods": entry.get("allowed_mods", 0),
                "options": options
            })
        else:
            # Already in expected format
            result.append(entry)
    return result, dropped


def filter_settings_for_vil(settings, supported_qsids=None):
    """
    Filter QMK settings to only include those supported by vial-gui.

    Args:
        settings: dict of {qsid: value}
        supported_qsids: set of qsids supported by vial-gui (if None, return all)

    Returns:
        dict of filtered settings
    """
    if supported_qsids is None:
        # If no filter provided, return all settings
        # vial-gui will filter when loading based on its own supported list
        return settings
    return {k: v for k, v in settings.items() if k in supported_qsids}
