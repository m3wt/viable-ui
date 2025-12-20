# SPDX-License-Identifier: GPL-2.0-or-later
import struct

from protocol.base_protocol import BaseProtocol
from protocol.constants import (SVAL_VIA_PREFIX, SVAL_GET_PROTOCOL_VERSION,
                                 SVAL_GET_LAYER_HSV, SVAL_SET_LAYER_HSV,
                                 SVAL_GET_LAYER_COUNT, SVAL_GET_SETTINGS,
                                 SVAL_SET_SETTINGS, SVAL_GET_DPI_LEVELS,
                                 SVAL_GET_MH_TIMERS)


class ProtocolSvalboard(BaseProtocol):
    """Protocol mixin for Svalboard-specific features"""

    # Capability flag
    is_svalboard = False
    sval_protocol_version = 0
    sval_layer_count = 0

    # State
    sval_layer_colors = None  # List of (h, s, v) tuples
    sval_settings = None      # Dict with all settings
    sval_dpi_levels = None    # List of DPI values from firmware
    sval_mh_timers = None     # List of mouse layer timeout values from firmware
    sval_turbo_scan_limit = None  # Number of turbo scan levels from firmware

    def reload_svalboard(self):
        """Check if svalboard and load settings"""
        self.is_svalboard = False
        self.sval_protocol_version = 0
        self.sval_layer_count = 0
        self.sval_layer_colors = None
        self.sval_settings = None
        self.sval_dpi_levels = None
        self.sval_mh_timers = None
        self.sval_turbo_scan_limit = None

        try:
            data = self.usb_send(
                self.dev,
                struct.pack("BB", SVAL_VIA_PREFIX, SVAL_GET_PROTOCOL_VERSION),
                retries=5
            )
            # Response: 'sval' + 4-byte version (little-endian)
            if data[0:4] == b'sval':
                self.is_svalboard = True
                self.sval_protocol_version = struct.unpack("<I", data[4:8])[0]
            else:
                return
        except Exception:
            return

        # Get layer count
        self._load_layer_count()
        # Load DPI levels from firmware
        self._load_dpi_levels()
        # Load mouse layer timeout options from firmware
        self._load_mh_timers()
        # Load current state
        self._load_layer_colors()
        self._load_settings()

    def _load_layer_count(self):
        """Get the number of layers from keyboard"""
        data = self.usb_send(
            self.dev,
            struct.pack("BB", SVAL_VIA_PREFIX, SVAL_GET_LAYER_COUNT),
            retries=20
        )
        self.sval_layer_count = data[0]

    def _load_dpi_levels(self):
        """Get the DPI levels table from keyboard"""
        data = self.usb_send(
            self.dev,
            struct.pack("BB", SVAL_VIA_PREFIX, SVAL_GET_DPI_LEVELS),
            retries=20
        )
        count = data[0]
        self.sval_dpi_levels = []
        for i in range(count):
            # DPI values are 2 bytes each, little-endian
            dpi = data[1 + i * 2] | (data[2 + i * 2] << 8)
            self.sval_dpi_levels.append(dpi)

    def _load_mh_timers(self):
        """Get the mouse layer timeout options from keyboard"""
        data = self.usb_send(
            self.dev,
            struct.pack("BB", SVAL_VIA_PREFIX, SVAL_GET_MH_TIMERS),
            retries=20
        )
        count = data[0]
        self.sval_mh_timers = []
        for i in range(count):
            # Timer values are signed 2 bytes each, little-endian
            raw = data[1 + i * 2] | (data[2 + i * 2] << 8)
            # Convert to signed int16
            if raw >= 0x8000:
                raw -= 0x10000
            self.sval_mh_timers.append(raw)

    def _load_layer_colors(self):
        """Load all layer colors"""
        self.sval_layer_colors = []
        for layer in range(self.sval_layer_count):
            data = self.usb_send(
                self.dev,
                struct.pack("BBB", SVAL_VIA_PREFIX, SVAL_GET_LAYER_HSV, layer),
                retries=20
            )
            self.sval_layer_colors.append((data[0], data[1], data[2]))

    def _load_settings(self):
        """Load all settings"""
        data = self.usb_send(
            self.dev,
            struct.pack("BB", SVAL_VIA_PREFIX, SVAL_GET_SETTINGS),
            retries=20
        )
        self.sval_settings = {
            'left_dpi_index': data[0],
            'right_dpi_index': data[1],
            'left_scroll': bool(data[2]),
            'right_scroll': bool(data[3]),
            'axis_scroll_lock': bool(data[4]),
            'auto_mouse': bool(data[5]),
            'mh_timer_index': data[6],
            'turbo_scan': data[7],
        }
        self.sval_turbo_scan_limit = data[8]

    def sval_set_layer_color(self, layer, h, s, v):
        """Set color for a layer"""
        self.usb_send(
            self.dev,
            struct.pack("BBBBBB", SVAL_VIA_PREFIX, SVAL_SET_LAYER_HSV,
                        layer, h, s, v),
            retries=20
        )
        self.sval_layer_colors[layer] = (h, s, v)

    def sval_set_settings(self, settings):
        """Set all settings"""
        self.usb_send(
            self.dev,
            struct.pack("BBBBBBBBBB", SVAL_VIA_PREFIX, SVAL_SET_SETTINGS,
                        settings['left_dpi_index'],
                        settings['right_dpi_index'],
                        int(settings['left_scroll']),
                        int(settings['right_scroll']),
                        int(settings['axis_scroll_lock']),
                        int(settings['auto_mouse']),
                        settings['mh_timer_index'],
                        settings['turbo_scan']),
            retries=20
        )
        self.sval_settings = settings.copy()

    def sval_reload_settings(self):
        """Reload just settings (not layer colors)"""
        if self.is_svalboard:
            self._load_settings()

    def sval_reload_layer_colors(self):
        """Reload just layer colors"""
        if self.is_svalboard:
            self._load_layer_colors()
