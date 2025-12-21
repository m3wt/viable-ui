# SPDX-License-Identifier: GPL-2.0-or-later
from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
                              QGridLayout, QLabel, QComboBox, QCheckBox,
                              QColorDialog, QGroupBox, QScrollArea, QSizePolicy)

from editor.basic_editor import BasicEditor
from widgets.clickable_label import ClickableLabel
from util import tr
from vial_device import VialKeyboard


class SvalboardEditor(BasicEditor):

    def __init__(self):
        super().__init__()
        self.keyboard = None

        # Pending changes (for deferred save)
        self.pending_layer_colors = None
        self.pending_settings = None

        # Create scrollable container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        container_widget = QWidget()
        self.container = QVBoxLayout()
        self.container.setAlignment(Qt.AlignTop)
        container_widget.setLayout(self.container)
        scroll.setWidget(container_widget)

        # Layer Colors section
        self._create_layer_colors_section()

        # Left/Right Pointer sections side by side
        self._create_pointer_sections()

        # Mouse Layer section
        self._create_mouse_section()

        # Scroll section
        self._create_scroll_section()

        # Experimental/Dangerous section
        self._create_experimental_section()

        self.container.addStretch()
        self.addWidget(scroll)

        # Buttons at bottom (outside scroll area)
        self._create_buttons()

    def _create_layer_colors_section(self):
        group = QGroupBox(tr("SvalboardEditor", "Layer Colors"))
        layout = QGridLayout()

        self.layer_color_widgets = []
        # 4x8 grid for up to 32 layers
        for i in range(32):
            row = i // 8
            col = i % 8

            frame = QWidget()
            frame_layout = QVBoxLayout()
            frame_layout.setContentsMargins(2, 2, 2, 2)
            frame_layout.setSpacing(2)

            color_btn = ClickableLabel()
            color_btn.setFixedSize(30, 20)
            color_btn.setStyleSheet("background-color: #000000; border: 1px solid gray;")
            color_btn.clicked.connect(lambda idx=i: self.on_layer_color_click(idx))

            label = QLabel(str(i))
            label.setAlignment(Qt.AlignCenter)

            frame_layout.addWidget(color_btn, alignment=Qt.AlignCenter)
            frame_layout.addWidget(label)
            frame.setLayout(frame_layout)

            layout.addWidget(frame, row, col)
            self.layer_color_widgets.append((frame, color_btn, label))

        group.setLayout(layout)
        self.layer_colors_group = group
        self.container.addWidget(group)

    def _create_pointer_sections(self):
        # Container for left and right pointer groups side by side
        pointer_container = QHBoxLayout()

        # Left Pointer group
        left_group = QGroupBox(tr("SvalboardEditor", "Left Pointer"))
        left_layout = QGridLayout()

        left_layout.addWidget(QLabel(tr("SvalboardEditor", "DPI")), 0, 0)
        self.left_dpi = QComboBox()
        self.left_dpi.currentIndexChanged.connect(self.on_setting_changed)
        left_layout.addWidget(self.left_dpi, 0, 1)

        self.left_scroll = QCheckBox(tr("SvalboardEditor", "Scroll mode"))
        self.left_scroll.stateChanged.connect(self.on_setting_changed)
        left_layout.addWidget(self.left_scroll, 1, 0, 1, 2)

        left_group.setLayout(left_layout)
        pointer_container.addWidget(left_group)

        # Right Pointer group
        right_group = QGroupBox(tr("SvalboardEditor", "Right Pointer"))
        right_layout = QGridLayout()

        right_layout.addWidget(QLabel(tr("SvalboardEditor", "DPI")), 0, 0)
        self.right_dpi = QComboBox()
        self.right_dpi.currentIndexChanged.connect(self.on_setting_changed)
        right_layout.addWidget(self.right_dpi, 0, 1)

        self.right_scroll = QCheckBox(tr("SvalboardEditor", "Scroll mode"))
        self.right_scroll.stateChanged.connect(self.on_setting_changed)
        right_layout.addWidget(self.right_scroll, 1, 0, 1, 2)

        right_group.setLayout(right_layout)
        pointer_container.addWidget(right_group)

        self.container.addLayout(pointer_container)

    def _create_mouse_section(self):
        group = QGroupBox(tr("SvalboardEditor", "Mouse Layer"))
        layout = QGridLayout()

        # Auto-mouse
        self.auto_mouse = QCheckBox(tr("SvalboardEditor", "Enable"))
        self.auto_mouse.stateChanged.connect(self.on_setting_changed)
        layout.addWidget(self.auto_mouse, 0, 0, 1, 2)

        # Mouse layer timeout (populated dynamically from firmware)
        layout.addWidget(QLabel(tr("SvalboardEditor", "Timeout")), 1, 0)
        self.mh_timeout = QComboBox()
        self.mh_timeout.currentIndexChanged.connect(self.on_setting_changed)
        layout.addWidget(self.mh_timeout, 1, 1)

        group.setLayout(layout)
        self.container.addWidget(group)

    def _create_scroll_section(self):
        group = QGroupBox(tr("SvalboardEditor", "Scroll"))
        layout = QGridLayout()

        # Axis scroll lock
        self.axis_scroll_lock = QCheckBox(tr("SvalboardEditor", "Axis lock"))
        self.axis_scroll_lock.stateChanged.connect(self.on_setting_changed)
        layout.addWidget(self.axis_scroll_lock, 0, 0, 1, 2)

        group.setLayout(layout)
        self.container.addWidget(group)

    def _create_experimental_section(self):
        group = QGroupBox(tr("SvalboardEditor", "Experimental/Dangerous"))
        layout = QGridLayout()

        # Turbo scan (populated dynamically from firmware)
        layout.addWidget(QLabel(tr("SvalboardEditor", "Turbo scan level")), 0, 0)
        self.turbo_scan = QComboBox()
        self.turbo_scan.currentIndexChanged.connect(self.on_setting_changed)
        layout.addWidget(self.turbo_scan, 0, 1)

        group.setLayout(layout)
        self.container.addWidget(group)

    def _create_buttons(self):
        buttons = QHBoxLayout()
        buttons.addStretch()

        self.btn_save = QPushButton(tr("SvalboardEditor", "Save"))
        self.btn_save.clicked.connect(self.on_save)
        self.btn_save.setEnabled(False)
        buttons.addWidget(self.btn_save)

        self.btn_undo = QPushButton(tr("SvalboardEditor", "Undo"))
        self.btn_undo.clicked.connect(self.on_undo)
        self.btn_undo.setEnabled(False)
        buttons.addWidget(self.btn_undo)

        self.addLayout(buttons)

    def valid(self):
        return (isinstance(self.device, VialKeyboard) and
                self.device.keyboard is not None and
                getattr(self.device.keyboard, 'is_svalboard', False))

    def rebuild(self, device):
        super().rebuild(device)
        if self.valid():
            self.keyboard = device.keyboard
            self._update_layer_visibility()
            self._update_dpi_dropdowns()
            self._update_mh_timeout_dropdown()
            self._update_turbo_scan_dropdown()
            self.update_from_keyboard()

    def _update_dpi_dropdowns(self):
        """Populate DPI dropdowns with values from firmware"""
        self.left_dpi.blockSignals(True)
        self.right_dpi.blockSignals(True)

        self.left_dpi.clear()
        self.right_dpi.clear()

        for dpi in self.keyboard.sval_dpi_levels:
            self.left_dpi.addItem(str(dpi))
            self.right_dpi.addItem(str(dpi))

        self.left_dpi.blockSignals(False)
        self.right_dpi.blockSignals(False)

    def _update_mh_timeout_dropdown(self):
        """Populate mouse layer timeout dropdown with values from firmware"""
        self.mh_timeout.blockSignals(True)
        self.mh_timeout.clear()

        for timeout in self.keyboard.sval_mh_timers:
            if timeout < 0:
                self.mh_timeout.addItem("Infinite")
            else:
                self.mh_timeout.addItem(f"{timeout} ms")

        self.mh_timeout.blockSignals(False)

    def _update_turbo_scan_dropdown(self):
        """Populate turbo scan dropdown with levels from firmware"""
        self.turbo_scan.blockSignals(True)
        self.turbo_scan.clear()

        for level in range(self.keyboard.sval_turbo_scan_limit):
            self.turbo_scan.addItem(str(level))

        self.turbo_scan.blockSignals(False)

    def _update_layer_visibility(self):
        """Show/hide layer color widgets based on actual layer count"""
        layer_count = self.keyboard.sval_layer_count
        for i, (frame, color_btn, label) in enumerate(self.layer_color_widgets):
            if i < layer_count:
                frame.show()
            else:
                frame.hide()

    def update_from_keyboard(self):
        """Load current state from keyboard into widgets"""
        if not self.keyboard:
            return

        self._block_signals()

        # Load layer colors
        if self.keyboard.sval_layer_colors:
            self.pending_layer_colors = list(self.keyboard.sval_layer_colors)
            for i, (h, s, v) in enumerate(self.keyboard.sval_layer_colors):
                if i < len(self.layer_color_widgets):
                    # Firmware uses 0-255 for hue, Qt uses 0-359
                    qt_hue = int(h * 359 / 255) if h > 0 else 0
                    color = QColor.fromHsv(qt_hue, s, v)
                    self.layer_color_widgets[i][1].setStyleSheet(
                        f"background-color: {color.name()}; border: 1px solid gray;"
                    )

        # Load settings
        if self.keyboard.sval_settings:
            settings = self.keyboard.sval_settings
            self.pending_settings = settings.copy()

            self.left_dpi.setCurrentIndex(settings.get('left_dpi_index', 0))
            self.right_dpi.setCurrentIndex(settings.get('right_dpi_index', 0))
            self.left_scroll.setChecked(settings.get('left_scroll', False))
            self.right_scroll.setChecked(settings.get('right_scroll', False))
            self.axis_scroll_lock.setChecked(settings.get('axis_scroll_lock', False))
            self.auto_mouse.setChecked(settings.get('auto_mouse', False))
            self.mh_timeout.setCurrentIndex(settings.get('mh_timer_index', 0))
            self.turbo_scan.setCurrentIndex(settings.get('turbo_scan', 0))

        self._unblock_signals()
        self._update_buttons()

    def _block_signals(self):
        self.left_dpi.blockSignals(True)
        self.right_dpi.blockSignals(True)
        self.left_scroll.blockSignals(True)
        self.right_scroll.blockSignals(True)
        self.axis_scroll_lock.blockSignals(True)
        self.auto_mouse.blockSignals(True)
        self.mh_timeout.blockSignals(True)
        self.turbo_scan.blockSignals(True)

    def _unblock_signals(self):
        self.left_dpi.blockSignals(False)
        self.right_dpi.blockSignals(False)
        self.left_scroll.blockSignals(False)
        self.right_scroll.blockSignals(False)
        self.axis_scroll_lock.blockSignals(False)
        self.auto_mouse.blockSignals(False)
        self.mh_timeout.blockSignals(False)
        self.turbo_scan.blockSignals(False)

    def on_layer_color_click(self, layer_idx):
        if not self.pending_layer_colors or layer_idx >= len(self.pending_layer_colors):
            return

        h, s, v = self.pending_layer_colors[layer_idx]
        # Firmware uses 0-255 for hue, Qt uses 0-359
        qt_hue = int(h * 359 / 255) if h > 0 else 0
        current_color = QColor.fromHsv(qt_hue, s, v)

        dlg = QColorDialog()
        dlg.setCurrentColor(current_color)
        if dlg.exec_():
            color = dlg.selectedColor()
            qt_h = color.hue() if color.hue() >= 0 else 0
            # Convert Qt hue (0-359) back to firmware hue (0-255)
            fw_h = int(qt_h * 255 / 359) if qt_h > 0 else 0
            new_s = color.saturation()
            new_v = color.value()

            self.pending_layer_colors[layer_idx] = (fw_h, new_s, new_v)
            self.layer_color_widgets[layer_idx][1].setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid gray;"
            )
            self._update_buttons()

    def on_setting_changed(self):
        if not self.pending_settings:
            return

        self.pending_settings['left_dpi_index'] = self.left_dpi.currentIndex()
        self.pending_settings['right_dpi_index'] = self.right_dpi.currentIndex()
        self.pending_settings['left_scroll'] = self.left_scroll.isChecked()
        self.pending_settings['right_scroll'] = self.right_scroll.isChecked()
        self.pending_settings['axis_scroll_lock'] = self.axis_scroll_lock.isChecked()
        self.pending_settings['auto_mouse'] = self.auto_mouse.isChecked()
        self.pending_settings['mh_timer_index'] = self.mh_timeout.currentIndex()
        self.pending_settings['turbo_scan'] = self.turbo_scan.currentIndex()

        self._update_buttons()

    def _has_changes(self):
        if not self.keyboard:
            return False

        # Check layer colors
        if self.pending_layer_colors and self.keyboard.sval_layer_colors:
            if self.pending_layer_colors != list(self.keyboard.sval_layer_colors):
                return True

        # Check settings
        if self.pending_settings and self.keyboard.sval_settings:
            if self.pending_settings != self.keyboard.sval_settings:
                return True

        return False

    def _update_buttons(self):
        has_changes = self._has_changes()
        self.btn_save.setEnabled(has_changes)
        self.btn_undo.setEnabled(has_changes)

    def on_save(self):
        if not self.keyboard:
            return

        # Save layer colors
        if self.pending_layer_colors and self.keyboard.sval_layer_colors:
            for i, (h, s, v) in enumerate(self.pending_layer_colors):
                if i < len(self.keyboard.sval_layer_colors):
                    old_h, old_s, old_v = self.keyboard.sval_layer_colors[i]
                    if (h, s, v) != (old_h, old_s, old_v):
                        self.keyboard.sval_set_layer_color(i, h, s, v)

        # Save settings
        if self.pending_settings and self.keyboard.sval_settings:
            if self.pending_settings != self.keyboard.sval_settings:
                self.keyboard.sval_set_settings(self.pending_settings)

        self._update_buttons()

    def on_undo(self):
        self.keyboard.sval_reload_layer_colors()
        self.keyboard.sval_reload_settings()
        self.update_from_keyboard()

    def save_state(self):
        """Return current state as a dict for saving to file"""
        if not self.valid():
            return None

        # Save layer colors as list of dicts for readability
        layer_colors = []
        if self.pending_layer_colors:
            for h, s, v in self.pending_layer_colors:
                layer_colors.append({"h": h, "s": s, "v": v})

        return {
            "layer_colors": layer_colors,
            "settings": self.pending_settings.copy() if self.pending_settings else {}
        }

    def restore_state(self, data):
        """Restore state from saved data dict"""
        if not self.valid() or not data:
            return

        self._block_signals()

        # Restore layer colors
        layer_colors = data.get("layer_colors", [])
        if layer_colors and self.pending_layer_colors:
            for i, color_data in enumerate(layer_colors):
                if i < len(self.pending_layer_colors):
                    h = color_data.get("h", 0)
                    s = color_data.get("s", 0)
                    v = color_data.get("v", 0)
                    self.pending_layer_colors[i] = (h, s, v)

                    # Update widget display
                    qt_hue = int(h * 359 / 255) if h > 0 else 0
                    color = QColor.fromHsv(qt_hue, s, v)
                    self.layer_color_widgets[i][1].setStyleSheet(
                        f"background-color: {color.name()}; border: 1px solid gray;"
                    )

        # Restore settings
        settings = data.get("settings", {})
        if settings and self.pending_settings:
            self.pending_settings.update(settings)

            self.left_dpi.setCurrentIndex(settings.get('left_dpi_index', 0))
            self.right_dpi.setCurrentIndex(settings.get('right_dpi_index', 0))
            self.left_scroll.setChecked(settings.get('left_scroll', False))
            self.right_scroll.setChecked(settings.get('right_scroll', False))
            self.axis_scroll_lock.setChecked(settings.get('axis_scroll_lock', False))
            self.auto_mouse.setChecked(settings.get('auto_mouse', False))
            self.mh_timeout.setCurrentIndex(settings.get('mh_timer_index', 0))
            self.turbo_scan.setCurrentIndex(settings.get('turbo_scan', 0))

        self._unblock_signals()
        self._update_buttons()
