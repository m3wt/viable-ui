# SPDX-License-Identifier: GPL-2.0-or-later
import json
from collections import defaultdict

from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QVBoxLayout, QCheckBox, QGridLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QTabWidget, QSpinBox, QFrame

from change_manager import ChangeManager, QmkSettingChange
from editor.basic_editor import BasicEditor
from protocol.constants import VIAL_PROTOCOL_QMK_SETTINGS
from util import tr
from vial_device import VialKeyboard


class GenericOption(QObject):

    changed = pyqtSignal()

    def __init__(self, option, container):
        super().__init__()

        self.row = container.rowCount()
        self.option = option
        self.qsid = self.option["qsid"]
        self.container = container

        # Create frame to hold label + widget for unified highlighting
        self.frame = QFrame()
        self.frame.setObjectName("option_frame")
        self.frame.setStyleSheet("#option_frame { border: 2px solid transparent; }")
        self.frame_layout = QHBoxLayout()
        self.frame_layout.setContentsMargins(2, 2, 2, 2)
        self.frame_layout.setSpacing(8)
        self.frame.setLayout(self.frame_layout)

        self.lbl = QLabel(option["title"])
        self.frame_layout.addWidget(self.lbl)
        self.frame_layout.addStretch()

        self.container.addWidget(self.frame, self.row, 0, 1, 2)

    def reload(self, keyboard):
        return keyboard.settings.get(self.qsid)

    def delete(self):
        self.frame.hide()
        self.frame.deleteLater()

    def on_change(self):
        self.changed.emit()


class BooleanOption(GenericOption):

    def __init__(self, option, container):
        super().__init__(option, container)

        self.qsid_bit = self.option.get("bit", 0)

        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self.on_change)
        self.frame_layout.addWidget(self.checkbox)

    def reload(self, keyboard):
        value = super().reload(keyboard)
        checked = value & (1 << self.qsid_bit)

        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(checked != 0)
        self.checkbox.blockSignals(False)

    def value(self):
        checked = int(self.checkbox.isChecked())
        return checked << self.qsid_bit

    def is_modified(self, current_full, committed_full):
        """Check if this specific bit changed."""
        mask = 1 << self.qsid_bit
        current_bit = current_full & mask
        committed_bit = committed_full & mask
        return current_bit != committed_bit

    def set_modified(self, modified):
        if modified:
            self.frame.setStyleSheet("#option_frame { border: 2px solid palette(link); }")
        else:
            self.frame.setStyleSheet("#option_frame { border: 2px solid transparent; }")


class IntegerOption(GenericOption):

    def __init__(self, option, container):
        super().__init__(option, container)

        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(option["min"])
        self.spinbox.setMaximum(option["max"])
        self.spinbox.valueChanged.connect(self.on_change)
        self.frame_layout.addWidget(self.spinbox)

    def reload(self, keyboard):
        value = super().reload(keyboard)
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        self.spinbox.blockSignals(False)

    def value(self):
        return self.spinbox.value()

    def is_modified(self, current_full, committed_full):
        """Check if this value changed."""
        return current_full != committed_full

    def set_modified(self, modified):
        if modified:
            self.frame.setStyleSheet("#option_frame { border: 2px solid palette(link); }")
        else:
            self.frame.setStyleSheet("#option_frame { border: 2px solid transparent; }")


class QmkSettings(BasicEditor):

    def __init__(self):
        super().__init__()
        self.keyboard = None
        self.committed_settings = {}  # Track committed state

        self.tabs_widget = QTabWidget()
        self.addWidget(self.tabs_widget)

        self.tabs = []
        self.misc_widgets = []

    def populate_tab(self, tab, container):
        options = []
        for field in tab["fields"]:
            if field["qsid"] not in self.keyboard.supported_settings:
                continue
            if field["type"] == "boolean":
                opt = BooleanOption(field, container)
                options.append(opt)
                opt.changed.connect(self.on_change)
            elif field["type"] == "integer":
                opt = IntegerOption(field, container)
                options.append(opt)
                opt.changed.connect(self.on_change)
            else:
                raise RuntimeError("unsupported field type: {}".format(field))
        return options

    def recreate_gui(self):
        # delete old GUI
        for tab in self.tabs:
            for field in tab:
                field.delete()
        self.tabs.clear()
        for w in self.misc_widgets:
            w.hide()
            w.deleteLater()
        self.misc_widgets.clear()
        while self.tabs_widget.count() > 0:
            self.tabs_widget.removeTab(0)

        # create new GUI
        for tab in self.settings_defs["tabs"]:
            # don't bother creating tabs that would be empty - i.e. at least one qsid in a tab should be supported
            use_tab = False
            for field in tab["fields"]:
                if field["qsid"] in self.keyboard.supported_settings:
                    use_tab = True
                    break
            if not use_tab:
                continue

            w = QWidget()
            w.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
            container = QGridLayout()
            w.setLayout(container)
            l = QVBoxLayout()
            l.addWidget(w)
            l.setAlignment(w, QtCore.Qt.AlignHCenter)
            w2 = QWidget()
            w2.setLayout(l)
            self.misc_widgets += [w, w2]
            self.tabs_widget.addTab(w2, tab["name"])
            self.tabs.append(self.populate_tab(tab, container))

    def reload_settings(self):
        self.keyboard.reload_settings()
        self.recreate_gui()

        for tab in self.tabs:
            for field in tab:
                field.reload(self.keyboard)

        # Store committed state AFTER UI is populated (to account for clamping/normalization)
        # This ensures comparison uses the same values that the UI can represent
        self.committed_settings = dict(self.prepare_settings())

        # Just update UI state, don't track changes (this is initial load)
        self._update_ui_state()

    def on_change(self):
        qsid_values = self.prepare_settings()
        cm = ChangeManager.instance()

        # Track changes by comparing UI to current keyboard.settings
        for qsid, new_value in qsid_values.items():
            old_value = self.keyboard.settings.get(qsid, 0)

            # Only track if UI value actually changed from keyboard state
            if old_value != new_value:
                change = QmkSettingChange(qsid, old_value, new_value)
                cm.add_change(change)
                self.keyboard.settings[qsid] = new_value

        # Update visual state
        self._update_ui_state()

    def _update_ui_state(self):
        """Update UI highlights and button states without tracking changes."""
        qsid_values = self.prepare_settings()

        # Get link color for highlighting
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QPalette
        link_color = QApplication.palette().color(QPalette.Link)
        default_color = QApplication.palette().color(QPalette.WindowText)

        # In auto_commit mode, no highlighting (changes are immediately committed)
        cm = ChangeManager.instance()
        if cm.auto_commit:
            for x, tab in enumerate(self.tabs):
                for opt in tab:
                    if hasattr(opt, 'set_modified'):
                        opt.set_modified(False)
                self.tabs_widget.tabBar().setTabTextColor(x, default_color)
            self.tabs_widget.tabBar().update()
            return

        # Update tab titles and highlight individual changed widgets
        any_modified = False
        for x, tab in enumerate(self.tabs):
            tab_changed = False
            for opt in tab:
                # Compare current value to committed value (using option's is_modified for bit-level comparison)
                current = qsid_values.get(opt.qsid, 0)
                committed = self.committed_settings.get(opt.qsid, 0)

                # Use option's is_modified method if available (handles bitfields correctly)
                if hasattr(opt, 'is_modified'):
                    is_opt_modified = opt.is_modified(current, committed)
                else:
                    is_opt_modified = current != committed

                # Highlight the specific widget
                if hasattr(opt, 'set_modified'):
                    opt.set_modified(is_opt_modified)

                if is_opt_modified:
                    tab_changed = True
                    any_modified = True

            if tab_changed:
                self.tabs_widget.tabBar().setTabTextColor(x, link_color)
            else:
                self.tabs_widget.tabBar().setTabTextColor(x, default_color)

        # Force repaint
        self.tabs_widget.tabBar().update()


    def rebuild(self, device):
        super().rebuild(device)
        if self.valid():
            self.keyboard = device.keyboard
            # Connect to ChangeManager signals
            cm = ChangeManager.instance()
            try:
                cm.values_restored.disconnect(self._on_values_restored)
            except TypeError:
                pass
            try:
                cm.saved.disconnect(self._on_saved)
            except TypeError:
                pass
            cm.values_restored.connect(self._on_values_restored)
            cm.saved.connect(self._on_saved)
            try:
                cm.auto_commit_changed.disconnect(self._on_auto_commit_changed)
            except TypeError:
                pass
            cm.auto_commit_changed.connect(self._on_auto_commit_changed)
            self.reload_settings()

    def _on_values_restored(self, affected_keys):
        """Refresh UI when settings are restored by undo/redo."""
        affected_qsid = None
        for key in affected_keys:
            if key[0] == 'qmk_setting':
                affected_qsid = key[1]  # ('qmk_setting', qsid)
                break

        if affected_qsid is not None:
            # Reload UI from keyboard.settings
            for tab in self.tabs:
                for field in tab:
                    field.reload(self.keyboard)
            self._update_ui_state()

            # Switch to the tab containing the affected setting
            for tab_idx, tab in enumerate(self.tabs):
                for field in tab:
                    if field.qsid == affected_qsid:
                        self.tabs_widget.setCurrentIndex(tab_idx)
                        return

    def _on_saved(self):
        """Update committed state after global save."""
        # Use prepare_settings() to get normalized values matching what UI can represent
        self.committed_settings = dict(self.prepare_settings())
        self._update_ui_state()

    def _on_auto_commit_changed(self, auto_commit):
        """Update UI when auto_commit mode changes."""
        # Always sync committed state - when entering push mode changes become committed,
        # when leaving push mode the device already has current state
        self.committed_settings = dict(self.prepare_settings())
        self._update_ui_state()

    def prepare_settings(self):
        qsid_values = defaultdict(int)
        for tab in self.tabs:
            for field in tab:
                qsid_values[field.qsid] |= field.value()
        return qsid_values

    def valid(self):
        return isinstance(self.device, VialKeyboard) and \
               (self.device.keyboard and self.device.keyboard.vial_protocol >= VIAL_PROTOCOL_QMK_SETTINGS
                and len(self.device.keyboard.supported_settings))

    @classmethod
    def initialize(cls, appctx):
        cls.qsid_fields = defaultdict(list)
        with open(appctx.get_resource("qmk_settings.json"), "r") as inf:
            cls.settings_defs = json.load(inf)
        for tab in cls.settings_defs["tabs"]:
            for field in tab["fields"]:
                cls.qsid_fields[field["qsid"]].append(field)

    @classmethod
    def is_qsid_supported(cls, qsid):
        """ Return whether this qsid is supported by the settings editor """
        return qsid in cls.qsid_fields

    @classmethod
    def qsid_serialize(cls, qsid, data):
        """ Serialize from internal representation into binary that can be sent to the firmware """
        fields = cls.qsid_fields[qsid]
        if fields[0]["type"] == "boolean":
            assert isinstance(data, int)
            return data.to_bytes(fields[0].get("width", 1), byteorder="little")
        elif fields[0]["type"] == "integer":
            assert isinstance(data, int)
            assert len(fields) == 1
            return data.to_bytes(fields[0]["width"], byteorder="little")

    @classmethod
    def qsid_deserialize(cls, qsid, data):
        """ Deserialize from binary received from firmware into internal representation """
        fields = cls.qsid_fields[qsid]
        if fields[0]["type"] == "boolean":
            return int.from_bytes(data[0:fields[0].get("width", 1)], byteorder="little")
        elif fields[0]["type"] == "integer":
            assert len(fields) == 1
            return int.from_bytes(data[0:fields[0]["width"]], byteorder="little")
        else:
            raise RuntimeError("unsupported field")
