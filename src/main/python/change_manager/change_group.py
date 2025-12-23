# SPDX-License-Identifier: GPL-2.0-or-later
"""ChangeGroup for grouping changes into single undo units."""
from typing import List, Dict, Tuple, Optional
from .changes import Change


class ChangeGroup:
    """Groups multiple changes into a single undo/redo unit.

    Used for operations like "Fill layer" or "Paste layer" that
    modify multiple keys but should undo as one action.
    """

    def __init__(self, name: str):
        self.name = name
        self._changes: List[Change] = []
        self._by_key: Dict[Tuple, Change] = {}

    def add(self, change: Change) -> None:
        """Add a change, merging if same key exists."""
        key = change.key()
        if key in self._by_key:
            existing = self._by_key[key]
            existing.merge(change)
        else:
            self._changes.append(change)
            self._by_key[key] = change

    def is_empty(self) -> bool:
        """Return True if no changes in group."""
        return len(self._changes) == 0

    def get_change(self, key: Tuple) -> Optional[Change]:
        """Get change by key, or None if not found."""
        return self._by_key.get(key)

    def has_key(self, key: Tuple) -> bool:
        """Return True if a change with this key exists."""
        return key in self._by_key

    @property
    def changes(self) -> List[Change]:
        """Return list of changes (read-only)."""
        return list(self._changes)

    @property
    def keys(self) -> set:
        """Return set of all change keys."""
        return set(self._by_key.keys())

    def apply(self, keyboard) -> bool:
        """Apply all changes to the device.

        Returns True if all succeeded, False if any failed.
        """
        success = True
        for change in self._changes:
            if not change.apply(keyboard):
                success = False
        return success

    def revert(self, keyboard) -> bool:
        """Revert all changes on the device (reverse order).

        Returns True if all succeeded, False if any failed.
        """
        success = True
        for change in reversed(self._changes):
            if not change.revert(keyboard):
                success = False
        return success

    def __len__(self) -> int:
        return len(self._changes)

    def __repr__(self):
        return f"ChangeGroup('{self.name}', {len(self._changes)} changes)"
