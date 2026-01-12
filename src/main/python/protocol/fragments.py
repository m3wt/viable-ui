# SPDX-License-Identifier: GPL-2.0-or-later
"""
Protocol mixin for fragment hardware detection and EEPROM selection storage.

This mixin adds fragment-related protocol commands (0x18, 0x19, 0x1A) to the
Keyboard class for:
- Hardware detection of attached fragment modules
- Reading fragment selections from EEPROM
- Writing fragment selections to EEPROM
"""

import logging
import struct

from protocol.constants import (
    VIABLE_PREFIX,
    VIABLE_FRAGMENT_GET_HARDWARE,
    VIABLE_FRAGMENT_GET_SELECTIONS,
    VIABLE_FRAGMENT_SET_SELECTIONS,
)


class ProtocolFragments:
    """Mixin for fragment hardware detection and EEPROM selection storage."""

    def reload_fragment_data(self):
        """Query hardware detection (0x18) and EEPROM selections (0x19)."""
        # Ensure these exist before any code tries to read them
        if not hasattr(self, 'fragment_selections'):
            self.fragment_selections = {}  # From keymap file (string id -> fragment name)
        if not hasattr(self, 'fragment_hw_detection'):
            self.fragment_hw_detection = {}  # From hardware (instance position -> fragment_id)
        if not hasattr(self, 'fragment_eeprom_selections'):
            self.fragment_eeprom_selections = {}  # From EEPROM (instance position -> fragment_id)

        if not self.has_fragments():
            return

        self._reload_hw_detection()
        self._reload_eeprom_selections()

    def _reload_hw_detection(self):
        """
        Query hardware detection results via 0x18 (implicit instance ordering).

        Note: The client_wrapper (0xDD) is handled by usb_send internally.
        We send [0xDF, cmd] and receive [0xDF, cmd, ...] after wrapper processing.
        Response is fixed 21-byte buffer; unused slots are 0xFF.
        """
        try:
            # send_viable already adds 0xDF prefix, so just send the command byte
            data = self.wrapper.send_viable(struct.pack("B", VIABLE_FRAGMENT_GET_HARDWARE), retries=20)
        except Exception:
            self.fragment_hw_detection = {}
            return

        # Response: [0xDF, 0x18, count, frag0, frag1, ..., frag20]
        if len(data) < 24 or data[0] != VIABLE_PREFIX or data[1] != VIABLE_FRAGMENT_GET_HARDWARE:
            self.fragment_hw_detection = {}
            return

        count = data[2]
        self.fragment_hw_detection = {}

        # Validate unused slots are 0xFF
        for i in range(count, 21):
            if data[3 + i] != 0xFF:
                logging.warning("Fragment hw detection slot %d not 0xFF (count=%d)", i, count)

        # Fragment IDs are in instance order (array position = instance identity)
        for instance_idx in range(count):
            fragment_id = data[3 + instance_idx]
            self.fragment_hw_detection[instance_idx] = fragment_id

    def _reload_eeprom_selections(self):
        """
        Query EEPROM selections via 0x19 (implicit instance ordering).

        Response is fixed 21-byte buffer; unused slots are 0xFF.
        """
        try:
            # send_viable already adds 0xDF prefix, so just send the command byte
            data = self.wrapper.send_viable(struct.pack("B", VIABLE_FRAGMENT_GET_SELECTIONS), retries=20)
        except Exception:
            self.fragment_eeprom_selections = {}
            return

        # Response: [0xDF, 0x19, count, frag0, frag1, ..., frag20]
        if len(data) < 24 or data[0] != VIABLE_PREFIX or data[1] != VIABLE_FRAGMENT_GET_SELECTIONS:
            self.fragment_eeprom_selections = {}
            return

        count = data[2]
        self.fragment_eeprom_selections = {}

        # Validate unused slots are 0xFF
        for i in range(count, 21):
            if data[3 + i] != 0xFF:
                logging.warning("Fragment EEPROM selection slot %d not 0xFF (count=%d)", i, count)

        # Fragment IDs are in instance order (array position = instance identity)
        for instance_idx in range(count):
            fragment_id = data[3 + instance_idx]
            # 0xFF means no selection, don't store it
            if fragment_id != 0xFF:
                self.fragment_eeprom_selections[instance_idx] = fragment_id

    def set_fragment_selection(self, instance_idx, option_idx):
        """
        Save a single fragment selection to EEPROM via 0x1A.

        Args:
            instance_idx: Instance array position (0-20)
            option_idx: Index into fragment_options (0-254), or 0xFF to clear

        Returns:
            True on success, False on failure

        Request is fixed 21-byte buffer; unused slots must be 0xFF.
        """
        fragment_id = option_idx  # For clarity - EEPROM stores option index
        # Get current selections, update one, send all
        composition = self.definition.get('composition', {})
        instance_count = len(composition.get('instances', []))

        # Build fixed 21-byte array: used slots from cache, unused slots 0xFF
        selections = [0xFF] * 21
        for i in range(instance_count):
            if i == instance_idx:
                selections[i] = fragment_id
            else:
                selections[i] = self.fragment_eeprom_selections.get(i, 0xFF)

        # send_viable already adds 0xDF prefix, so send [0x1A, count, frag0..frag20]
        request = struct.pack("BB", VIABLE_FRAGMENT_SET_SELECTIONS, instance_count)
        request += bytes(selections)

        try:
            # send_viable handles client wrapper protocol and adds 0xDF prefix
            data = self.wrapper.send_viable(request, retries=20)
        except Exception:
            return False

        if len(data) >= 3 and data[0] == VIABLE_PREFIX and data[1] == VIABLE_FRAGMENT_SET_SELECTIONS and data[2] == 0x00:
            # Success - update local cache
            if fragment_id == 0xFF:
                self.fragment_eeprom_selections.pop(instance_idx, None)
            else:
                self.fragment_eeprom_selections[instance_idx] = fragment_id
            return True
        return False

    def has_fragments(self):
        """Check if keyboard definition has fragments."""
        return bool(self.definition.get('fragments'))

    def save_fragment_selections(self):
        """Return fragment selections for keymap file persistence."""
        return getattr(self, 'fragment_selections', {})

    def restore_fragment_selections(self, data):
        """Restore fragment selections from keymap file."""
        self.fragment_selections = data if data else {}
