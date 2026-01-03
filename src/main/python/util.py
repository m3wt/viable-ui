# SPDX-License-Identifier: GPL-2.0-or-later
import logging
import os
import pathlib
import sys
import time
from logging.handlers import RotatingFileHandler

from qtpy.QtCore import QCoreApplication, QStandardPaths
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QApplication, QWidget, QScrollArea, QFrame

from hidproxy import hid
from keycodes.keycodes import Keycode
from keymaps import KEYMAPS

tr = QCoreApplication.translate

# Serial number magic string for device detection
VIABLE_SERIAL_NUMBER_MAGIC = "viable:"

# VIA protocol version 12 = VIA3 (supports custom menus)
VIA3_MIN_PROTOCOL = 12

MSG_LEN = 32

# these should match what we have in vial-qmk/keyboards/vial_example
# so that people don't accidentally reuse a sample keyboard UID
EXAMPLE_KEYBOARDS = [
    0xD4A36200603E3007,  # vial_stm32f103_vibl
    0x32F62BC2EEF2237B,  # vial_atmega32u4
    0x38CEA320F23046A5,  # vial_stm32f072
    0xBED2D31EC59A0BD8,  # vial_stm32f401
]

# anything starting with this prefix should not be allowed
EXAMPLE_KEYBOARD_PREFIX = 0xA6867BDFD3B00F


def hid_send(dev, msg, retries=1):
    if len(msg) > MSG_LEN:
        raise RuntimeError("message must be less than 32 bytes")
    msg += b"\x00" * (MSG_LEN - len(msg))

    data = b""
    first = True
    attempt = 0

    while retries > 0:
        attempt += 1
        retries -= 1
        if not first:
            time.sleep(0.5)
        first = False
        try:
            # add 00 at start for hidapi report id
            logging.debug("hid_send attempt %d: writing %s", attempt, msg[:8].hex())
            written = dev.write(b"\x00" + msg)
            if written != MSG_LEN + 1:
                err = dev.error() if hasattr(dev, 'error') else 'N/A'
                logging.warning("hid_send: write returned %d, expected %d, error=%s", written, MSG_LEN + 1, err)
                continue

            logging.debug("hid_send: waiting for response...")
            data = bytes(dev.read(MSG_LEN, timeout_ms=500))
            if not data:
                logging.warning("hid_send: read returned empty data")
                continue
            logging.debug("hid_send: received %s", data[:8].hex())
        except OSError as e:
            logging.warning("hid_send: OSError: %s", e)
            continue
        break

    if not data:
        logging.error("hid_send: failed to communicate after %d attempts", attempt)
        raise RuntimeError("failed to communicate with the device")
    return data


def is_rawhid(desc, quiet):
    # Accept both Viable (0xFF61/0x62) and VIA (0xFF60/0x61) boards
    is_viable = desc["usage_page"] == 0xFF61 and desc["usage"] == 0x62
    is_via = desc["usage_page"] == 0xFF60 and desc["usage"] == 0x61
    if not (is_viable or is_via):
        if not quiet:
            logging.warning("is_rawhid: {} does not match - usage_page={:04X} usage={:02X}".format(
                desc["path"], desc["usage_page"], desc["usage"]))
        return False

    # there's no reason to check for permission issues on mac or windows
    # and mac won't let us reopen an opened device
    # so skip the rest of the checks for non-linux
    if not sys.platform.startswith("linux"):
        return True

    dev = hid.device()

    try:
        dev.open_path(desc["path"])
    except OSError as e:
        if not quiet:
            logging.warning("is_rawhid: {} does not match - open_path error {}".format(desc["path"], e))
        return False

    dev.close()
    return True


def is_via3_device(desc, quiet=False):
    """Check if a device supports VIA protocol version 3 (protocol >= 12)"""
    import struct

    # Skip probing on web platform - device is handled differently there
    if sys.platform == "emscripten":
        return False

    # Check for VIA (0xFF60/0x61) or Viable (0xFF61/0x62) usage page/id
    is_via = desc["usage_page"] == 0xFF60 and desc["usage"] == 0x61
    is_viable = desc["usage_page"] == 0xFF61 and desc["usage"] == 0x62
    if not (is_via or is_viable):
        return False

    dev = hid.device()
    try:
        dev.open_path(desc["path"])
    except OSError:
        return False

    try:
        # Send CMD_VIA_GET_PROTOCOL_VERSION (0x01)
        msg = struct.pack("B", 0x01) + b"\x00" * (MSG_LEN - 1)
        dev.write(msg)

        data = bytes(dev.read(MSG_LEN, timeout_ms=500))
        if len(data) < 3:
            return False

        # Response: [0x01] [version_hi] [version_lo]
        protocol_version = struct.unpack(">H", bytes(data[1:3]))[0]

        if not quiet:
            logging.info("VIA protocol probe: {} = version {}".format(desc["path"], protocol_version))

        return protocol_version >= VIA3_MIN_PROTOCOL
    except Exception as e:
        if not quiet:
            logging.warning("VIA protocol probe failed for {}: {}".format(desc["path"], e))
        return False
    finally:
        dev.close()


def find_vial_devices(via_stack_json, sideload_vid=None, sideload_pid=None, quiet=False):
    from vial_device import VialKeyboard, VialDummyKeyboard

    filtered = []
    seen_paths = set()  # Avoid duplicates
    for dev in hid.enumerate():
        if dev["path"] in seen_paths:
            continue

        if dev["vendor_id"] == sideload_vid and dev["product_id"] == sideload_pid:
            if not quiet:
                logging.info("Trying VID={:04X}, PID={:04X}, serial={}, path={} - sideload".format(
                    dev["vendor_id"], dev["product_id"], dev["serial_number"], dev["path"]
                ))
            if is_rawhid(dev, quiet):
                filtered.append(VialKeyboard(dev, sideload=True))
                seen_paths.add(dev["path"])
        elif VIABLE_SERIAL_NUMBER_MAGIC in dev["serial_number"]:
            if not quiet:
                logging.info("Matching VID={:04X}, PID={:04X}, serial={}, path={} - viable serial magic".format(
                    dev["vendor_id"], dev["product_id"], dev["serial_number"], dev["path"]
                ))
            if is_rawhid(dev, quiet):
                filtered.append(VialKeyboard(dev))
                seen_paths.add(dev["path"])
        elif is_via3_device(dev, quiet):
            # VIA3 board without Viable firmware - will need sideload JSON
            if not quiet:
                logging.info("Matching VID={:04X}, PID={:04X}, serial={}, path={} - VIA3 board".format(
                    dev["vendor_id"], dev["product_id"], dev["serial_number"], dev["path"]
                ))
            filtered.append(VialKeyboard(dev, sideload=True))
            seen_paths.add(dev["path"])

    if sideload_vid == sideload_pid == 0:
        filtered.append(VialDummyKeyboard())

    return filtered


def chunks(data, sz):
    for i in range(0, len(data), sz):
        yield data[i:i+sz]


def pad_for_vibl(msg):
    """ Pads message to vibl fixed 64-byte length """
    if len(msg) > 64:
        raise RuntimeError("vibl message too long")
    return msg + b"\x00" * (64 - len(msg))


def init_logger():
    logging.basicConfig(level=logging.INFO)
    directory = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
    path = os.path.join(directory, "vial.log")
    handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=5)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"))
    logging.getLogger().addHandler(handler)


def make_scrollable(layout):
    w = QWidget()
    w.setLayout(layout)
    w.setObjectName("w")
    scroll = QScrollArea()
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setStyleSheet("QScrollArea { background-color:transparent; }")
    w.setStyleSheet("#w { background-color:transparent; }")
    scroll.setWidgetResizable(True)
    scroll.setWidget(w)
    return scroll


class KeycodeDisplay:

    keymap_override = KEYMAPS[0][1]
    clients = []

    @classmethod
    def get_label(cls, code):
        """ Get label for a specific keycode """
        if cls.code_is_overriden(code):
            return cls.keymap_override[Keycode.find_outer_keycode(code).qmk_id]
        return Keycode.label(code)

    @classmethod
    def code_is_overriden(cls, code):
        """ Check whether a country-specific keymap overrides a code """
        key = Keycode.find_outer_keycode(code)
        return key is not None and key.qmk_id in cls.keymap_override

    @classmethod
    def display_keycode(cls, widget, code):
        text = cls.get_label(code)
        tooltip = Keycode.tooltip(code)
        mask = Keycode.is_mask(code)
        mask_text = ""
        inner = Keycode.find_inner_keycode(code)
        if inner:
            mask_text = cls.get_label(inner.qmk_id)
        if mask:
            text = text.split("\n")[0]
        widget.masked = mask
        widget.setText(text)
        widget.setMaskText(mask_text)
        widget.setToolTip(tooltip)
        if cls.code_is_overriden(code):
            widget.setColor(QApplication.palette().color(QPalette.Link))
        else:
            widget.setColor(None)
        if inner and mask and cls.code_is_overriden(inner.qmk_id):
            widget.setMaskColor(QApplication.palette().color(QPalette.Link))
        else:
            widget.setMaskColor(None)

    @classmethod
    def set_keymap_override(cls, override):
        cls.keymap_override = override
        for client in cls.clients:
            client.on_keymap_override()

    @classmethod
    def notify_keymap_override(cls, client):
        cls.clients.append(client)
        client.on_keymap_override()

    @classmethod
    def unregister_keymap_override(cls, client):
        cls.clients.remove(client)

    @classmethod
    def relabel_buttons(cls, buttons):
        for widget in buttons:
            qmk_id = widget.keycode.qmk_id
            if qmk_id in KeycodeDisplay.keymap_override:
                label = KeycodeDisplay.keymap_override[qmk_id]
                highlight_color = QApplication.palette().color(QPalette.Link).getRgb()
                widget.setStyleSheet("QPushButton {color: rgb%s;}" % str(highlight_color))
            else:
                label = widget.keycode.label
                # Use smaller font for macro buttons with preview text (has newline)
                if qmk_id.startswith("M") and qmk_id[1:].isdigit() and '\n' in label:
                    # Lock in current size to prevent shrinking or growing
                    widget.setFixedSize(widget.sizeHint())
                    # Use HTML: M# centered, preview left-aligned with small gap, no wrap
                    parts = label.split('\n', 1)
                    preview = parts[1] if len(parts) > 1 else ""
                    html_label = '<div style="font-size:6pt"><center>{}</center><div style="margin-top:2px;white-space:nowrap" align="left">{}</div></div>'.format(
                        parts[0], preview)
                    widget.setWordWrap(True)
                    widget.setText(html_label)
                    continue
                else:
                    widget.setMinimumSize(0, 0)
                    widget.setMaximumSize(16777215, 16777215)  # Reset to default max
                    widget.setStyleSheet("QPushButton {}")
                    widget.setWordWrap(False)
            widget.setText(label.replace("&", "&&"))
