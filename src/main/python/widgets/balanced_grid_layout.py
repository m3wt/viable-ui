# SPDX-License-Identifier: GPL-2.0-or-later
"""
Balanced grid layout that distributes items evenly across rows.

When wrapping is needed, calculates optimal columns to balance rows
rather than greedily filling rows like FlowLayout.

Example with 16 items:
- Width fits 10: FlowLayout would give 10+6, BalancedGridLayout gives 8+8
- Width fits 5: FlowLayout would give 5+5+5+1, BalancedGridLayout gives 4+4+4+4
"""

from math import ceil

from qtpy.QtCore import QPoint, QRect, QSize, Qt
from qtpy.QtWidgets import QLayout, QSizePolicy


class BalancedGridLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=8, stretch_items=False):
        super().__init__(parent)

        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)

        self._spacing = spacing
        self._stretch_items = stretch_items  # If True, items expand to fill cell width
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def spacing(self):
        return self._spacing

    def setSpacing(self, spacing):
        self._spacing = spacing

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margin, _, _, _ = self.getContentsMargins()
        size += QSize(2 * margin, 2 * margin)
        return size

    def _calculate_balanced_columns(self, available_width, item_width, item_count):
        """Calculate optimal column count for balanced rows."""
        if item_count == 0:
            return 1

        spacing = self._spacing

        # How many items can fit in one row?
        if item_width + spacing > 0:
            max_cols = max(1, (available_width + spacing) // (item_width + spacing))
        else:
            max_cols = item_count

        # If all items fit in one row, use that
        if max_cols >= item_count:
            return item_count

        # Calculate rows needed, then balance
        rows = ceil(item_count / max_cols)
        balanced_cols = ceil(item_count / rows)

        return balanced_cols

    def doLayout(self, rect, testOnly):
        if not self.itemList:
            return 0

        margin_left, margin_top, margin_right, margin_bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(margin_left, margin_top, -margin_right, -margin_bottom)

        spacing = self._spacing

        # For stretch mode with variable items, use max width for column calculation
        if self._stretch_items:
            item_width = max(item.sizeHint().width() for item in self.itemList)
        else:
            item_width = self.itemList[0].sizeHint().width()

        # Calculate balanced columns
        cols = self._calculate_balanced_columns(
            effective_rect.width(),
            item_width,
            len(self.itemList)
        )

        # Calculate cell width to distribute space evenly
        total_spacing = (cols - 1) * spacing if cols > 1 else 0
        cell_width = (effective_rect.width() - total_spacing) // cols if cols > 0 else item_width

        # Calculate row heights (max height of items in each row)
        total_rows = ceil(len(self.itemList) / cols) if cols > 0 else 1
        row_heights = []
        for row in range(total_rows):
            row_start = row * cols
            row_end = min(row_start + cols, len(self.itemList))
            row_height = max(self.itemList[i].sizeHint().height() for i in range(row_start, row_end))
            row_heights.append(row_height)

        # Layout items in grid
        x_start = effective_rect.x()
        y_pos = effective_rect.y()

        for i, item in enumerate(self.itemList):
            col = i % cols
            row = i // cols

            if col == 0 and row > 0:
                y_pos += row_heights[row - 1] + spacing

            cell_x = x_start + col * (cell_width + spacing)

            if self._stretch_items:
                # Stretch item to fill cell width
                if not testOnly:
                    item.setGeometry(QRect(cell_x, y_pos, cell_width, item.sizeHint().height()))
            else:
                # Center item in cell
                item_actual_width = item.sizeHint().width()
                x_offset = (cell_width - item_actual_width) // 2
                x = cell_x + x_offset

                if not testOnly:
                    item.setGeometry(QRect(QPoint(x, y_pos), item.sizeHint()))

        # Calculate total height
        total_height = sum(row_heights) + (total_rows - 1) * spacing if row_heights else 0

        return total_height + margin_top + margin_bottom
