from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class EditorContainer(QWidget):

    clicked = Signal()

    def __init__(self, editor):
        super().__init__()

        self.editor = editor

        self.setLayout(editor)
        self.clicked.connect(editor.on_container_clicked)

    def mousePressEvent(self, ev):
        self.clicked.emit()
