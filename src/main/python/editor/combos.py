# SPDX-License-Identifier: GPL-2.0-or-later
from qtpy import QtCore
from qtpy.QtCore import Signal, QObject, Qt
from qtpy.QtWidgets import (QWidget, QSizePolicy, QHBoxLayout, QVBoxLayout, QLabel,
                             QScrollArea, QPushButton, QSpinBox, QCheckBox, QGridLayout)

from change_manager import ChangeManager, ComboChange
from widgets.key_widget import KeyWidget
from tabbed_keycodes import TabbedKeycodes
from vial_device import VialKeyboard
from editor.basic_editor import BasicEditor
from widgets.flowlayout import FlowLayout


class ComboEntryUI(QObject):
    """A single combo entry: small index + 4 input keys + arrow + output key + custom term"""

    key_changed = Signal(int)  # emits combo index
    deleted = Signal(int)  # emits combo index

    def __init__(self, idx):
        super().__init__()

        self.idx = idx
        self.kc_inputs = []
        self.all_keys = []  # All keys in order for auto-advance
        self.custom_combo_term = 0x8000  # Default: enabled, no custom term

        # Use grid layout for proper column alignment
        self.container = QGridLayout()
        self.container.setSpacing(2)
        self.container.setContentsMargins(4, 4, 4, 4)

        # Row 0: Index and column headers
        self.index_label = QLabel()
        self.index_label.setStyleSheet("font-size: 9px; color: palette(text);")
        self.index_label.setAlignment(Qt.AlignCenter)
        self.update_index_label()
        self.container.addWidget(self.index_label, 0, 0)

        # Input key headers (columns 1-4)
        for col in range(4):
            lbl = QLabel(f"In{col + 1}")
            lbl.setStyleSheet("font-size: 9px; color: palette(text);")
            lbl.setAlignment(Qt.AlignCenter)
            self.container.addWidget(lbl, 0, col + 1)

        # Arrow column (5) - no header needed
        # Output header (column 6)
        out_header = QLabel("Out")
        out_header.setStyleSheet("font-size: 9px; color: palette(text);")
        out_header.setAlignment(Qt.AlignCenter)
        self.container.addWidget(out_header, 0, 6)

        # Term header (column 7)
        term_header = QLabel("Term")
        term_header.setStyleSheet("font-size: 9px; color: palette(text);")
        term_header.setAlignment(Qt.AlignCenter)
        self.container.addWidget(term_header, 0, 7)

        # Row 1: Enable checkbox under index, then keys and term
        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.stateChanged.connect(self.on_enabled_changed)
        self.container.addWidget(self.enabled_checkbox, 1, 0, Qt.AlignCenter)

        # 4 input keys
        for x in range(4):
            kc_widget = KeyWidget()
            kc_widget.changed.connect(lambda idx=x: self.on_key_changed_at(idx))
            self.container.addWidget(kc_widget, 1, x + 1)
            self.kc_inputs.append(kc_widget)
            self.all_keys.append(kc_widget)

        # Arrow
        arrow = QLabel("\u2192")  # →
        arrow.setStyleSheet("font-size: 16px; color: palette(text);")
        arrow.setAlignment(Qt.AlignCenter)
        self.container.addWidget(arrow, 1, 5)

        # Output key
        self.kc_output = KeyWidget()
        self.kc_output.changed.connect(lambda: self.on_key_changed_at(4))
        self.container.addWidget(self.kc_output, 1, 6)
        self.all_keys.append(self.kc_output)

        # Term spinbox
        self.term_spinbox = QSpinBox()
        self.term_spinbox.setRange(0, 32767)
        self.term_spinbox.setSuffix(" ms")
        self.term_spinbox.setSpecialValueText("default")
        self.term_spinbox.setToolTip("Custom combo term (0 = use global default)")
        self.term_spinbox.setFixedWidth(80)
        self.term_spinbox.valueChanged.connect(self.on_term_changed)
        self.container.addWidget(self.term_spinbox, 1, 7)

        # Create the widget
        self.widget_container = QWidget()
        self.widget_container.setObjectName("comboEntry")
        self.widget_container.setStyleSheet("#comboEntry { border: 2px solid transparent; }")
        self.widget_container.setLayout(self.container)
        self.widget_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def update_index_label(self):
        self.index_label.setText(str(self.idx + 1))

    def set_modified(self, modified):
        """Set visual indicator for uncommitted changes."""
        if modified:
            self.widget_container.setStyleSheet("#comboEntry { border: 2px solid palette(link); }")
        else:
            self.widget_container.setStyleSheet("#comboEntry { border: 2px solid transparent; }")

    def widget(self):
        return self.widget_container

    def load(self, data):
        objs = self.kc_inputs + [self.kc_output]
        for o in objs:
            o.blockSignals(True)
        self.term_spinbox.blockSignals(True)
        self.enabled_checkbox.blockSignals(True)

        for x in range(4):
            self.kc_inputs[x].set_keycode(data[x])
        self.kc_output.set_keycode(data[4])

        # Load custom_combo_term (6th element)
        # Bit 15 = enabled, bits 0-14 = timing
        if len(data) > 5:
            self.custom_combo_term = data[5]
            term_value = self.custom_combo_term & 0x7FFF
            self.term_spinbox.setValue(term_value)
            self.enabled_checkbox.setChecked(bool(self.custom_combo_term & 0x8000))
        else:
            # Old format without custom_combo_term
            self.custom_combo_term = 0x8000  # enabled, default timing
            self.term_spinbox.setValue(0)
            self.enabled_checkbox.setChecked(True)

        for o in objs:
            o.blockSignals(False)
        self.term_spinbox.blockSignals(False)
        self.enabled_checkbox.blockSignals(False)

    def save(self):
        # Use checkbox for enabled bit
        term = self.term_spinbox.value() & 0x7FFF  # Get timing bits
        if self.enabled_checkbox.isChecked():
            term |= 0x8000  # Set enabled bit
        return (
            self.kc_inputs[0].keycode,
            self.kc_inputs[1].keycode,
            self.kc_inputs[2].keycode,
            self.kc_inputs[3].keycode,
            self.kc_output.keycode,
            term
        )

    def is_empty(self):
        """Check if this combo has no keys defined"""
        for kc in self.kc_inputs:
            if kc.keycode and kc.keycode != "KC_NO":
                return False
        if self.kc_output.keycode and self.kc_output.keycode != "KC_NO":
            return False
        return True

    def on_term_changed(self, value):
        """Handle custom combo term change"""
        # Keep the enabled bit (bit 15), update timing bits (0-14)
        enabled = self.custom_combo_term & 0x8000
        self.custom_combo_term = enabled | (value & 0x7FFF)
        self.key_changed.emit(self.idx)

    def on_enabled_changed(self):
        """Handle enabled checkbox change"""
        self.key_changed.emit(self.idx)

    def on_key_changed_at(self, key_idx):
        """Called when a specific key in the combo changes - auto-advance to next"""
        self.key_changed.emit(self.idx)

        # Auto-advance to next key (0-3 are inputs, 4 is output)
        next_idx = key_idx + 1
        if next_idx < len(self.all_keys):
            next_key = self.all_keys[next_idx]
            # Select the key (set it as active so it highlights)
            next_key.active_key = next_key.widgets[0]
            next_key.active_mask = False
            next_key.update()
            # Open the keycode tray for the next key
            TabbedKeycodes.open_tray(next_key)

    def delete_widgets(self):
        """Clean up widgets for deletion"""
        for kc in self.kc_inputs:
            kc.delete()
        self.kc_output.delete()


class Combos(BasicEditor):

    CM_KEY_TYPE = 'combo'

    def __init__(self):
        super().__init__()
        self.keyboard = None

        self.combo_entries = []
        self.combo_entries_available = []

        # Pre-create combo entry UIs
        for x in range(128):
            entry = ComboEntryUI(x)
            entry.key_changed.connect(self.on_key_changed)
            self.combo_entries_available.append(entry)

        # Header with count and buttons
        header = QHBoxLayout()
        self.count_label = QLabel("0 of 0 combos defined")
        header.addWidget(self.count_label)
        header.addStretch()

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setFixedWidth(60)
        self.add_btn.clicked.connect(self.on_add_combo)
        header.addWidget(self.add_btn)

        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.setCheckable(True)
        self.show_all_btn.setFixedWidth(80)
        self.show_all_btn.toggled.connect(self.on_show_all_toggled)
        header.addWidget(self.show_all_btn)

        header_widget = QWidget()
        header_widget.setLayout(header)
        self.addWidget(header_widget)

        # Scrollable area for combos
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Flow layout for combo entries
        self.flow_container = QWidget()
        self.flow_layout = FlowLayout()
        self.flow_layout.setSpacing(8)
        self.flow_container.setLayout(self.flow_layout)

        self.scroll.setWidget(self.flow_container)
        self.addWidget(self.scroll)

        self.show_all = False

    def rebuild_ui(self):
        # Clear flow layout
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().hide()

        # Load data into entries
        self.combo_entries = self.combo_entries_available[:self.keyboard.combo_count]
        for x, e in enumerate(self.combo_entries):
            e.load(self.keyboard.combo_get(x))

        self.refresh_display()

    def refresh_display(self):
        """Refresh which combos are shown based on show_all setting"""
        cm = ChangeManager.instance()

        # Clear flow layout
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().hide()

        # Count defined combos and add widgets
        defined_count = 0
        for e in self.combo_entries:
            # Update modified indicator
            e.set_modified(cm.is_modified(('combo', e.idx)))

            if not e.is_empty():
                defined_count += 1

            if self.show_all or not e.is_empty():
                e.widget().show()
                self.flow_layout.addWidget(e.widget())

        # Update count label
        self.count_label.setText(f"{defined_count} of {len(self.combo_entries)} combos defined")

        # Update button text
        if self.show_all:
            self.show_all_btn.setText("Hide Empty")
        else:
            self.show_all_btn.setText("Show All")

    def on_show_all_toggled(self, checked):
        self.show_all = checked
        self.refresh_display()

    def on_add_combo(self):
        """Find first empty combo, show it, and select its first key"""
        for e in self.combo_entries:
            if e.is_empty():
                # Make sure this combo is visible
                if not self.show_all:
                    e.widget().show()
                    self.flow_layout.addWidget(e.widget())

                # Select the first key of this combo
                first_key = e.all_keys[0]
                first_key.active_key = first_key.widgets[0]
                first_key.active_mask = False
                first_key.update()
                TabbedKeycodes.open_tray(first_key)

                # Scroll to make it visible
                self.scroll.ensureWidgetVisible(e.widget())
                return

        # No empty combos available
        # Could show a message, but for now just do nothing

    def rebuild(self, device):
        super().rebuild(device)
        if self.valid():
            self.keyboard = device.keyboard
            self.rebuild_ui()

    def _reload_entry(self, idx):
        if idx < len(self.combo_entries):
            self.combo_entries[idx].load(self.keyboard.combo_get(idx))

    def valid(self):
        return isinstance(self.device, VialKeyboard) and \
               (self.device.keyboard and self.device.keyboard.viable_protocol
                and self.device.keyboard.combo_count > 0)

    def on_key_changed(self, idx):
        new_value = self.combo_entries[idx].save()
        old_value = self.keyboard.combo_entries[idx]

        if old_value != new_value:
            # Track change in ChangeManager for undo/redo
            change = ComboChange(idx, old_value, new_value)
            ChangeManager.instance().add_change(change)
            # Update local state
            self.keyboard.combo_entries[idx] = new_value

        # Refresh display in case combo became empty or non-empty
        if not self.show_all:
            self.refresh_display()
        else:
            # Just update count
            defined_count = sum(1 for e in self.combo_entries if not e.is_empty())
            self.count_label.setText(f"{defined_count} of {len(self.combo_entries)} combos defined")
