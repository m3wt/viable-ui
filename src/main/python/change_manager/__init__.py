# SPDX-License-Identifier: GPL-2.0-or-later
"""Change management with undo/redo support."""
from .change_manager import ChangeManager
from .change_group import ChangeGroup
from .changes import (
    Change,
    KeymapChange,
    EncoderChange,
    ComboChange,
    TapDanceChange,
    KeyOverrideChange,
    AltRepeatKeyChange,
    MacroChange,
    QmkSettingChange,
    SvalboardSettingsChange,
    SvalboardLayerColorChange,
)

__all__ = [
    'ChangeManager',
    'ChangeGroup',
    'Change',
    'KeymapChange',
    'EncoderChange',
    'ComboChange',
    'TapDanceChange',
    'KeyOverrideChange',
    'AltRepeatKeyChange',
    'MacroChange',
    'QmkSettingChange',
    'SvalboardSettingsChange',
    'SvalboardLayerColorChange',
]
