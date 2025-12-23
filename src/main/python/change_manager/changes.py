# SPDX-License-Identifier: GPL-2.0-or-later
"""Change classes for tracking uncommitted modifications."""
from abc import ABC, abstractmethod
from typing import Tuple, Any


class Change(ABC):
    """Base class for all change types."""

    @abstractmethod
    def key(self) -> Tuple:
        """Return unique key for deduplication.

        Changes with the same key will be merged (only latest value kept).
        """
        pass

    @abstractmethod
    def apply(self, keyboard) -> bool:
        """Send this change to the device.

        Returns True on success, False on failure.
        """
        pass

    @abstractmethod
    def revert(self, keyboard) -> bool:
        """Send old value to the device (for undo after save).

        Returns True on success, False on failure.
        """
        pass

    def merge(self, other: 'Change') -> bool:
        """Merge another change into this one.

        Called when a new change has the same key as an existing one.
        Default implementation replaces new_value with other's new_value.

        Returns True if merge was successful.
        """
        if hasattr(self, 'new_value') and hasattr(other, 'new_value'):
            self.new_value = other.new_value
            return True
        return False


class KeymapChange(Change):
    """Change to a key in the keymap."""

    def __init__(self, layer: int, row: int, col: int, old_value: int, new_value: int):
        self.layer = layer
        self.row = row
        self.col = col
        self.old_value = old_value
        self.new_value = new_value

    def key(self) -> Tuple:
        return ('keymap', self.layer, self.row, self.col)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_key(self.layer, self.row, self.col, self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_key(self.layer, self.row, self.col, self.old_value)

    def __repr__(self):
        return f"KeymapChange(layer={self.layer}, row={self.row}, col={self.col}, {self.old_value}->{self.new_value})"


class EncoderChange(Change):
    """Change to an encoder action."""

    def __init__(self, layer: int, index: int, direction: int, old_value: int, new_value: int):
        self.layer = layer
        self.index = index
        self.direction = direction  # 0 = CW, 1 = CCW
        self.old_value = old_value
        self.new_value = new_value

    def key(self) -> Tuple:
        return ('encoder', self.layer, self.index, self.direction)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_encoder(self.layer, self.index, self.direction, self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_encoder(self.layer, self.index, self.direction, self.old_value)

    def __repr__(self):
        return f"EncoderChange(layer={self.layer}, idx={self.index}, dir={self.direction}, {self.old_value}->{self.new_value})"


class ComboChange(Change):
    """Change to a combo entry."""

    def __init__(self, index: int, old_value: Any, new_value: Any):
        self.index = index
        self.old_value = old_value  # Combo object or serialized form
        self.new_value = new_value

    def key(self) -> Tuple:
        return ('combo', self.index)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_combo(self.index, self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_combo(self.index, self.old_value)

    def __repr__(self):
        return f"ComboChange(index={self.index})"


class TapDanceChange(Change):
    """Change to a tap dance entry."""

    def __init__(self, index: int, old_value: Any, new_value: Any):
        self.index = index
        self.old_value = old_value
        self.new_value = new_value

    def key(self) -> Tuple:
        return ('tap_dance', self.index)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_tap_dance(self.index, self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_tap_dance(self.index, self.old_value)

    def __repr__(self):
        return f"TapDanceChange(index={self.index})"


class KeyOverrideChange(Change):
    """Change to a key override entry."""

    def __init__(self, index: int, old_value: Any, new_value: Any):
        self.index = index
        self.old_value = old_value
        self.new_value = new_value

    def key(self) -> Tuple:
        return ('key_override', self.index)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_key_override(self.index, self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_key_override(self.index, self.old_value)

    def __repr__(self):
        return f"KeyOverrideChange(index={self.index})"


class AltRepeatKeyChange(Change):
    """Change to an alternate repeat key entry."""

    def __init__(self, index: int, old_value: Any, new_value: Any):
        self.index = index
        self.old_value = old_value
        self.new_value = new_value

    def key(self) -> Tuple:
        return ('alt_repeat_key', self.index)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_alt_repeat_key(self.index, self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_alt_repeat_key(self.index, self.old_value)

    def __repr__(self):
        return f"AltRepeatKeyChange(index={self.index})"


class MacroChange(Change):
    """Change to macro data (all macros as a unit)."""

    def __init__(self, old_data: bytes, new_data: bytes):
        self.old_value = old_data
        self.new_value = new_data

    def key(self) -> Tuple:
        return ('macro',)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_macro(self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_macro(self.old_value)

    def __repr__(self):
        return f"MacroChange({len(self.old_value)} -> {len(self.new_value)} bytes)"


class QmkSettingChange(Change):
    """Change to a QMK setting."""

    def __init__(self, qsid: int, old_value: int, new_value: int):
        self.qsid = qsid
        self.old_value = old_value
        self.new_value = new_value

    def key(self) -> Tuple:
        return ('qmk_setting', self.qsid)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_qmk_setting(self.qsid, self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_qmk_setting(self.qsid, self.old_value)

    def __repr__(self):
        return f"QmkSettingChange(qsid={self.qsid}, {self.old_value}->{self.new_value})"


class SvalboardSettingsChange(Change):
    """Change to Svalboard settings (all settings as a unit)."""

    def __init__(self, old_settings: dict, new_settings: dict):
        self.old_value = old_settings
        self.new_value = new_settings

    def key(self) -> Tuple:
        return ('svalboard_settings',)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_svalboard_settings(self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_svalboard_settings(self.old_value)

    def __repr__(self):
        return f"SvalboardSettingsChange()"


class SvalboardLayerColorChange(Change):
    """Change to a Svalboard layer color."""

    def __init__(self, layer: int, old_hsv: Tuple[int, int, int], new_hsv: Tuple[int, int, int]):
        self.layer = layer
        self.old_value = old_hsv
        self.new_value = new_hsv

    def key(self) -> Tuple:
        return ('svalboard_layer_color', self.layer)

    def apply(self, keyboard) -> bool:
        return keyboard._commit_svalboard_layer_color(self.layer, self.new_value)

    def revert(self, keyboard) -> bool:
        return keyboard._commit_svalboard_layer_color(self.layer, self.old_value)

    def merge(self, other: 'SvalboardLayerColorChange') -> bool:
        self.new_value = other.new_value
        return True

    def __repr__(self):
        return f"SvalboardLayerColorChange(layer={self.layer}, {self.old_value}->{self.new_value})"
