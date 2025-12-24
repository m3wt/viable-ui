# SPDX-License-Identifier: GPL-2.0-or-later

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton, QLabel, QHBoxLayout

class SquareButton(QPushButton):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.scale = 1.2
        self.label = None
        self.word_wrap = False
        self.text = ""
        self.keycode = None  # Set by caller if this button represents a keycode

    def setRelSize(self, ratio):
        self.scale = ratio
        self.updateGeometry()

    def setWordWrap(self, state):
        self.word_wrap = state
        self.setText(self.text)

    def sizeHint(self):
        size = int(round(self.fontMetrics().height() * self.scale))
        return QSize(size, size)

    # Override setText to facilitate automatic word wrapping
    def setText(self, text):
        self.text = text
        if self.word_wrap:
            super().setText("")
            if self.label is None:
                self.label = QLabel(text, self)
                self.label.setWordWrap(True)
                self.label.setTextFormat(Qt.RichText)
                self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(1, 1, 1, 1)
                layout.addWidget(self.label)
            else:
                self.label.setText(text)
            # Inherit font from button
            self.label.setFont(self.font())
        else:
            if self.label is not None:
                self.label.hide()
                self.label.deleteLater()
                self.label = None
            super().setText(text)

    def mouseDoubleClickEvent(self, ev):
        """Handle double-click to navigate to macro editor if this is a macro key"""
        if self.keycode and hasattr(self.keycode, 'qmk_id'):
            qmk_id = self.keycode.qmk_id
            if qmk_id.startswith("M") and qmk_id[1:].isdigit():
                macro_index = int(qmk_id[1:])
                from unlocker import Unlocker
                if Unlocker.global_main_window:
                    Unlocker.global_main_window.navigate_to_macro(macro_index)
                    ev.accept()
                    return
        super().mouseDoubleClickEvent(ev)