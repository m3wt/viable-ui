# SPDX-License-Identifier: GPL-2.0-or-later
import struct
import json
import lzma
import logging
from collections import OrderedDict

from keycodes.keycodes import RESET_KEYCODE, Keycode, recreate_keyboard_keycodes, translate_keycode_v5_to_v6
from kle_serial import Serial as KleSerial
from protocol.alt_repeat_key import ProtocolAltRepeatKey
from protocol.combo import ProtocolCombo
from protocol.constants import CMD_VIA_GET_PROTOCOL_VERSION, CMD_VIA_GET_KEYBOARD_VALUE, CMD_VIA_SET_KEYBOARD_VALUE, \
    CMD_VIA_SET_KEYCODE, CMD_VIA_LIGHTING_SET_VALUE, CMD_VIA_LIGHTING_GET_VALUE, CMD_VIA_LIGHTING_SAVE, \
    CMD_VIA_GET_LAYER_COUNT, CMD_VIA_KEYMAP_GET_BUFFER, CMD_VIA_ENCODER_GET, CMD_VIA_ENCODER_SET, \
    CMD_VIA_CUSTOM_SET_VALUE, CMD_VIA_CUSTOM_GET_VALUE, CMD_VIA_CUSTOM_SAVE, \
    VIA_LAYOUT_OPTIONS, VIA_SWITCH_MATRIX_STATE, QMK_BACKLIGHT_BRIGHTNESS, QMK_BACKLIGHT_EFFECT, \
    QMK_RGBLIGHT_BRIGHTNESS, QMK_RGBLIGHT_EFFECT, QMK_RGBLIGHT_EFFECT_SPEED, QMK_RGBLIGHT_COLOR, \
    VIALRGB_GET_INFO, VIALRGB_GET_MODE, VIALRGB_GET_SUPPORTED, VIALRGB_SET_MODE, VIA_BUFFER_CHUNK_SIZE, \
    VIABLE_PREFIX, VIABLE_GET_PROTOCOL_INFO, VIABLE_DEFINITION_SIZE, VIABLE_DEFINITION_CHUNK, \
    VIABLE_DEFINITION_CHUNK_SIZE, \
    VIABLE_QMK_SETTINGS_QUERY, VIABLE_QMK_SETTINGS_GET, VIABLE_QMK_SETTINGS_SET, VIABLE_QMK_SETTINGS_RESET
from protocol.dynamic import ProtocolDynamic
from protocol.key_override import ProtocolKeyOverride
from protocol.macro import ProtocolMacro
from protocol.svalboard import ProtocolSvalboard
from protocol.tap_dance import ProtocolTapDance
from protocol.viable import ProtocolViable
from protocol.client_wrapper import ClientWrapper
from unlocker import Unlocker
from util import MSG_LEN, hid_send

SUPPORTED_VIA_PROTOCOL = [-1, 12]  # -1 is initial/unknown, 12 is current QMK VIA
SUPPORTED_VIABLE_PROTOCOL = [1]


class ProtocolError(Exception):
    pass


class Keyboard(ProtocolMacro, ProtocolDynamic, ProtocolTapDance, ProtocolCombo, ProtocolKeyOverride, ProtocolAltRepeatKey, ProtocolViable, ProtocolSvalboard):
    """ Low-level communication with a vial-enabled keyboard """

    def __init__(self, dev, usb_send=hid_send):
        self.dev = dev
        self.usb_send = usb_send
        self.wrapper = ClientWrapper(dev, usb_send)
        self.definition = None

        # n.b. using OrderedDict here to make order of layout requests consistent for tests
        self.rowcol = OrderedDict()
        self.encoderpos = OrderedDict()
        self.encoder_count = 0
        self.layout = dict()
        self.encoder_layout = dict()
        self.rows = self.cols = self.layers = 0
        self.layout_labels = None
        self.layout_options = -1
        self.keys = []
        self.encoders = []
        self.vibl = False
        self.custom_keycodes = None
        self.midi = None

        self.lighting_qmk_rgblight = self.lighting_qmk_backlight = self.lighting_vialrgb = False

        # underglow
        self.underglow_brightness = self.underglow_effect = self.underglow_effect_speed = -1
        self.underglow_color = (0, 0)
        # backlight
        self.backlight_brightness = self.backlight_effect = -1
        # vialrgb
        self.rgb_mode = self.rgb_speed = self.rgb_version = self.rgb_maximum_brightness = -1
        self.rgb_hsv = (0, 0, 0)
        self.rgb_supported_effects = set()

        self.via_protocol = self.keyboard_id = -1
        self.viable_protocol = None  # Viable 0xDF protocol version, or None if not supported

    def via_send(self, msg, retries=20):
        """Send a VIA command through the wrapper for client ID isolation."""
        return self.wrapper.send_via(msg, retries=retries)

    def reload(self, sideload_json=None):
        """ Load information about the keyboard: number of layers, physical key layout """

        self.rowcol = OrderedDict()
        self.encoderpos = OrderedDict()
        self.layout = dict()
        self.encoder_layout = dict()

        self.reload_layout(sideload_json)
        self.reload_layers()

        self.reload_macros_early()
        self.reload_persistent_rgb()
        self.reload_rgb()

        self.reload_dynamic()

        # Load QMK settings after reload_dynamic so viable_protocol is set
        self.reload_settings()

        # Load macro data early so preview text is available for keycode labels
        self.reload_macros_late()

        # based on the number of macros, tapdance, etc, this will generate global keycode arrays
        recreate_keyboard_keycodes(self)

        # at this stage we have correct keycode info and can reload everything that depends on keycodes
        self.reload_keymap()
        self.reload_tap_dance()
        self.reload_combo()
        self.reload_key_override()
        self.reload_alt_repeat_key()
        self.reload_svalboard()

    def reload_layers(self):
        """ Get how many layers the keyboard has """

        self.layers = self.via_send(struct.pack("B", CMD_VIA_GET_LAYER_COUNT), retries=20)[1]

    def reload_via_protocol(self):
        logging.debug(" Sending CMD_VIA_GET_PROTOCOL_VERSION (0x%02X)", CMD_VIA_GET_PROTOCOL_VERSION)
        data = self.via_send(struct.pack("B", CMD_VIA_GET_PROTOCOL_VERSION), retries=20)
        logging.debug(" Received: %s", data.hex())
        self.via_protocol = struct.unpack(">H", data[1:3])[0]
        logging.debug(" VIA protocol version: %d", self.via_protocol)

    def check_protocol_version(self):
        if self.via_protocol not in SUPPORTED_VIA_PROTOCOL:
            raise ProtocolError()
        if self.viable_protocol and self.viable_protocol not in SUPPORTED_VIABLE_PROTOCOL:
            raise ProtocolError()

    def reload_layout(self, sideload_json=None):
        """ Requests layout data from the current device """

        logging.debug(" reload_layout() starting")
        self.reload_via_protocol()

        self.sideload = False
        if sideload_json is not None:
            self.sideload = True
            payload = sideload_json
        else:
            # Probe for Viable 0xDF protocol (v2) - uses wrapper for client ID isolation
            logging.debug(" Sending VIABLE_GET_PROTOCOL_INFO via wrapper")
            data = self.wrapper.send_viable(struct.pack("B", VIABLE_GET_PROTOCOL_INFO), retries=5)
            logging.debug(" Received: %s", data.hex())
            # v2 Response: [0xDF] [0x00] [ver0-3] [td_count] [combo_count] [ko_count] [ark_count] [flags] [uid0-7]
            if data[0] != VIABLE_PREFIX or data[1] != VIABLE_GET_PROTOCOL_INFO:
                # VIA-only board - no Viable protocol support
                logging.info("Keyboard does not support Viable protocol (VIA-only board)")
                self.viable_protocol = None
                raise RuntimeError("VIA-only keyboard detected. Please sideload a JSON definition file.")
            version = struct.unpack("<I", bytes(data[2:6]))[0]
            logging.debug(" Viable protocol version: %d", version)
            if version == 0:
                raise RuntimeError("Invalid Viable protocol version")
            self.viable_protocol = version
            # Read keyboard UID (8 bytes at offset 11, for .vil compatibility)
            self.keyboard_id = struct.unpack("<Q", bytes(data[11:19]))[0]
            logging.debug(" Keyboard UID: 0x%016X", self.keyboard_id)

            # get the size via Viable protocol
            logging.debug(" Sending VIABLE_DEFINITION_SIZE via wrapper")
            data = self.wrapper.send_viable(struct.pack("B", VIABLE_DEFINITION_SIZE), retries=20)
            logging.debug(" Received: %s", data.hex())
            # Response: [0xDF] [0x0D] [size0-3]
            sz = struct.unpack("<I", bytes(data[2:6]))[0]
            logging.debug(" Definition size: %d bytes", sz)

            # get the payload via Viable protocol
            payload = b""
            offset = 0
            logging.debug(" Fetching definition chunks...")
            while offset < sz:
                # Request: [0xDF] [0x0E] [offset:2] [size:1]
                data = self.wrapper.send_viable(
                    struct.pack("<BHB", VIABLE_DEFINITION_CHUNK, offset, VIABLE_DEFINITION_CHUNK_SIZE),
                    retries=20)
                # Response: [0xDF] [0x0E] [offset:2] [actual_size:1] [data...]
                actual_size = data[4]
                chunk = data[5:5 + actual_size]
                payload += chunk
                offset += actual_size
                if offset % 220 == 0:  # Log every 10 chunks
                    logging.debug(" Fetched %d/%d bytes", offset, sz)

            logging.debug(" All chunks fetched, decompressing %d bytes", len(payload))
            payload = json.loads(lzma.decompress(payload))
            logging.debug(" Decompression successful")

        self.check_protocol_version()

        self.definition = payload

        if "vial" in payload:
            vial = payload["vial"]
            self.vibl = vial.get("vibl", False)
            self.midi = vial.get("midi", None)

        self.layout_labels = payload["layouts"].get("labels")

        self.rows = payload["matrix"]["rows"]
        self.cols = payload["matrix"]["cols"]

        self.custom_keycodes = payload.get("customKeycodes", None)

        serial = KleSerial()
        kb = serial.deserialize(payload["layouts"]["keymap"])

        self.keys = []
        self.encoders = []

        for key in kb.keys:
            key.row = key.col = None
            key.encoder_idx = key.encoder_dir = None
            if key.labels[4] == "e":
                idx, direction = key.labels[0].split(",")
                idx, direction = int(idx), int(direction)
                key.encoder_idx = idx
                key.encoder_dir = direction
                self.encoderpos[idx] = True
                self.encoder_count = max(self.encoder_count, idx + 1)
                self.encoders.append(key)
            elif key.decal or (key.labels[0] and "," in key.labels[0]):
                row, col = 0, 0
                if key.labels[0] and "," in key.labels[0]:
                    row, col = key.labels[0].split(",")
                    row, col = int(row), int(col)
                key.row = row
                key.col = col
                self.rowcol[(row, col)] = True
                self.keys.append(key)

            # bottom right corner determines layout index and option in this layout
            key.layout_index = -1
            key.layout_option = -1
            if key.labels[8]:
                idx, opt = key.labels[8].split(",")
                key.layout_index, key.layout_option = int(idx), int(opt)

    def reload_keymap(self):
        """ Load current key mapping from the keyboard """

        keymap = b""
        # calculate what the size of keymap will be and retrieve the entire binary buffer
        size = self.layers * self.rows * self.cols * 2
        for x in range(0, size, VIA_BUFFER_CHUNK_SIZE):
            offset = x
            sz = min(size - offset, VIA_BUFFER_CHUNK_SIZE)
            data = self.via_send(struct.pack(">BHB", CMD_VIA_KEYMAP_GET_BUFFER, offset, sz), retries=20)
            keymap += data[4:4+sz]

        for layer in range(self.layers):
            for row, col in self.rowcol.keys():
                if row >= self.rows or col >= self.cols:
                    raise RuntimeError("malformed vial.json, key references {},{} but matrix declares rows={} cols={}"
                                       .format(row, col, self.rows, self.cols))
                # determine where this (layer, row, col) will be located in keymap array
                offset = layer * self.rows * self.cols * 2 + row * self.cols * 2 + col * 2
                keycode = Keycode.serialize(struct.unpack(">H", keymap[offset:offset+2])[0])
                self.layout[(layer, row, col)] = keycode

        for layer in range(self.layers):
            for idx in self.encoderpos:
                # VIA3: one call per direction, keycode at bytes 3-4
                data = self.via_send(struct.pack("BBBB", CMD_VIA_ENCODER_GET, layer, idx, 0), retries=20)
                self.encoder_layout[(layer, idx, 0)] = Keycode.serialize(struct.unpack(">H", data[3:5])[0])
                data = self.via_send(struct.pack("BBBB", CMD_VIA_ENCODER_GET, layer, idx, 1), retries=20)
                self.encoder_layout[(layer, idx, 1)] = Keycode.serialize(struct.unpack(">H", data[3:5])[0])

        if self.layout_labels:
            data = self.via_send(struct.pack("BB", CMD_VIA_GET_KEYBOARD_VALUE, VIA_LAYOUT_OPTIONS),
                                 retries=20)
            self.layout_options = struct.unpack(">I", data[2:6])[0]

    def reload_persistent_rgb(self):
        """
            Reload RGB properties which are slow, and do not change while keyboard is plugged in
            e.g. VialRGB supported effects list
        """

        if "lighting" in self.definition:
            self.lighting_qmk_rgblight = self.definition["lighting"] in ["qmk_rgblight", "qmk_backlight_rgblight"]
            self.lighting_qmk_backlight = self.definition["lighting"] in ["qmk_backlight", "qmk_backlight_rgblight"]
            self.lighting_vialrgb = self.definition["lighting"] == "vialrgb"

        if self.lighting_vialrgb:
            data = self.via_send(struct.pack("BB", CMD_VIA_LIGHTING_GET_VALUE, VIALRGB_GET_INFO),
                                 retries=20)[2:]
            self.rgb_version = data[0] | (data[1] << 8)
            if self.rgb_version != 1:
                raise RuntimeError("Unsupported VialRGB protocol ({}), update your Vial version to latest"
                                   .format(self.rgb_version))
            self.rgb_maximum_brightness = data[2]

            self.rgb_supported_effects = {0}
            max_effect = 0
            while max_effect < 0xFFFF:
                data = self.via_send(struct.pack("<BBH", CMD_VIA_LIGHTING_GET_VALUE, VIALRGB_GET_SUPPORTED,
                                                           max_effect))[2:]
                for x in range(0, len(data), 2):
                    value = int.from_bytes(data[x:x+2], byteorder="little")
                    if value != 0xFFFF:
                        self.rgb_supported_effects.add(value)
                    max_effect = max(max_effect, value)

    def reload_rgb(self):
        if self.lighting_qmk_rgblight:
            self.underglow_brightness = self.via_send(
                struct.pack(">BB", CMD_VIA_LIGHTING_GET_VALUE, QMK_RGBLIGHT_BRIGHTNESS), retries=20)[2]
            self.underglow_effect = self.via_send(
                struct.pack(">BB", CMD_VIA_LIGHTING_GET_VALUE, QMK_RGBLIGHT_EFFECT), retries=20)[2]
            self.underglow_effect_speed = self.via_send(
                struct.pack(">BB", CMD_VIA_LIGHTING_GET_VALUE, QMK_RGBLIGHT_EFFECT_SPEED), retries=20)[2]
            color = self.via_send(
                struct.pack(">BB", CMD_VIA_LIGHTING_GET_VALUE, QMK_RGBLIGHT_COLOR), retries=20)[2:4]
            # hue, sat
            self.underglow_color = (color[0], color[1])

        if self.lighting_qmk_backlight:
            self.backlight_brightness = self.via_send(
                struct.pack(">BB", CMD_VIA_LIGHTING_GET_VALUE, QMK_BACKLIGHT_BRIGHTNESS), retries=20)[2]
            self.backlight_effect = self.via_send(
                struct.pack(">BB", CMD_VIA_LIGHTING_GET_VALUE, QMK_BACKLIGHT_EFFECT), retries=20)[2]

        if self.lighting_vialrgb:
            data = self.via_send(struct.pack("BB", CMD_VIA_LIGHTING_GET_VALUE, VIALRGB_GET_MODE),
                                 retries=20)[2:]
            self.rgb_mode = int.from_bytes(data[0:2], byteorder="little")
            self.rgb_speed = data[2]
            self.rgb_hsv = (data[3], data[4], data[5])

    def reload_settings(self):
        self.settings = dict()
        self.supported_settings = set()

        # Query supported QSIDs via 0xDF protocol
        cur = 0
        while cur != 0xFFFF:
            data = self.wrapper.send_viable(struct.pack("<BH", VIABLE_QMK_SETTINGS_QUERY, cur),
                                            retries=20)
            # Response: [0xDF] [0x10] [qsid1_lo] [qsid1_hi] ... [0xFF] [0xFF]
            # Firmware fills unused entries with 0xFFFF, so stop when we hit it
            for x in range(2, len(data), 2):
                qsid = int.from_bytes(data[x:x+2], byteorder="little")
                if qsid == 0xFFFF:
                    cur = 0xFFFF
                    break
                cur = max(cur, qsid)
                self.supported_settings.add(qsid)

        # Get values for supported settings
        for qsid in self.supported_settings:
            from editor.qmk_settings import QmkSettings

            if not QmkSettings.is_qsid_supported(qsid):
                continue

            # Request: [0xDF] [0x11] [qsid_lo] [qsid_hi]
            # Response: [0xDF] [0x11] [status] [value bytes...]
            data = self.wrapper.send_viable(struct.pack("<BH", VIABLE_QMK_SETTINGS_GET, qsid),
                                            retries=20)
            if data[2] == 0:  # status = success
                self.settings[qsid] = QmkSettings.qsid_deserialize(qsid, data[3:])

    def set_key(self, layer, row, col, code):
        key = (layer, row, col)
        if self.layout[key] != code:
            if code == RESET_KEYCODE:
                Unlocker.unlock(self)

            self.via_send(struct.pack(">BBBBH", CMD_VIA_SET_KEYCODE, layer, row, col,
                                                Keycode.deserialize(code)), retries=20)
            self.layout[key] = code

    def _commit_key(self, layer, row, col, code):
        """Send a key change to the device (used by ChangeManager)."""
        if code == RESET_KEYCODE:
            Unlocker.unlock(self)
        self.via_send(struct.pack(">BBBBH", CMD_VIA_SET_KEYCODE, layer, row, col,
                                            Keycode.deserialize(code)), retries=20)
        self.layout[(layer, row, col)] = code
        return True

    def set_encoder(self, layer, index, direction, code):
        key = (layer, index, direction)
        if self.encoder_layout[key] != code:
            # VIA3: [0x15] [layer] [encoder_id] [direction] [keycode_hi] [keycode_lo]
            self.via_send(struct.pack(">BBBBH", CMD_VIA_ENCODER_SET,
                                                layer, index, direction, Keycode.deserialize(code)), retries=20)
            self.encoder_layout[key] = code

    def _commit_encoder(self, layer, index, direction, code):
        """Send an encoder change to the device (used by ChangeManager)."""
        # VIA3: [0x15] [layer] [encoder_id] [direction] [keycode_hi] [keycode_lo]
        self.via_send(struct.pack(">BBBBH", CMD_VIA_ENCODER_SET,
                                            layer, index, direction, Keycode.deserialize(code)), retries=20)
        self.encoder_layout[(layer, index, direction)] = code
        return True

    def set_layout_options(self, options):
        if self.layout_options != -1 and self.layout_options != options:
            self.layout_options = options
            self.via_send(struct.pack(">BBI", CMD_VIA_SET_KEYBOARD_VALUE, VIA_LAYOUT_OPTIONS, options),
                          retries=20)

    def set_qmk_rgblight_brightness(self, value):
        self.underglow_brightness = value
        self.via_send(struct.pack(">BBB", CMD_VIA_LIGHTING_SET_VALUE, QMK_RGBLIGHT_BRIGHTNESS, value),
                      retries=20)

    def set_qmk_rgblight_effect(self, index):
        self.underglow_effect = index
        self.via_send(struct.pack(">BBB", CMD_VIA_LIGHTING_SET_VALUE, QMK_RGBLIGHT_EFFECT, index),
                      retries=20)

    def set_qmk_rgblight_effect_speed(self, value):
        self.underglow_effect_speed = value
        self.via_send(struct.pack(">BBB", CMD_VIA_LIGHTING_SET_VALUE, QMK_RGBLIGHT_EFFECT_SPEED, value),
                      retries=20)

    def set_qmk_rgblight_color(self, h, s, v):
        self.set_qmk_rgblight_brightness(v)
        self.via_send(struct.pack(">BBBB", CMD_VIA_LIGHTING_SET_VALUE, QMK_RGBLIGHT_COLOR, h, s))

    def set_qmk_backlight_brightness(self, value):
        self.backlight_brightness = value
        self.via_send(struct.pack(">BBB", CMD_VIA_LIGHTING_SET_VALUE, QMK_BACKLIGHT_BRIGHTNESS, value))

    def set_qmk_backlight_effect(self, value):
        self.backlight_effect = value
        self.via_send(struct.pack(">BBB", CMD_VIA_LIGHTING_SET_VALUE, QMK_BACKLIGHT_EFFECT, value))

    def save_rgb(self):
        self.via_send(struct.pack(">B", CMD_VIA_LIGHTING_SAVE), retries=20)

    def save_layout(self):
        """ Serializes current layout to a binary """

        data = {"version": 1, "uid": self.keyboard_id}
        # Add keyboard name for better matching (UID is 0 for all Viable keyboards)
        if self.definition:
            data["name"] = self.definition.get("keyboard_name", "")

        layout = []
        for l in range(self.layers):
            layer = []
            layout.append(layer)
            for r in range(self.rows):
                row = []
                layer.append(row)
                for c in range(self.cols):
                    val = self.layout.get((l, r, c), -1)
                    row.append(val)

        encoder_layout = []
        for l in range(self.layers):
            layer = []
            for e in range(self.encoder_count):
                cw = (l, e, 0)
                ccw = (l, e, 1)
                layer.append([self.encoder_layout.get(cw, -1),
                              self.encoder_layout.get(ccw, -1)])
            encoder_layout.append(layer)

        data["layout"] = layout
        data["encoder_layout"] = encoder_layout
        data["layout_options"] = self.layout_options
        data["macro"] = self.save_macro()
        data["viable_protocol"] = self.viable_protocol
        data["via_protocol"] = self.via_protocol
        data["tap_dance"] = self.save_tap_dance()
        data["combo"] = self.save_combo()
        data["key_override"] = self.save_key_override()
        data["alt_repeat_key"] = self.save_alt_repeat_key()
        data["oneshot"] = self.save_oneshot()
        data["settings"] = self.settings

        return json.dumps(data).encode("utf-8")

    def restore_layout(self, data):
        """ Restores saved layout """

        data = json.loads(data.decode("utf-8"))

        # Check if we need to translate keycodes from v5 to v6 format
        # VIA protocol < 12 used v5 keycodes, >= 12 uses v6
        # Files without via_protocol are old and need translation
        saved_via_protocol = data.get("via_protocol")
        needs_translation = (saved_via_protocol is None or saved_via_protocol < 12) and self.via_protocol >= 12

        # Check if we need to fix USER keycodes saved at wrong location
        # Older .vil files had USER at 0x7E00-0x7E3F, should be 0x7E40-0x7E7F
        needs_user_fix = data.get("vil_version", 0) < 2

        def translate_code(code):
            """Translate keycode if needed, handling both int and string formats."""
            # String keycodes (like "M0", "KC_A") are protocol-agnostic and get
            # deserialized with the current protocol - no translation needed.
            # Only integer keycodes stored in v5 format need translation.
            was_string = isinstance(code, str)
            if was_string:
                code = Keycode.deserialize(code)
            if needs_translation and not was_string:
                code = translate_keycode_v5_to_v6(code)
            # Fix USER keycodes that were incorrectly saved at QK_KB range
            if needs_user_fix and 0x7E00 <= code <= 0x7E3F:
                code = code + 0x40
            return Keycode.serialize(code)

        # restore keymap
        for l, layer in enumerate(data["layout"]):
            for r, row in enumerate(layer):
                for c, code in enumerate(row):
                    if (l, r, c) in self.layout:
                        self.set_key(l, r, c, translate_code(code))

        # restore encoders
        for l, layer in enumerate(data["encoder_layout"]):
            for e, encoder in enumerate(layer):
                self.set_encoder(l, e, 0, translate_code(encoder[0]))
                self.set_encoder(l, e, 1, translate_code(encoder[1]))

        self.set_layout_options(data["layout_options"])
        self.restore_macros(data.get("macro"))

        self.restore_tap_dance(data.get("tap_dance", []))
        self.restore_combo(data.get("combo", []))
        self.restore_key_override(data.get("key_override", []))
        self.restore_alt_repeat_key(data.get("alt_repeat_key", []))
        self.restore_oneshot(data.get("oneshot"))

        for qsid, value in data.get("settings", dict()).items():
            from editor.qmk_settings import QmkSettings

            qsid = int(qsid)
            if QmkSettings.is_qsid_supported(qsid):
                self.qmk_settings_set(qsid, value)

    def reset(self):
        self.via_send(struct.pack("B", 0xB))
        self.dev.close()

    def get_uid(self):
        """ Retrieve UID from the keyboard - stub, Vial protocol removed """
        return bytes(8)

    def get_unlock_status(self, retries=20):
        # Vial unlock removed - always unlocked
        return 1

    def get_unlock_in_progress(self):
        # Vial unlock removed
        return 0

    def get_unlock_keys(self):
        """ Return keys users have to hold to unlock the keyboard as a list of rowcols """
        # Vial unlock removed
        return []

    def unlock_start(self):
        # Vial unlock removed
        pass

    def unlock_poll(self):
        # Vial unlock removed
        return bytes([1, 0, 0])

    def lock(self):
        # Vial unlock removed
        pass

    def matrix_poll(self):
        if self.via_protocol < 0:
            return

        data = self.via_send(struct.pack("BB", CMD_VIA_GET_KEYBOARD_VALUE, VIA_SWITCH_MATRIX_STATE),
                             retries=3)
        return data

    def qmk_settings_set(self, qsid, value):
        from editor.qmk_settings import QmkSettings

        # Serialize value to bytes
        value_bytes = QmkSettings.qsid_serialize(qsid, value)
        # Request: [0xDF] [0x12] [qsid_lo] [qsid_hi] [value bytes...]
        msg = struct.pack("<BH", VIABLE_QMK_SETTINGS_SET, qsid) + value_bytes
        data = self.wrapper.send_viable(msg, retries=20)
        # Response: [0xDF] [0x12] [status]
        status = data[2]
        if status == 0:
            self.settings[qsid] = value
        return status

    def _commit_qmk_setting(self, qsid, value):
        """Send a QMK setting change to the device (used by ChangeManager)."""
        from editor.qmk_settings import QmkSettings

        # Serialize value to bytes
        value_bytes = QmkSettings.qsid_serialize(qsid, value)
        # Request: [0xDF] [0x12] [qsid_lo] [qsid_hi] [value bytes...]
        msg = struct.pack("<BH", VIABLE_QMK_SETTINGS_SET, qsid) + value_bytes
        data = self.wrapper.send_viable(msg, retries=20)
        # Response: [0xDF] [0x12] [status]
        status = data[2]
        if status == 0:
            self.settings[qsid] = value
            return True
        return False

    def qmk_settings_reset(self):
        # Request: [0xDF] [0x13]
        self.wrapper.send_viable(struct.pack("B", VIABLE_QMK_SETTINGS_RESET), retries=20)
        # Reload settings from firmware
        self.reload_settings()

    def _vialrgb_set_mode(self):
        self.via_send(struct.pack("BBHBBBB", CMD_VIA_LIGHTING_SET_VALUE, VIALRGB_SET_MODE,
                                            self.rgb_mode, self.rgb_speed,
                                            self.rgb_hsv[0], self.rgb_hsv[1], self.rgb_hsv[2]))

    def set_vialrgb_brightness(self, value):
        self.rgb_hsv = (self.rgb_hsv[0], self.rgb_hsv[1], value)
        self._vialrgb_set_mode()

    def set_vialrgb_speed(self, value):
        self.rgb_speed = value
        self._vialrgb_set_mode()

    def set_vialrgb_mode(self, value):
        self.rgb_mode = value
        self._vialrgb_set_mode()

    def set_vialrgb_color(self, h, s, v):
        self.rgb_hsv = (h, s, v)
        self._vialrgb_set_mode()

    @property
    def custom_ui(self):
        """Return VIA3 custom_ui definition (menus) from keyboard definition."""
        if not self.definition:
            return None
        menus = self.definition.get("menus")
        if not menus:
            return None
        return {"menus": menus}

    def custom_value_get(self, channel, value_id):
        """
        Get a custom value from the keyboard using VIA custom value protocol.

        Packet: [0x08] [channel] [value_id]
        Response: [0x08] [channel] [value_id] [data...]

        VIA channels:
        - 0: Keyboard-specific custom values
        - 1: QMK backlight
        - 2: QMK rgblight
        - 3: QMK rgb_matrix
        - 4: QMK audio
        - 5: QMK led_matrix
        """
        msg = struct.pack("BBB", CMD_VIA_CUSTOM_GET_VALUE, channel, value_id)
        data = self.via_send(msg, retries=20)
        # Response: [cmd] [channel] [value_id] [data...]
        return data[3:] if len(data) > 3 else bytes()

    def custom_value_set(self, channel, value_id, data):
        """
        Set a custom value on the keyboard using VIA custom value protocol.

        Packet: [0x07] [channel] [value_id] [data...]
        """
        msg = struct.pack("BBB", CMD_VIA_CUSTOM_SET_VALUE, channel, value_id) + bytes(data)
        self.via_send(msg, retries=20)

    def custom_value_save(self, channel):
        """
        Save custom values to EEPROM using VIA custom value protocol.

        Packet: [0x09] [channel]
        """
        msg = struct.pack("BB", CMD_VIA_CUSTOM_SAVE, channel)
        self.via_send(msg, retries=20)

    def _commit_custom_value(self, channel, value_id, data):
        """
        Commit a custom value change (set value and save to EEPROM).

        Used by ChangeManager for applying custom value changes.
        """
        try:
            self.custom_value_set(channel, value_id, data)
            self.custom_value_save(channel)
            # Update local cache
            if not hasattr(self, 'custom_values'):
                self.custom_values = {}
            self.custom_values[(channel, value_id)] = data
            return True
        except Exception:
            return False
