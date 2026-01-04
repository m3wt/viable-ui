# SPDX-License-Identifier: GPL-2.0-or-later
from qtpy.QtCore import Signal, QObject, Qt
from qtpy.QtWidgets import (QWidget, QSizePolicy, QHBoxLayout, QVBoxLayout, QLabel,
                             QScrollArea, QPushButton, QCheckBox)

from change_manager import ChangeManager, LeaderChange
from widgets.key_widget import KeyWidget
from tabbed_keycodes import TabbedKeycodes
from vial_device import VialKeyboard
from editor.basic_editor import BasicEditor
from widgets.flowlayout import FlowLayout


class LeaderEntryUI(QObject):
    """A single leader entry: small index + 5 sequence keys + arrow + output key + enabled"""

    key_changed = Signal(int)  # emits leader index

    def __init__(self, idx):
        super().__init__()

        self.idx = idx
        self.kc_sequence = []
        self.all_keys = []  # All keys in order for auto-advance
        self.options = 0x8000  # Default: enabled

        # Main vertical layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(2)
        self.main_layout.setContentsMargins(4, 4, 4, 4)

        # Top row: keys
        self.keys_row = QHBoxLayout()
        self.keys_row.setSpacing(2)

        # Small superscript-style index number
        self.index_label = QLabel()
        self.index_label.setStyleSheet("font-size: 9px; color: palette(text); min-width: 20px;")
        self.index_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.update_index_label()
        self.keys_row.addWidget(self.index_label)

        # 5 sequence keys
        for x in range(5):
            kc_widget = KeyWidget()
            kc_widget.changed.connect(lambda idx=x: self.on_key_changed_at(idx))
            self.keys_row.addWidget(kc_widget)
            self.kc_sequence.append(kc_widget)
            self.all_keys.append(kc_widget)

        # Arrow
        arrow = QLabel("\u2192")  # ->
        arrow.setStyleSheet("font-size: 16px; color: palette(text);")
        arrow.setAlignment(Qt.AlignCenter)
        self.keys_row.addWidget(arrow)

        # Output key
        self.kc_output = KeyWidget()
        self.kc_output.changed.connect(lambda: self.on_key_changed_at(5))
        self.keys_row.addWidget(self.kc_output)
        self.all_keys.append(self.kc_output)

        self.main_layout.addLayout(self.keys_row)

        # Bottom row: enabled checkbox
        self.options_row = QHBoxLayout()
        self.options_row.setSpacing(4)

        self.enabled_label = QLabel("Enabled:")
        self.enabled_label.setStyleSheet("font-size: 9px; color: palette(text);")
        self.options_row.addWidget(self.enabled_label)

        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.stateChanged.connect(self.on_enabled_changed)
        self.options_row.addWidget(self.enabled_checkbox)

        self.options_row.addStretch()
        self.main_layout.addLayout(self.options_row)

        # Create the widget
        self.widget_container = QWidget()
        self.widget_container.setObjectName("leaderEntry")
        self.widget_container.setStyleSheet("#leaderEntry { border: 2px solid transparent; }")
        self.widget_container.setLayout(self.main_layout)
        self.widget_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def update_index_label(self):
        self.index_label.setText(str(self.idx + 1))

    def set_modified(self, modified):
        """Set visual indicator for uncommitted changes."""
        if modified:
            self.widget_container.setStyleSheet("#leaderEntry { border: 2px solid palette(link); }")
        else:
            self.widget_container.setStyleSheet("#leaderEntry { border: 2px solid transparent; }")

    def widget(self):
        return self.widget_container

    def load(self, data):
        objs = self.kc_sequence + [self.kc_output]
        for o in objs:
            o.blockSignals(True)
        self.enabled_checkbox.blockSignals(True)

        for x in range(5):
            self.kc_sequence[x].set_keycode(data[x])
        self.kc_output.set_keycode(data[5])

        # Load options (7th element)
        # Bit 15 = enabled
        if len(data) > 6:
            self.options = data[6]
            self.enabled_checkbox.setChecked(bool(self.options & 0x8000))
        else:
            self.options = 0x8000  # enabled
            self.enabled_checkbox.setChecked(True)

        for o in objs:
            o.blockSignals(False)
        self.enabled_checkbox.blockSignals(False)

    def save(self):
        # Use checkbox for enabled bit
        options = self.options & 0x7FFF  # Clear enabled bit
        if self.enabled_checkbox.isChecked():
            options |= 0x8000  # Set enabled bit
        return (
            self.kc_sequence[0].keycode,
            self.kc_sequence[1].keycode,
            self.kc_sequence[2].keycode,
            self.kc_sequence[3].keycode,
            self.kc_sequence[4].keycode,
            self.kc_output.keycode,
            options
        )

    def is_empty(self):
        """Check if this leader entry has no keys defined"""
        for kc in self.kc_sequence:
            if kc.keycode and kc.keycode != "KC_NO":
                return False
        if self.kc_output.keycode and self.kc_output.keycode != "KC_NO":
            return False
        return True

    def on_enabled_changed(self):
        """Handle enabled checkbox change"""
        self.key_changed.emit(self.idx)

    def on_key_changed_at(self, key_idx):
        """Called when a specific key changes - auto-advance to next"""
        self.key_changed.emit(self.idx)

        # Auto-advance to next key (0-4 are sequence, 5 is output)
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
        for kc in self.kc_sequence:
            kc.delete()
        self.kc_output.delete()


class Leader(BasicEditor):

    CM_KEY_TYPE = 'leader'

    def __init__(self):
        super().__init__()
        self.keyboard = None

        self.leader_entries = []
        self.leader_entries_available = []

        # Pre-create leader entry UIs
        for x in range(128):
            entry = LeaderEntryUI(x)
            entry.key_changed.connect(self.on_key_changed)
            self.leader_entries_available.append(entry)

        # Header with count and buttons
        header = QHBoxLayout()
        self.count_label = QLabel("0 of 0 leader sequences defined")
        header.addWidget(self.count_label)
        header.addStretch()

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setFixedWidth(60)
        self.add_btn.clicked.connect(self.on_add_leader)
        header.addWidget(self.add_btn)

        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.setCheckable(True)
        self.show_all_btn.setFixedWidth(80)
        self.show_all_btn.toggled.connect(self.on_show_all_toggled)
        header.addWidget(self.show_all_btn)

        header_widget = QWidget()
        header_widget.setLayout(header)
        self.addWidget(header_widget)

        # Scrollable area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Flow layout for entries
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
        self.leader_entries = self.leader_entries_available[:self.keyboard.leader_count]
        for x, e in enumerate(self.leader_entries):
            e.load(self.keyboard.leader_get(x))

        self.refresh_display()

    def refresh_display(self):
        """Refresh which entries are shown based on show_all setting"""
        cm = ChangeManager.instance()

        # Clear flow layout
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().hide()

        # Count defined entries and add widgets
        defined_count = 0
        for e in self.leader_entries:
            # Update modified indicator
            e.set_modified(cm.is_modified(('leader', e.idx)))

            if not e.is_empty():
                defined_count += 1

            if self.show_all or not e.is_empty():
                e.widget().show()
                self.flow_layout.addWidget(e.widget())

        # Update count label
        self.count_label.setText(f"{defined_count} of {len(self.leader_entries)} leader sequences defined")

        # Update button text
        if self.show_all:
            self.show_all_btn.setText("Hide Empty")
        else:
            self.show_all_btn.setText("Show All")

    def on_show_all_toggled(self, checked):
        self.show_all = checked
        self.refresh_display()

    def on_add_leader(self):
        """Find first empty entry, show it, and select its first key"""
        for e in self.leader_entries:
            if e.is_empty():
                # Make sure this entry is visible
                if not self.show_all:
                    e.widget().show()
                    self.flow_layout.addWidget(e.widget())

                # Select the first key
                first_key = e.all_keys[0]
                first_key.active_key = first_key.widgets[0]
                first_key.active_mask = False
                first_key.update()
                TabbedKeycodes.open_tray(first_key)

                # Scroll to make it visible
                self.scroll.ensureWidgetVisible(e.widget())
                return

    def rebuild(self, device):
        super().rebuild(device)
        if self.valid():
            self.keyboard = device.keyboard
            self.rebuild_ui()

    def _reload_entry(self, idx):
        if idx < len(self.leader_entries):
            self.leader_entries[idx].load(self.keyboard.leader_get(idx))

    def valid(self):
        return isinstance(self.device, VialKeyboard) and \
               (self.device.keyboard and self.device.keyboard.viable_protocol
                and self.device.keyboard.leader_count > 0)

    def on_key_changed(self, idx):
        new_value = self.leader_entries[idx].save()
        old_value = self.keyboard.leader_entries[idx]

        if old_value != new_value:
            # Track change in ChangeManager for undo/redo
            change = LeaderChange(idx, old_value, new_value)
            ChangeManager.instance().add_change(change)
            # Update local state
            self.keyboard.leader_entries[idx] = new_value

        # Refresh display in case entry became empty or non-empty
        if not self.show_all:
            self.refresh_display()
        else:
            # Just update count
            defined_count = sum(1 for e in self.leader_entries if not e.is_empty())
            self.count_label.setText(f"{defined_count} of {len(self.leader_entries)} leader sequences defined")
