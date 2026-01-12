# SPDX-License-Identifier: GPL-2.0-or-later
"""
Fragment selection editor for keyboards with fragment-based layouts.

Allows users to select which fragment is used for each selectable instance
position. Hardware detection is displayed but may be overridden by user selection.
"""

from qtpy import QtCore
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QLabel, QComboBox, QGridLayout, QWidget, QSizePolicy, QGroupBox, QVBoxLayout,
    QHBoxLayout, QFrame
)

from change_manager import ChangeManager
from change_manager.changes import FragmentSelectionChange
from editor.basic_editor import BasicEditor
from vial_device import VialKeyboard


class FragmentChoice:
    """Widget for selecting a fragment for an instance position."""

    def __init__(self, cb, container, instance_id, instance_idx, fragment_options,
                 current_fragment, hw_detected_fragment, allow_override,
                 instance_display_name, fragment_display_names, hw_detected_display_name):
        """
        Create a fragment selection widget.

        Args:
            cb: Callback when selection changes
            container: Parent grid layout
            instance_id: String ID of instance (e.g., "left_index")
            instance_idx: Numeric position in instances array (0-20)
            fragment_options: List of available fragment names (internal)
            current_fragment: Currently selected fragment name (internal)
            hw_detected_fragment: Fragment name detected by hardware (or None)
            allow_override: Whether user can override hardware detection
            instance_display_name: Human-readable name for instance position
            fragment_display_names: Dict mapping fragment name -> display name
            hw_detected_display_name: Display name for hw detected fragment (or None)
        """
        self.cb = cb
        self.instance_id = instance_id
        self.instance_idx = instance_idx
        self.fragment_options = fragment_options
        self.fragment_display_names = fragment_display_names
        self.hw_detected_fragment = hw_detected_fragment
        self.allow_override = allow_override
        self.current_fragment = current_fragment

        # Build reverse mapping: display name -> internal name
        self.display_to_internal = {v: k for k, v in fragment_display_names.items()}

        # Build label with hardware detection info
        label_text = instance_display_name
        if hw_detected_fragment:
            if allow_override:
                label_text += f" (detected: {hw_detected_display_name})"
            else:
                label_text += f" (locked: {hw_detected_display_name})"

        # Create container frame for highlighting
        self.widget_container = QFrame()
        self.widget_container.setObjectName("fragmentEntry")
        self.widget_container.setStyleSheet("#fragmentEntry { border: 2px solid transparent; }")
        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(4, 2, 4, 2)

        self.widget_label = QLabel(label_text)
        self.widget_options = QComboBox()

        # Add display names to dropdown
        display_names = [fragment_display_names.get(f, f) for f in fragment_options]
        self.widget_options.addItems(display_names)

        # Set current selection using display name
        if current_fragment in fragment_options:
            current_display = fragment_display_names.get(current_fragment, current_fragment)
            self.widget_options.setCurrentText(current_display)

        # Disable if hardware locked
        if hw_detected_fragment and not allow_override:
            self.widget_options.setEnabled(False)

        self.widget_options.currentTextChanged.connect(self.on_selection)

        container_layout.addWidget(self.widget_label)
        container_layout.addWidget(self.widget_options)
        container_layout.addStretch()
        self.widget_container.setLayout(container_layout)

        row = container.rowCount()
        container.addWidget(self.widget_container, row, 0, 1, 2)

    def delete(self):
        """Remove widgets from layout."""
        self.widget_container.hide()
        self.widget_container.deleteLater()

    def set_modified(self, modified):
        """Set visual indicator for uncommitted changes."""
        if modified:
            self.widget_container.setStyleSheet("#fragmentEntry { border: 2px solid palette(link); }")
        else:
            self.widget_container.setStyleSheet("#fragmentEntry { border: 2px solid transparent; }")

    def on_selection(self, display_text):
        """Handle user selection change."""
        # Convert display name back to internal name
        internal_name = self.display_to_internal.get(display_text, display_text)
        if internal_name != self.current_fragment:
            old_fragment = self.current_fragment
            self.current_fragment = internal_name
            self.cb(self.instance_id, self.instance_idx, old_fragment, internal_name)

    def set_selection(self, fragment_name):
        """Programmatically set selection (for undo/redo)."""
        self.widget_options.blockSignals(True)
        self.current_fragment = fragment_name
        if fragment_name in self.fragment_options:
            display_name = self.fragment_display_names.get(fragment_name, fragment_name)
            self.widget_options.setCurrentText(display_name)
        self.widget_options.blockSignals(False)


class FragmentEditor(BasicEditor):
    """Editor for fragment selections."""

    changed = Signal()
    CM_KEY_TYPE = 'fragment_selection'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device = self.keyboard = None
        self.choices = []  # List of FragmentChoice widgets

        self.addStretch()

        # Create container for fragment selections
        self.group = QGroupBox("Fragment Selections")
        group_layout = QVBoxLayout()

        self.container_widget = QWidget()
        self.container_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.container = QGridLayout()
        self.container_widget.setLayout(self.container)

        # Info label
        self.info_label = QLabel(
            "Select which physical component is installed at each position.\n"
            "Hardware-detected components are shown; some may be locked."
        )
        self.info_label.setWordWrap(True)

        group_layout.addWidget(self.info_label)
        group_layout.addWidget(self.container_widget)
        self.group.setLayout(group_layout)

        self.addWidget(self.group)
        self.setAlignment(self.group, QtCore.Qt.AlignHCenter)
        self.addStretch()

    def rebuild(self, device):
        """Rebuild the editor for a new device."""
        super().rebuild(device)

        if not self.valid():
            return

        self.keyboard = device.keyboard

        self.blockSignals(True)

        # Clear existing choices
        for choice in self.choices:
            choice.delete()
        self.choices = []

        composer = self.keyboard.fragment_composer

        # Get selectable instances
        for instance_idx, instance in composer.get_selectable_instances():
            instance_id = instance['id']
            fragment_options = composer.get_fragment_options(instance)

            # Get current selection (from keymap > EEPROM > hardware > default)
            current_fragment = self._get_current_fragment(instance_idx, instance, composer)

            # Get hardware detection for this instance
            hw_frag_id = self.keyboard.fragment_hw_detection.get(instance_idx, 0xFF)
            hw_detected_fragment = None
            hw_detected_display_name = None
            if hw_frag_id != 0xFF:
                hw_detected_fragment = composer.get_fragment_name(hw_frag_id)
                if hw_detected_fragment:
                    hw_detected_display_name = composer.get_fragment_display_name(hw_detected_fragment)

            allow_override = instance.get('allow_override', True)

            # Build display name mappings
            instance_display_name = composer.get_instance_display_name(instance_id)
            fragment_display_names = {
                f: composer.get_fragment_display_name(f) for f in fragment_options
            }

            choice = FragmentChoice(
                self.on_fragment_changed,
                self.container,
                instance_id,
                instance_idx,
                fragment_options,
                current_fragment,
                hw_detected_fragment,
                allow_override,
                instance_display_name,
                fragment_display_names,
                hw_detected_display_name
            )
            self.choices.append(choice)

        self.blockSignals(False)

    def _get_current_fragment(self, instance_idx, instance, composer):
        """Determine current fragment for an instance using same logic as keymap view."""
        # Use composer's resolve_instance for single source of truth
        frag_name, _, _, _ = composer.resolve_instance(
            instance_idx,
            instance,
            self.keyboard.fragment_hw_detection,
            self.keyboard.fragment_eeprom_selections,
            self.keyboard.fragment_selections
        )
        return frag_name

    def on_fragment_changed(self, instance_id, instance_idx, old_fragment, new_fragment):
        """Handle fragment selection change."""
        composer = self.keyboard.fragment_composer

        # Get instance to find option indices
        _, instance = composer.get_instance_by_id(instance_id)

        # Get option indices for EEPROM storage (not fragment IDs)
        old_opt_idx = composer.get_option_index(instance, old_fragment) if old_fragment else 0xFF
        new_opt_idx = composer.get_option_index(instance, new_fragment)

        # Create change for undo/redo
        change = FragmentSelectionChange(
            instance_id=instance_id,
            instance_idx=instance_idx,
            old_fragment=old_fragment,
            new_fragment=new_fragment,
            old_fragment_id=old_opt_idx,
            new_fragment_id=new_opt_idx
        )

        # Update local state
        self.keyboard.fragment_selections[instance_id] = new_fragment

        # Recompose keyboard keys with new fragment selection
        self.keyboard.recompose_fragments()

        # Record change
        ChangeManager.instance().add_change(change)

        # Update highlight immediately
        self.refresh_display()

        self.changed.emit()

    def valid(self):
        """Check if this editor should be shown."""
        if not isinstance(self.device, VialKeyboard):
            return False
        keyboard = self.device.keyboard
        if not keyboard.fragment_composer:
            return False
        # Only show if there are selectable instances
        return bool(keyboard.fragment_composer.get_selectable_instances())

    def _reload_entry(self, instance_id):
        """Reload a specific entry after undo/redo."""
        for choice in self.choices:
            if choice.instance_id == instance_id:
                # Get updated fragment from keyboard state
                frag = self.keyboard.fragment_selections.get(instance_id)
                if frag:
                    choice.set_selection(frag)
                break

    def refresh_display(self):
        """Refresh display after save or undo/redo."""
        cm = ChangeManager.instance()

        # Update all choices to reflect current state and highlight modified ones
        for choice in self.choices:
            frag = self.keyboard.fragment_selections.get(choice.instance_id)
            if frag:
                choice.set_selection(frag)
            # Update modified indicator
            choice.set_modified(cm.is_modified(('fragment_selection', choice.instance_id)))
