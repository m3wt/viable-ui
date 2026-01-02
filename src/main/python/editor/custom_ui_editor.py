# SPDX-License-Identifier: GPL-2.0-or-later
"""
Custom UI editor for VIA3 custom_ui definitions.

Displays keyboard-provided custom_ui settings using the CustomUIRenderer.
This handles keyboard-specific settings like layer colors, DPI, automouse, etc.
"""
from editor.basic_editor import BasicEditor
from ui.custom_ui_renderer import CustomUIRenderer
from vial_device import VialKeyboard


class CustomUIEditor(BasicEditor):
    """
    Editor that renders custom_ui definitions from the keyboard.

    The keyboard provides a custom_ui.json definition that describes
    what settings are available and how to render them.
    """

    def __init__(self):
        super().__init__()
        self.keyboard = None
        self.renderer = CustomUIRenderer()
        self.content_widget = None

    def valid(self):
        """Check if this editor is valid for the current device."""
        if not isinstance(self.device, VialKeyboard):
            return False
        if not self.device.keyboard:
            return False
        # Valid if keyboard has custom_ui definition
        return hasattr(self.device.keyboard, 'custom_ui') and self.device.keyboard.custom_ui

    def rebuild(self, device):
        """Rebuild the editor for a new device."""
        super().rebuild(device)

        # Clear existing content
        if self.content_widget:
            self.content_widget.hide()
            self.content_widget.deleteLater()
            self.content_widget = None

        # If not valid, tab won't be shown anyway - nothing to do
        if not self.valid():
            return

        self.keyboard = device.keyboard

        # Set up renderer with keyboard
        self.renderer.set_keyboard(self.keyboard)

        # Get custom_ui definition from keyboard
        custom_ui = self.keyboard.custom_ui

        # Render the UI
        self.content_widget = self.renderer.render(custom_ui)
        self.addWidget(self.content_widget)

        # Connect value changed signal
        self.renderer.value_changed.connect(self._on_value_changed)

    def _on_value_changed(self, channel: int, value_id: int, value: bytes):
        """Handle value changes from the renderer."""
        # The renderer already sends the value to the keyboard
        # This is for any additional handling (change tracking, etc.)
        pass

    def refresh_display(self):
        """Refresh the display."""
        if self.renderer:
            self.renderer.refresh_all()

    def _on_values_restored(self, affected_keys):
        """Handle undo/redo - refresh all values."""
        self.refresh_display()

    def _on_saved(self):
        """Handle save - refresh display."""
        self.refresh_display()
