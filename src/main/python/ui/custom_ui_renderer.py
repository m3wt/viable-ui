# SPDX-License-Identifier: GPL-2.0-or-later
"""
VIA3 custom_ui renderer.

Renders Qt widgets from VIA3 custom_ui.json definitions received from keyboard.
Supports all VIA3 control types: button, toggle, range, dropdown, color, keycode.

See https://caniusevia.com/docs/custom_ui for specification.
"""
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from qtpy.QtCore import Qt, Signal, QObject
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QCheckBox, QPushButton, QSlider, QSpinBox, QComboBox,
    QGroupBox, QTabWidget, QScrollArea, QSizePolicy, QColorDialog,
    QFrame
)
from qtpy.QtGui import QColor

from change_manager import ChangeManager, CustomValueChange
from ui.common_menus import resolve_common_menu


class CustomUIValue:
    """Represents a custom UI value with its current state."""

    def __init__(self, channel: int, value_id: int, size: int = 1):
        self.channel = channel
        self.value_id = value_id
        self.size = size  # in bytes
        self.value = 0
        self.indices: List[int] = []  # for array access

    def key(self) -> Tuple:
        """Return a unique key for this value."""
        return (self.channel, self.value_id, tuple(self.indices))


class CustomUIRenderer(QObject):
    """
    Renders VIA3 custom_ui definitions to Qt widgets.

    Usage:
        renderer = CustomUIRenderer(keyboard)
        widget = renderer.render(custom_ui_definition)
    """

    value_changed = Signal(int, int, bytes)  # channel, value_id, value

    def __init__(self, keyboard=None):
        super().__init__()
        self.keyboard = keyboard
        self.values: Dict[str, CustomUIValue] = {}  # id -> value
        self.widgets: Dict[str, QWidget] = {}  # id -> widget
        self.widget_updaters: Dict[str, Callable] = {}  # id -> update function
        self.widget_frames: Dict[str, QFrame] = {}  # id -> frame for highlighting
        self.show_if_widgets: List[Tuple[str, QWidget]] = []  # (expr, widget)

    def set_keyboard(self, keyboard):
        """Set the keyboard for value get/set operations."""
        self.keyboard = keyboard

    def render(self, definition: dict) -> QWidget:
        """
        Render a custom_ui definition to a Qt widget.

        Args:
            definition: VIA3 custom_ui definition dict

        Returns:
            QWidget containing the rendered UI
        """
        self.values.clear()
        self.widgets.clear()
        self.widget_updaters.clear()
        self.widget_frames.clear()
        self.show_if_widgets.clear()

        menus = definition.get("menus", [])
        if not menus:
            return QWidget()

        # Multiple top-level menus -> tabs
        if len(menus) > 1:
            return self._render_tabbed_menus(menus)
        else:
            # Single menu -> scroll area with groupboxes
            return self._render_single_menu(menus[0])

    def _render_tabbed_menus(self, menus: List[dict]) -> QWidget:
        """Render multiple menus as tabs."""
        tab_widget = QTabWidget()

        for menu in menus:
            if isinstance(menu, str):
                # String reference to common menu - resolve it
                menu = self._resolve_common_menu(menu)
                if menu is None:
                    continue

            label = menu.get("label", "Settings")
            content = self._render_menu_content(menu)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content)

            tab_widget.addTab(scroll, label)

        return tab_widget

    def _render_single_menu(self, menu: dict) -> QWidget:
        """Render a single menu as a scroll area."""
        if isinstance(menu, str):
            menu = self._resolve_common_menu(menu)
            if menu is None:
                return QWidget()

        content = self._render_menu_content(menu)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        return scroll

    def _render_menu_content(self, menu: dict) -> QWidget:
        """Render the content of a menu (sections)."""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        content = menu.get("content", [])
        for item in content:
            section_widget = self._render_section(item)
            if section_widget:
                layout.addWidget(section_widget)

        layout.addStretch()
        return widget

    def _render_section(self, section: dict) -> Optional[QWidget]:
        """Render a section (groupbox with controls) or a direct control."""
        if not isinstance(section, dict):
            return None

        # If item has a "type", it's a control, not a section
        if section.get("type"):
            return self._render_control(section)

        label = section.get("label", "")
        show_if = section.get("showIf")
        content = section.get("content", [])

        # If content is not a list of dicts (e.g., it's ["id", channel, value_id]),
        # this is malformed - skip it
        if content and not isinstance(content[0], dict):
            return None

        group = QGroupBox(label)
        layout = QVBoxLayout()
        group.setLayout(layout)

        for item in content:
            control_widget = self._render_section(item)  # Recursively handle nested sections/controls
            if control_widget:
                layout.addWidget(control_widget)

        if show_if:
            self.show_if_widgets.append((show_if, group))
            self._evaluate_show_if(show_if, group)

        return group

    def _render_control(self, control: dict) -> Optional[QWidget]:
        """Render a single control."""
        # Handle non-dict items (e.g., string menu references)
        if not isinstance(control, dict):
            return None

        control_type = control.get("type")
        label = control.get("label", "")
        show_if = control.get("showIf")
        content = control.get("content", [])

        # Handle showIf wrapper without type - it's a conditional group
        if show_if and not control_type and content:
            container = QWidget()
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(layout)

            for item in content:
                widget = self._render_control(item)
                if widget:
                    layout.addWidget(widget)

            self.show_if_widgets.append((show_if, container))
            self._evaluate_show_if(show_if, container)
            return container

        # Parse content: [id, channel, value_id, ...indices]
        value_key = content[0] if content else None
        channel = content[1] if len(content) > 1 else 0
        value_id = content[2] if len(content) > 2 else 0
        indices = content[3:] if len(content) > 3 else []

        widget = None

        if control_type == "toggle":
            widget = self._render_toggle(label, channel, value_id, value_key, control)
        elif control_type == "range":
            widget = self._render_range(label, channel, value_id, value_key, control)
        elif control_type == "dropdown":
            widget = self._render_dropdown(label, channel, value_id, value_key, control)
        elif control_type == "button":
            widget = self._render_button(label, channel, value_id, value_key, control)
        elif control_type == "color":
            widget = self._render_color(label, channel, value_id, value_key, control)
        elif control_type == "keycode":
            widget = self._render_keycode(label, channel, value_id, value_key, control)

        if widget and show_if:
            self.show_if_widgets.append((show_if, widget))
            self._evaluate_show_if(show_if, widget)

        if widget and value_key:
            self.widgets[value_key] = widget

        return widget

    def _render_toggle(self, label: str, channel: int, value_id: int,
                       value_key: str, control: dict) -> QWidget:
        """Render a toggle (checkbox) control."""
        frame = QFrame()
        frame.setObjectName("custom_ui_frame")
        frame.setStyleSheet("#custom_ui_frame { border: 2px solid transparent; }")
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        frame.setLayout(layout)

        lbl = QLabel(label)
        checkbox = QCheckBox()

        options = control.get("options", [0, 1])
        off_value = options[0] if len(options) > 0 else 0
        on_value = options[1] if len(options) > 1 else 1

        # Load current value
        current = self._get_value(channel, value_id)
        checkbox.setChecked(current == on_value)

        def on_change(state):
            value = on_value if state == Qt.Checked else off_value
            self._set_value(channel, value_id, value, 1)

        checkbox.stateChanged.connect(on_change)

        # Register updater for refresh
        def update_checkbox(value):
            checkbox.blockSignals(True)
            checkbox.setChecked(value == on_value)
            checkbox.blockSignals(False)

        if value_key:
            self.widget_updaters[value_key] = update_checkbox
            self.widget_frames[value_key] = frame

        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(checkbox)

        # Store value reference
        self._register_value(value_key, channel, value_id, 1)

        return frame

    def _render_range(self, label: str, channel: int, value_id: int,
                      value_key: str, control: dict) -> QWidget:
        """Render a range (slider + spinbox) control."""
        frame = QFrame()
        frame.setObjectName("custom_ui_frame")
        frame.setStyleSheet("#custom_ui_frame { border: 2px solid transparent; }")
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        frame.setLayout(layout)

        lbl = QLabel(label)
        slider = QSlider(Qt.Horizontal)
        spinbox = QSpinBox()

        options = control.get("options", [0, 255])
        min_val = options[0] if len(options) > 0 else 0
        max_val = options[1] if len(options) > 1 else 255

        # Determine byte size
        size = 2 if max_val > 255 else 1

        slider.setRange(min_val, max_val)
        spinbox.setRange(min_val, max_val)

        # Load current value
        current = self._get_value(channel, value_id, size)
        slider.setValue(current)
        spinbox.setValue(current)

        # Sync slider and spinbox
        def on_slider_change(value):
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)
            self._set_value(channel, value_id, value, size)

        def on_spinbox_change(value):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            self._set_value(channel, value_id, value, size)

        slider.valueChanged.connect(on_slider_change)
        spinbox.valueChanged.connect(on_spinbox_change)

        # Register updater for refresh
        def update_range(value):
            slider.blockSignals(True)
            spinbox.blockSignals(True)
            slider.setValue(value)
            spinbox.setValue(value)
            slider.blockSignals(False)
            spinbox.blockSignals(False)

        if value_key:
            self.widget_updaters[value_key] = update_range
            self.widget_frames[value_key] = frame

        layout.addWidget(lbl)
        layout.addWidget(slider, stretch=1)
        layout.addWidget(spinbox)

        # Store value reference
        self._register_value(value_key, channel, value_id, size)

        return frame

    def _render_dropdown(self, label: str, channel: int, value_id: int,
                         value_key: str, control: dict) -> QWidget:
        """Render a dropdown (combobox) control."""
        frame = QFrame()
        frame.setObjectName("custom_ui_frame")
        frame.setStyleSheet("#custom_ui_frame { border: 2px solid transparent; }")
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        frame.setLayout(layout)

        lbl = QLabel(label)
        combo = QComboBox()

        options = control.get("options", [])
        for i, opt in enumerate(options):
            if isinstance(opt, str):
                combo.addItem(opt, i)
            elif isinstance(opt, list) and len(opt) >= 2:
                combo.addItem(opt[0], opt[1])

        # Load current value
        current = self._get_value(channel, value_id)
        for i in range(combo.count()):
            if combo.itemData(i) == current:
                combo.setCurrentIndex(i)
                break

        def on_change(index):
            value = combo.itemData(index)
            self._set_value(channel, value_id, value, 1)

        combo.currentIndexChanged.connect(on_change)

        # Register updater for refresh
        def update_dropdown(value):
            combo.blockSignals(True)
            for i in range(combo.count()):
                if combo.itemData(i) == value:
                    combo.setCurrentIndex(i)
                    break
            combo.blockSignals(False)

        if value_key:
            self.widget_updaters[value_key] = update_dropdown
            self.widget_frames[value_key] = frame

        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(combo)

        # Store value reference
        self._register_value(value_key, channel, value_id, 1)

        return frame

    def _render_button(self, label: str, channel: int, value_id: int,
                       value_key: str, control: dict) -> QWidget:
        """Render a button control."""
        frame = QFrame()
        frame.setObjectName("custom_ui_frame")
        frame.setStyleSheet("#custom_ui_frame { border: 2px solid transparent; }")
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        frame.setLayout(layout)

        button = QPushButton(label)

        options = control.get("options", [1])
        send_value = options[0] if options else 1

        def on_click():
            self._set_value(channel, value_id, send_value, 1)

        button.clicked.connect(on_click)

        layout.addStretch()
        layout.addWidget(button)
        layout.addStretch()

        return frame

    def _render_color(self, label: str, channel: int, value_id: int,
                      value_key: str, control: dict) -> QWidget:
        """Render a color picker control (HSV, 2 bytes)."""
        frame = QFrame()
        frame.setObjectName("custom_ui_frame")
        frame.setStyleSheet("#custom_ui_frame { border: 2px solid transparent; }")
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        frame.setLayout(layout)

        lbl = QLabel(label)
        color_button = QPushButton()
        color_button.setFixedSize(40, 24)

        # Store current HS values in a mutable container for closures
        hs_state = [0, 0]  # [hue, sat]

        # Load current HSV value (hue + sat packed in 2 bytes)
        current = self._get_value(channel, value_id, 2)
        hs_state[0] = current & 0xFF
        hs_state[1] = (current >> 8) & 0xFF

        def update_button_color():
            color = QColor.fromHsv(int(hs_state[0] * 360 / 255), int(hs_state[1] * 255 / 255), 255)
            color_button.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid gray;"
            )

        update_button_color()

        def on_click():
            initial = QColor.fromHsv(int(hs_state[0] * 360 / 255), int(hs_state[1] * 255 / 255), 255)
            color = QColorDialog.getColor(initial, None, "Select Color")
            if color.isValid():
                h, s, v, _ = color.getHsv()
                hs_state[0] = int(h * 255 / 360)
                hs_state[1] = int(s * 255 / 255)
                value = hs_state[0] | (hs_state[1] << 8)
                self._set_value(channel, value_id, value, 2)
                update_button_color()

        color_button.clicked.connect(on_click)

        # Register updater for refresh
        def update_color(value):
            hs_state[0] = value & 0xFF
            hs_state[1] = (value >> 8) & 0xFF
            update_button_color()

        if value_key:
            self.widget_updaters[value_key] = update_color
            self.widget_frames[value_key] = frame

        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(color_button)

        # Store value reference
        self._register_value(value_key, channel, value_id, 2)

        return frame

    def _render_keycode(self, label: str, channel: int, value_id: int,
                        value_key: str, control: dict) -> QWidget:
        """Render a keycode selector control."""
        # TODO: Integrate with existing KeyWidget from vial-gui
        # For now, render as a spinbox with keycode value
        frame = QFrame()
        frame.setObjectName("custom_ui_frame")
        frame.setStyleSheet("#custom_ui_frame { border: 2px solid transparent; }")
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        frame.setLayout(layout)

        lbl = QLabel(label)
        spinbox = QSpinBox()
        spinbox.setRange(0, 0xFFFF)
        spinbox.setDisplayIntegerBase(16)
        spinbox.setPrefix("0x")

        # Load current value
        current = self._get_value(channel, value_id, 2)
        spinbox.setValue(current)

        def on_change(value):
            self._set_value(channel, value_id, value, 2)

        spinbox.valueChanged.connect(on_change)

        # Register updater for refresh
        def update_keycode(value):
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)

        if value_key:
            self.widget_updaters[value_key] = update_keycode
            self.widget_frames[value_key] = frame

        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(spinbox)

        # Store value reference
        self._register_value(value_key, channel, value_id, 2)

        return frame

    def _register_value(self, key: str, channel: int, value_id: int, size: int):
        """Register a value for tracking."""
        if key:
            value = CustomUIValue(channel, value_id, size)
            self.values[key] = value

    def _get_value(self, channel: int, value_id: int, size: int = 1) -> int:
        """Get a value from the keyboard (uses local cache if available)."""
        if self.keyboard is None:
            return 0

        # Check local cache first
        if hasattr(self.keyboard, 'custom_values'):
            cached = self.keyboard.custom_values.get((channel, value_id))
            if cached is not None:
                if size == 1:
                    return cached[0] if cached else 0
                elif size == 2:
                    return int.from_bytes(cached[:2], 'little') if len(cached) >= 2 else 0
                return 0

        # Fetch from keyboard and cache
        try:
            data = self.keyboard.custom_value_get(channel, value_id)
            # Cache the result
            if not hasattr(self.keyboard, 'custom_values'):
                self.keyboard.custom_values = {}
            self.keyboard.custom_values[(channel, value_id)] = data

            if size == 1:
                return data[0] if data else 0
            elif size == 2:
                return int.from_bytes(data[:2], 'little') if len(data) >= 2 else 0
            return 0
        except Exception as e:
            import logging
            logging.error(f"custom_value_get({channel}, {value_id}) failed: {e}")
            return 0

    def _set_value(self, channel: int, value_id: int, value: int, size: int):
        """Set a value on the keyboard via ChangeManager."""
        new_data = value.to_bytes(size, 'little')

        # Get current value from local cache for change tracking
        old_data = bytes(size)
        if self.keyboard:
            if hasattr(self.keyboard, 'custom_values'):
                cached = self.keyboard.custom_values.get((channel, value_id))
                if cached is not None:
                    old_data = cached[:size] if len(cached) >= size else cached + bytes(size - len(cached))
            else:
                # No cache yet, fetch from keyboard
                try:
                    old_data = self.keyboard.custom_value_get(channel, value_id)
                    if len(old_data) < size:
                        old_data = old_data + bytes(size - len(old_data))
                    else:
                        old_data = old_data[:size]
                except Exception:
                    pass

        # Don't record if value unchanged
        if old_data == new_data:
            return

        # Record change via ChangeManager
        cm = ChangeManager.instance()
        change = CustomValueChange(channel, value_id, old_data, new_data)
        cm.add_change(change)

        # Update local cache
        if self.keyboard:
            if not hasattr(self.keyboard, 'custom_values'):
                self.keyboard.custom_values = {}
            self.keyboard.custom_values[(channel, value_id)] = new_data

        self.value_changed.emit(channel, value_id, new_data)

        # Re-evaluate showIf expressions and update highlights
        self._reevaluate_show_ifs()
        self.refresh_highlights()

    def _reevaluate_show_ifs(self):
        """Re-evaluate all showIf expressions."""
        for expr, widget in self.show_if_widgets:
            self._evaluate_show_if(expr, widget)

    def _evaluate_show_if(self, expression: str, widget: QWidget):
        """Evaluate a showIf expression and show/hide widget."""
        try:
            result = self._parse_show_if(expression)
            widget.setVisible(result)
        except Exception:
            widget.setVisible(True)

    def _parse_show_if(self, expression: str) -> bool:
        """
        Parse and evaluate a showIf expression.

        Supports:
        - Value refs: {id_xxx}, {id_xxx.N}
        - Operators: ==, !=, <, <=, >, >=, ||, &&, !
        - Parentheses: ()
        """
        # Replace value references with actual values
        def replace_ref(match):
            ref = match.group(1)
            parts = ref.split('.')
            value_key = parts[0]
            index = int(parts[1]) if len(parts) > 1 else None

            if value_key in self.values:
                val = self.values[value_key]
                current = self._get_value(val.channel, val.value_id, val.size)
                if index is not None:
                    # Array access - return specific byte
                    if index < val.size:
                        return str((current >> (index * 8)) & 0xFF)
                return str(current)
            return "0"

        # Replace {id_xxx} and {id_xxx.N} patterns
        expr = re.sub(r'\{([^}]+)\}', replace_ref, expression)

        # Replace operators with Python equivalents
        expr = expr.replace('||', ' or ')
        expr = expr.replace('&&', ' and ')
        expr = expr.replace('!', ' not ')

        # Evaluate safely
        try:
            # Only allow safe operations
            allowed = {'True', 'False', 'and', 'or', 'not'}
            for token in re.findall(r'[a-zA-Z_]+', expr):
                if token not in allowed:
                    return True  # Default to visible on parse error

            return bool(eval(expr))
        except Exception:
            return True

    def _resolve_common_menu(self, menu_name: str) -> Optional[dict]:
        """
        Resolve a common menu reference.

        Common menus are bundled definitions for standard QMK features:
        - qmk_backlight
        - qmk_rgblight
        - qmk_rgb_matrix
        - qmk_audio
        - qmk_led_matrix
        - qmk_backlight_rgblight
        """
        return resolve_common_menu(menu_name)

    def refresh_all(self):
        """Refresh all values from local cache and update widgets."""
        for key, val in self.values.items():
            current = self._get_value(val.channel, val.value_id, val.size)
            val.value = current
            # Update widget display
            if key in self.widget_updaters:
                self.widget_updaters[key](current)

        self._reevaluate_show_ifs()
        self.refresh_highlights()

    def refresh_highlights(self):
        """Update border highlights based on pending changes."""
        cm = ChangeManager.instance()

        for key, val in self.values.items():
            frame = self.widget_frames.get(key)
            if frame is None:
                continue

            # Build the change key
            change_key = ('custom_value', val.channel, val.value_id)
            is_modified = cm.is_modified(change_key)

            if is_modified:
                frame.setStyleSheet("#custom_ui_frame { border: 2px solid palette(link); }")
            else:
                frame.setStyleSheet("#custom_ui_frame { border: 2px solid transparent; }")
