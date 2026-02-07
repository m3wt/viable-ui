# SPDX-License-Identifier: GPL-2.0-or-later

from qtpy.QtCore import Signal
from qtpy.QtWidgets import QLabel


class ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, ev):
        self.clicked.emit()
