# SPDX-License-Identifier: GPL-2.0-or-later
"""
Fragment composition for keyboard layouts.

This module handles the expansion of fragment-based keyboard layout definitions
into flat lists of keys with absolute matrix positions.
"""

from copy import copy
from kle_serial import Serial as KleSerial


class FragmentComposer:
    """
    Handles fragment-based layout composition.

    Fragments are visual layout templates (KLE) that can be instantiated
    at specific positions with absolute matrix mappings.

    Two ID systems:
    - fragment.id (int 0-254): Used in protocol for hardware detection
    - instance.id (string): Human-readable name, used in keymap files
    - Instance array position: Protocol identity for EEPROM storage
    """

    def __init__(self, definition):
        """
        Parse fragments and composition from keyboard definition.

        Args:
            definition: Keyboard definition dict with 'fragments' and 'composition' sections
        """
        self.definition = definition
        self.fragments = definition.get('fragments', {})
        self.composition = definition.get('composition', {})
        self.instances = self.composition.get('instances', [])

        # Build fragment_name -> fragment_id mapping (from explicit 'id' field)
        self.fragment_ids = {
            name: frag['id']
            for name, frag in self.fragments.items()
        }

        # Reverse lookup: fragment_id -> fragment_name (for protocol responses)
        self.fragment_names = {
            frag['id']: name
            for name, frag in self.fragments.items()
        }

    def has_fragments(self):
        """Check if this definition uses fragments."""
        return bool(self.fragments) and bool(self.instances)

    def get_selectable_instances(self):
        """
        Get list of instances that have selectable fragment options.

        Returns:
            List of (instance_idx, instance) tuples for selectable instances
        """
        result = []
        for idx, instance in enumerate(self.instances):
            if 'fragment_options' in instance:
                result.append((idx, instance))
        return result

    def get_fragment_id(self, fragment_name):
        """Get numeric fragment ID from fragment name."""
        return self.fragment_ids.get(fragment_name, 0xFF)

    def get_fragment_name(self, fragment_id):
        """Get fragment name from numeric fragment ID."""
        return self.fragment_names.get(fragment_id)

    def resolve_instance(self, instance_idx, instance, hw_detection, eeprom_selections, keymap_selections):
        """
        Resolve which fragment to use for an instance.

        Priority depends on allow_override flag:
        - If hardware detected AND allow_override=False: hardware wins (no user choice)
        - If hardware detected AND allow_override=True: user selection can override
        - Otherwise: keymap > EEPROM > default

        Args:
            instance_idx: Array position (0-based), used as numeric instance ID for protocol
            instance: Instance dict from composition.instances
            hw_detection: Dict mapping instance position -> fragment_id (from 0x18)
            eeprom_selections: Dict mapping instance position -> fragment_id (from 0x19)
            keymap_selections: Dict mapping string instance id -> fragment name (from loaded keymap)

        Returns:
            Tuple of (fragment_name, placement, matrix_map, encoder_offset)
        """
        # Two ID systems: array position for protocol, string for keymap/human use
        string_id = instance['id']  # str ("left_index"), used by keymap file
        encoder_offset = instance.get('encoder_offset', 0)

        # Fixed instance - no options
        if 'fragment' in instance:
            return (
                instance['fragment'],
                instance['placement'],
                instance['matrix_map'],
                encoder_offset
            )

        # Selectable instance
        options = instance['fragment_options']
        # allow_override defaults to True: user CAN override hardware detection
        # Only meaningful when hardware_detect is True for this instance
        allow_override = instance.get('allow_override', True)

        # Check hardware detection
        hw_frag_id = hw_detection.get(instance_idx, 0xFF)
        hw_detected = hw_frag_id != 0xFF

        # 1. If hardware detected AND override not allowed, hardware wins
        if hw_detected and not allow_override:
            for opt in options:
                opt_frag_id = self.fragments[opt['fragment']]['id']
                if opt_frag_id == hw_frag_id:
                    return (opt['fragment'], opt['placement'],
                            opt['matrix_map'], opt.get('encoder_offset', encoder_offset))

        # 2. Check keymap file selection (user's explicit intent when loading keymap)
        if string_id in keymap_selections:
            selected = keymap_selections[string_id]
            for opt in options:
                if opt['fragment'] == selected:
                    return (opt['fragment'], opt['placement'],
                            opt['matrix_map'], opt.get('encoder_offset', encoder_offset))

        # 3. Check EEPROM selection (persisted from previous UI choice)
        # EEPROM stores index into fragment_options, not fragment ID
        if instance_idx in eeprom_selections:
            opt_idx = eeprom_selections[instance_idx]
            if opt_idx < len(options):
                opt = options[opt_idx]
                return (opt['fragment'], opt['placement'],
                        opt['matrix_map'], opt.get('encoder_offset', encoder_offset))

        # 4. If hardware detected (with override allowed but no user selection), use hardware
        if hw_detected:
            for opt in options:
                opt_frag_id = self.fragments[opt['fragment']]['id']
                if opt_frag_id == hw_frag_id:
                    return (opt['fragment'], opt['placement'],
                            opt['matrix_map'], opt.get('encoder_offset', encoder_offset))

        # 5. Fall back to default
        for opt in options:
            if opt.get('default'):
                return (opt['fragment'], opt['placement'],
                        opt['matrix_map'], opt.get('encoder_offset', encoder_offset))

        # Should never happen if validation passed
        opt = options[0]
        return (opt['fragment'], opt['placement'],
                opt['matrix_map'], opt.get('encoder_offset', encoder_offset))

    def expand_to_keys(self, hw_detection=None, eeprom_selections=None, keymap_selections=None):
        """
        Expand all instances to flat list of keys with absolute matrix positions.

        Args:
            hw_detection: Dict mapping instance position -> fragment_id (from 0x18)
            eeprom_selections: Dict mapping instance position -> fragment_id (from 0x19)
            keymap_selections: Dict mapping string instance id -> fragment name (from keymap file)

        Returns:
            Tuple of (keys, encoders) - two lists of Key objects
        """
        hw_detection = hw_detection or {}
        eeprom_selections = eeprom_selections or {}
        keymap_selections = keymap_selections or {}

        serial = KleSerial()
        all_keys = []
        all_encoders = []

        for instance_idx, instance in enumerate(self.instances):
            frag_name, placement, matrix_map, encoder_offset = \
                self.resolve_instance(instance_idx, instance, hw_detection, eeprom_selections, keymap_selections)

            fragment = self.fragments[frag_name]
            kb = serial.deserialize(fragment['kle'])

            key_idx = 0

            for key in kb.keys:
                # Deep copy to avoid modifying the original
                key = copy(key)

                # Apply placement offset
                key.x += placement['x']
                key.y += placement['y']

                # Check if encoder (Vial format: labels[4] == "e")
                is_encoder = (len(key.labels) > 4 and key.labels[4] == "e"
                              and key.labels[0] and "," in key.labels[0])

                # Fragment keys don't have layout options (no KLE multi-layout support)
                key.layout_index = -1
                key.layout_option = -1

                if is_encoder:
                    # Remap encoder index: "local_idx,dir" -> "global_idx,dir"
                    local_idx, direction = key.labels[0].split(",")
                    global_idx = int(local_idx) + encoder_offset
                    # Create new labels list with updated encoder index
                    key.labels = list(key.labels)
                    key.labels[0] = f"{global_idx},{direction}"
                    # Set encoder properties
                    key.encoder_idx = global_idx
                    key.encoder_dir = int(direction)
                    all_encoders.append(key)
                else:
                    # Regular key - assign matrix position
                    key.row = None
                    key.col = None
                    key.encoder_idx = None
                    key.encoder_dir = None
                    if key_idx < len(matrix_map):
                        row, col = matrix_map[key_idx]
                        key.row = row
                        key.col = col
                        key_idx += 1
                    all_keys.append(key)

        return all_keys, all_encoders

    def get_instance_count(self):
        """Get total number of instances."""
        return len(self.instances)

    def get_instance_by_id(self, string_id):
        """
        Get instance by string ID.

        Args:
            string_id: The string 'id' field of the instance

        Returns:
            Tuple of (instance_idx, instance) or (None, None) if not found
        """
        for idx, instance in enumerate(self.instances):
            if instance['id'] == string_id:
                return idx, instance
        return None, None

    def get_default_fragment(self, instance):
        """
        Get the default fragment for an instance (first option).

        Args:
            instance: Instance dict

        Returns:
            Fragment name string
        """
        if 'fragment' in instance:
            return instance['fragment']

        # Default is first option
        options = instance.get('fragment_options', [])
        if options:
            return options[0]['fragment']

        return None

    def get_option_index(self, instance, fragment_name):
        """
        Get the index of a fragment option within an instance.

        Args:
            instance: Instance dict
            fragment_name: Name of fragment to find

        Returns:
            Index into fragment_options, or 0 if not found
        """
        options = instance.get('fragment_options', [])
        for idx, opt in enumerate(options):
            if opt['fragment'] == fragment_name:
                return idx
        return 0

    def get_fragment_options(self, instance):
        """
        Get list of available fragment options for an instance.

        Args:
            instance: Instance dict

        Returns:
            List of fragment names, or empty list if fixed instance
        """
        if 'fragment' in instance:
            return []  # Fixed instance

        return [opt['fragment'] for opt in instance.get('fragment_options', [])]

    def get_fragment_display_name(self, fragment_name):
        """
        Get human-readable display name for a fragment.

        Uses the 'description' field if available, otherwise formats the name.

        Args:
            fragment_name: Internal fragment name (e.g., "finger_5")

        Returns:
            Display name string (e.g., "5-key finger cluster (no 2S)")
        """
        fragment = self.fragments.get(fragment_name, {})
        if 'description' in fragment:
            return fragment['description']
        # Fallback: convert snake_case to Title Case
        return fragment_name.replace('_', ' ').title()

    def get_instance_display_name(self, instance_id):
        """
        Get human-readable display name for an instance position.

        Args:
            instance_id: Internal instance ID (e.g., "left_pinky")

        Returns:
            Display name string (e.g., "Left Pinky")
        """
        # Convert snake_case to Title Case
        return instance_id.replace('_', ' ').title()
