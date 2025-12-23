# SPDX-License-Identifier: GPL-2.0-or-later
"""Serial assignment modes for auto-advance through keys."""
from enum import Enum, auto


class SerialMode(Enum):
    TOP_TO_BOTTOM = auto()  # (y, x) - Vial default
    LEFT_TO_RIGHT = auto()  # (x, y)
    CLUSTER = auto()        # By finger cluster (Svalboard only)
    DIRECTION = auto()      # By key direction N->C->S->W->E (Svalboard only)


# Svalboard matrix layout
# Matrix is 10 rows x 6 cols. Columns = directions, Rows = fingers.
# Rows 1-4: Left hand (pinky->index), Rows 6-9: Right hand (index->pinky)
# Row 0: Left thumb, Row 5: Right thumb
# Col 0=S, Col 1=E, Col 2=C, Col 3=N, Col 4=W, Col 5=2S (optional)
# Formula: keymap_id = row * 6 + col

# Direction order within a cluster: clockwise from N, then center, then 2S
# N, E, S, W, C, 2S (cols 3, 1, 0, 4, 2, 5)
SVALBOARD_CLUSTER_DIRECTION_ORDER = [3, 1, 0, 4, 2, 5]

# Cluster (row) order for "By cluster" mode
# Left hand: index(4), middle(3), ring(2), pinky(1), thumb(0)
# Right hand: index(6), middle(7), ring(8), pinky(9), thumb(5)
SVALBOARD_CLUSTER_ROW_ORDER = [4, 3, 2, 1, 0, 6, 7, 8, 9, 5]


def get_svalboard_cluster_order(existing_keymap_ids):
    """Generate cluster order based on which keys actually exist.

    Args:
        existing_keymap_ids: set of keymap IDs that exist in the layout

    Returns:
        List of keymap IDs in cluster order (only includes existing keys)
    """
    result = []
    for row in SVALBOARD_CLUSTER_ROW_ORDER:
        for col in SVALBOARD_CLUSTER_DIRECTION_ORDER:
            keymap_id = row * 6 + col
            if keymap_id in existing_keymap_ids:
                result.append(keymap_id)
    return result


SVALBOARD_DIRECTION_ORDER = [
    # N keys (col 3): left hand rows 4,3,2,1 then right hand 6,7,8,9
    27, 21, 15, 9, 39, 45, 51, 57,
    # C keys (col 2)
    26, 20, 14, 8, 38, 44, 50, 56,
    # S keys (col 0)
    24, 18, 12, 6, 36, 42, 48, 54,
    # W keys (col 4)
    28, 22, 16, 10, 40, 46, 52, 58,
    # E keys (col 1)
    25, 19, 13, 7, 37, 43, 49, 55,
    # Thumb clusters (rows 0, 5) - Claussen-style ordering
    3, 5, 1, 31, 35, 33,  # Top row
    4, 2, 0, 30, 32, 34,  # Bottom row
    # Note: Col 5 (2S keys) omitted - they're layout-optional
]
