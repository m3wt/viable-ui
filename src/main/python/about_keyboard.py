# SPDX-License-Identifier: GPL-2.0-or-later
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel, QPlainTextEdit


class AboutKeyboard(QDialog):

    def want_viable(self):
        if self.keyboard.sideload:
            return "unsupported - sideloaded keyboard"
        if not self.keyboard.viable_protocol:
            return "unsupported - no Viable firmware"
        return "unsupported - disabled in firmware"

    def about_tap_dance(self):
        if self.keyboard.tap_dance_count > 0:
            return str(self.keyboard.tap_dance_count)
        return self.want_viable()

    def about_combo(self):
        if self.keyboard.combo_count > 0:
            return str(self.keyboard.combo_count)
        return self.want_viable()

    def about_key_override(self):
        if self.keyboard.key_override_count > 0:
            return str(self.keyboard.key_override_count)
        return self.want_viable()

    def about_alt_repeat_key(self):
        if self.keyboard.alt_repeat_key_count > 0:
            return str(self.keyboard.alt_repeat_key_count)
        return self.want_viable()

    def about_macro_delays(self):
        # Viable always supports macro delays
        if self.keyboard.viable_protocol:
            return "yes"
        return self.want_viable()

    def about_macro_ext_keycodes(self):
        # Viable always supports extended macro keycodes
        if self.keyboard.viable_protocol:
            return "yes"
        return self.want_viable()

    def about_qmk_settings(self):
        if self.keyboard.viable_protocol:
            if len(self.keyboard.supported_settings) == 0:
                return "disabled in firmware"
            return "yes"
        return self.want_viable()

    def about_feature(self, feature_name):
        if feature_name in self.keyboard.supported_features:
            return "yes"
        return self.want_viable()

    def __init__(self, device):
        super().__init__()

        self.keyboard = device.keyboard
        self.setWindowTitle("About {}".format(device.title()))

        text = ""
        desc = device.desc
        text += "Manufacturer: {}\n".format(desc["manufacturer_string"])
        text += "Product: {}\n".format(desc["product_string"])
        text += "VID: {:04X}\n".format(desc["vendor_id"])
        text += "PID: {:04X}\n".format(desc["product_id"])
        text += "Device: {}\n".format(desc["path"])
        text += "\n"

        if self.keyboard.sideload:
            text += "Sideloaded JSON, dynamic features are disabled\n\n"

        text += "VIA protocol: {}\n".format(self.keyboard.via_protocol)
        text += "Viable protocol: {}\n".format(self.keyboard.viable_protocol or "none")
        text += "\n"

        text += "Macro entries: {}\n".format(self.keyboard.macro_count)
        text += "Macro memory: {} bytes\n".format(self.keyboard.macro_memory)
        text += "Macro delays: {}\n".format(self.about_macro_delays())
        text += "Complex (2-byte) macro keycodes: {}\n".format(self.about_macro_ext_keycodes())
        text += "\n"

        text += "Tap Dance entries: {}\n".format(self.about_tap_dance())
        text += "Combo entries: {}\n".format(self.about_combo())
        text += "Key Override entries: {}\n".format(self.about_key_override())
        text += "Alt Repeat Key entries: {}\n".format(self.about_alt_repeat_key())
        text += "Caps Word: {}\n".format(self.about_feature("caps_word"))
        text += "Layer Lock: {}\n".format(self.about_feature("layer_lock"))
        text += "\n"

        text += "QMK Settings: {}\n".format(self.about_qmk_settings())

        font = QFont("monospace")
        font.setStyleHint(QFont.TypeWriter)
        self.textarea = QPlainTextEdit()
        self.textarea.setReadOnly(True)
        self.textarea.setFont(font)

        self.textarea.setPlainText(text)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.textarea)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)
