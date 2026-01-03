# SPDX-License-Identifier: GPL-2.0-or-later
import struct

from protocol.base_protocol import BaseProtocol
from protocol.constants import CMD_VIA_CUSTOM_GET_VALUE, CMD_VIA_CUSTOM_SET_VALUE

# VIA custom value IDs for Svalboard (must match firmware)
SVAL_ID_LEFT_DPI = 0
SVAL_ID_LEFT_SCROLL = 1
SVAL_ID_RIGHT_DPI = 2
SVAL_ID_RIGHT_SCROLL = 3
SVAL_ID_AUTOMOUSE_ENABLE = 4
SVAL_ID_NATURAL_SCROLL = 7
SVAL_ID_AXIS_LOCK = 8
SVAL_ID_LAYER0_COLOR = 32
SVAL_ID_CURRENT_LAYER = 48


class ProtocolSvalboard(BaseProtocol):
    """Protocol mixin for Svalboard-specific features using VIA custom values"""

    # Capability flag - determined from keyboard JSON menus
    is_svalboard = False
    sval_layer_count = 0

    # State
    sval_layer_colors = None  # List of (h, s) tuples
    sval_settings = None      # Dict with all settings

    # Configuration (hardcoded for now, could come from firmware)
    sval_dpi_levels = [400, 800, 1200, 1600, 2000, 2400, 3200, 4000]
    sval_mh_timers = [100, 200, 300, 500, 750, 1000, 1500, 2000, -1]  # -1 = infinite
    sval_turbo_scan_limit = 10

    def reload_svalboard(self):
        """Check if svalboard (from JSON menus) and load settings via VIA protocol"""
        self.is_svalboard = False
        self.sval_layer_count = 0
        self.sval_layer_colors = None
        self.sval_settings = None

        # Detect Svalboard from keyboard definition menus
        if not hasattr(self, 'definition') or not self.definition:
            return

        menus = self.definition.get('menus', [])
        has_layer_colors = False
        for menu in menus:
            if menu.get('label') == 'Layer Colors':
                has_layer_colors = True
                break

        if not has_layer_colors:
            return

        self.is_svalboard = True
        self.sval_layer_count = self.layers  # Use keymap layer count

        # Load current state via VIA custom values
        self._load_layer_colors()
        self._load_settings()

    def _via_get_value(self, value_id):
        """Get a custom keyboard value via VIA protocol.

        Returns data bytes on success, or None if firmware doesn't support this value.
        """
        # VIA custom value format: [command, channel, value_id]
        # Channel 0 = keyboard-level custom values
        data = self.via_send(
            struct.pack("BBB", CMD_VIA_CUSTOM_GET_VALUE, 0, value_id),
            retries=20
        )
        # Check for error response (0xFF instead of echoed command)
        if data[0] == 0xFF:
            return None
        return data[3:]  # Skip command echo, channel, and value_id

    def _via_set_value(self, value_id, *values):
        """Set a custom keyboard value via VIA protocol"""
        # VIA custom value format: [command, channel, value_id, value_data...]
        # Channel 0 = keyboard-level custom values
        msg = struct.pack("BBB", CMD_VIA_CUSTOM_SET_VALUE, 0, value_id) + bytes(values)
        self.via_send(msg, retries=20)

    def _load_layer_colors(self):
        """Load all layer colors via VIA custom values"""
        self.sval_layer_colors = []
        for layer in range(min(self.sval_layer_count, 16)):
            data = self._via_get_value(SVAL_ID_LAYER0_COLOR + layer)
            if data is None:
                # Firmware doesn't support custom values - use default colors
                # Spread hues across layers for visual distinction
                default_hue = (layer * 20) % 256
                self.sval_layer_colors.append((default_hue, 255))
            else:
                # VIA color returns H, S (2 bytes)
                self.sval_layer_colors.append((data[0], data[1]))

    def _load_settings(self):
        """Load settings via individual VIA custom value gets"""

        def get_u16(value_id, default=0):
            data = self._via_get_value(value_id)
            if data is None or len(data) < 2:
                return default
            return data[0] | (data[1] << 8)

        def get_bool(value_id, default=False):
            data = self._via_get_value(value_id)
            if data is None or len(data) < 1:
                return default
            return bool(data[0])

        self.sval_settings = {
            'left_dpi': get_u16(SVAL_ID_LEFT_DPI, 800),
            'right_dpi': get_u16(SVAL_ID_RIGHT_DPI, 800),
            'left_scroll': get_bool(SVAL_ID_LEFT_SCROLL),
            'right_scroll': get_bool(SVAL_ID_RIGHT_SCROLL),
            'axis_scroll_lock': get_bool(SVAL_ID_AXIS_LOCK),
            'auto_mouse': get_bool(SVAL_ID_AUTOMOUSE_ENABLE),
            'natural_scroll': get_bool(SVAL_ID_NATURAL_SCROLL),
        }

    def sval_set_layer_color(self, layer, h, s):
        """Set color for a layer (H, S only)"""
        self._via_set_value(SVAL_ID_LAYER0_COLOR + layer, h, s)
        self.sval_layer_colors[layer] = (h, s)

    def _commit_svalboard_layer_color(self, layer, hs):
        """Send a layer color change to the device (used by ChangeManager)."""
        h, s = hs
        self._via_set_value(SVAL_ID_LAYER0_COLOR + layer, h, s)
        self.sval_layer_colors[layer] = (h, s)
        return True

    def sval_set_setting(self, setting_name, value):
        """Set a single setting"""
        id_map = {
            'left_dpi': SVAL_ID_LEFT_DPI,
            'right_dpi': SVAL_ID_RIGHT_DPI,
            'left_scroll': SVAL_ID_LEFT_SCROLL,
            'right_scroll': SVAL_ID_RIGHT_SCROLL,
            'axis_scroll_lock': SVAL_ID_AXIS_LOCK,
            'auto_mouse': SVAL_ID_AUTOMOUSE_ENABLE,
            'natural_scroll': SVAL_ID_NATURAL_SCROLL,
        }
        value_id = id_map.get(setting_name)
        if value_id is None:
            return

        if setting_name in ('left_dpi', 'right_dpi'):
            # DPI is 2 bytes little-endian
            self._via_set_value(value_id, value & 0xFF, (value >> 8) & 0xFF)
        else:
            # Boolean settings
            self._via_set_value(value_id, int(value))

        self.sval_settings[setting_name] = value

    def _commit_svalboard_settings(self, settings):
        """Send all settings to the device (used by ChangeManager)."""
        for key, value in settings.items():
            self.sval_set_setting(key, value)
        return True

    def sval_reload_settings(self):
        """Reload settings"""
        if self.is_svalboard:
            self._load_settings()

    def sval_reload_layer_colors(self):
        """Reload layer colors"""
        if self.is_svalboard:
            self._load_layer_colors()

    def sval_get_current_layer(self):
        """Get the currently active layer from the keyboard"""
        if not self.is_svalboard:
            return None
        try:
            data = self._via_get_value(SVAL_ID_CURRENT_LAYER)
            return data[0]
        except Exception:
            return None
