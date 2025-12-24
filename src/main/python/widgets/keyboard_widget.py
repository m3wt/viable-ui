from collections import defaultdict

from PyQt5.QtGui import QPainter, QColor, QPainterPath, QTransform, QBrush, QPolygonF, QPalette, QPen
from PyQt5.QtWidgets import QWidget, QToolTip, QApplication
from PyQt5.QtCore import Qt, QSize, QRect, QPointF, pyqtSignal, QEvent, QRectF

from change_manager import ChangeManager
from constants import KEY_SIZE_RATIO, KEY_SPACING_RATIO, KEYBOARD_WIDGET_PADDING, \
    KEYBOARD_WIDGET_MASK_HEIGHT, KEY_ROUNDNESS, SHADOW_SIDE_PADDING, SHADOW_TOP_PADDING, SHADOW_BOTTOM_PADDING, \
    KEYBOARD_WIDGET_NONMASK_PADDING
from themes import Theme
from serial_assignment import SerialMode, SVALBOARD_DIRECTION_ORDER, get_svalboard_cluster_order


class KeyWidget:

    def __init__(self, desc, scale, shift_x=0, shift_y=0):
        self.active = False
        self.on = False
        self.masked = False
        self.pressed = False
        self.desc = desc
        self.text = ""
        self.mask_text = ""
        self.tooltip = ""
        self.color = None
        self.mask_color = None
        self.scale = 0

        self.rotation_angle = desc.rotation_angle

        self.has2 = desc.width2 != desc.width or desc.height2 != desc.height or desc.x2 != 0 or desc.y2 != 0

        self.update_position(scale, shift_x, shift_y)

    def update_position(self, scale, shift_x=0, shift_y=0):
        if self.scale != scale or self.shift_x != shift_x or self.shift_y != shift_y:
            self.scale = scale
            self.size = self.scale * (KEY_SIZE_RATIO + KEY_SPACING_RATIO)
            spacing = self.scale * KEY_SPACING_RATIO

            self.rotation_x = self.size * self.desc.rotation_x
            self.rotation_y = self.size * self.desc.rotation_y

            self.shift_x = shift_x
            self.shift_y = shift_y
            self.x = self.size * self.desc.x
            self.y = self.size * self.desc.y
            self.w = self.size * self.desc.width - spacing
            self.h = self.size * self.desc.height - spacing

            self.rect = QRect(
                round(self.x),
                round(self.y),
                round(self.w),
                round(self.h)
            )
            self.text_rect = QRect(
                round(self.x),
                round(self.y + self.size * SHADOW_TOP_PADDING),
                round(self.w),
                round(self.h - self.size * (SHADOW_BOTTOM_PADDING + SHADOW_TOP_PADDING))
            )

            self.x2 = self.x + self.size * self.desc.x2
            self.y2 = self.y + self.size * self.desc.y2
            self.w2 = self.size * self.desc.width2 - spacing
            self.h2 = self.size * self.desc.height2 - spacing

            self.rect2 = QRect(
                round(self.x2),
                round(self.y2),
                round(self.w2),
                round(self.h2)
            )

            self.bbox = self.calculate_bbox(self.rect)
            self.bbox2 = self.calculate_bbox(self.rect2)
            self.polygon = QPolygonF(self.bbox + [self.bbox[0]])
            self.polygon2 = QPolygonF(self.bbox2 + [self.bbox2[0]])
            self.polygon = self.polygon.united(self.polygon2)
            self.corner = self.size * KEY_ROUNDNESS
            self.background_draw_path = self.calculate_background_draw_path()
            self.foreground_draw_path = self.calculate_foreground_draw_path()
            self.extra_draw_path = self.calculate_extra_draw_path()

            # calculate areas where the inner keycode will be located
            # nonmask = outer (e.g. Rsft_T)
            # mask = inner (e.g. KC_A)
            self.nonmask_rect = QRect(
                round(self.x),
                round(self.y + self.size * KEYBOARD_WIDGET_NONMASK_PADDING),
                round(self.w),
                round(self.h * (1 - KEYBOARD_WIDGET_MASK_HEIGHT))
            )
            self.mask_rect = QRect(
                round(self.x + self.size * SHADOW_SIDE_PADDING),
                round(self.y + self.h * (1 - KEYBOARD_WIDGET_MASK_HEIGHT)),
                round(self.w - 2 * self.size * SHADOW_SIDE_PADDING),
                round(self.h * KEYBOARD_WIDGET_MASK_HEIGHT - self.size * SHADOW_BOTTOM_PADDING)
            )
            self.mask_bbox = self.calculate_bbox(self.mask_rect)
            self.mask_polygon = QPolygonF(self.mask_bbox + [self.mask_bbox[0]])

    def calculate_bbox(self, rect):
        x1 = rect.topLeft().x()
        y1 = rect.topLeft().y()
        x2 = rect.bottomRight().x()
        y2 = rect.bottomRight().y()
        points = [(x1, y1), (x1, y2), (x2, y2), (x2, y1)]
        bbox = []
        for p in points:
            t = QTransform()
            t.translate(self.shift_x, self.shift_y)
            t.translate(self.rotation_x, self.rotation_y)
            t.rotate(self.rotation_angle)
            t.translate(-self.rotation_x, -self.rotation_y)
            p = t.map(QPointF(p[0], p[1]))
            bbox.append(p)
        return bbox

    def calculate_background_draw_path(self):
        path = QPainterPath()
        path.addRoundedRect(
            round(self.x),
            round(self.y),
            round(self.w),
            round(self.h),
            self.corner,
            self.corner
        )

        # second part only considered if different from first
        if self.has2:
            path2 = QPainterPath()
            path2.addRoundedRect(
                round(self.x2),
                round(self.y2),
                round(self.w2),
                round(self.h2),
                self.corner,
                self.corner
            )
            path = path.united(path2)

        return path

    def calculate_foreground_draw_path(self):
        path = QPainterPath()
        path.addRoundedRect(
            round(self.x + self.size * SHADOW_SIDE_PADDING),
            round(self.y + self.size * SHADOW_TOP_PADDING),
            round(self.w - 2 * self.size * SHADOW_SIDE_PADDING),
            round(self.h - self.size * (SHADOW_BOTTOM_PADDING + SHADOW_TOP_PADDING)),
            self.corner,
            self.corner
        )

        # second part only considered if different from first
        if self.has2:
            path2 = QPainterPath()
            path2.addRoundedRect(
                round(self.x2 + self.size * SHADOW_SIDE_PADDING),
                round(self.y2 + self.size * SHADOW_TOP_PADDING),
                round(self.w2 - 2 * self.size * SHADOW_SIDE_PADDING),
                round(self.h2 - self.size * (SHADOW_BOTTOM_PADDING + SHADOW_TOP_PADDING)),
                self.corner,
                self.corner
            )
            path = path.united(path2)

        return path

    def calculate_extra_draw_path(self):
        return QPainterPath()

    def setText(self, text):
        self.text = text

    def setMaskText(self, text):
        self.mask_text = text

    def setToolTip(self, tooltip):
        self.tooltip = tooltip

    def setActive(self, active):
        self.active = active

    def setOn(self, on):
        self.on = on

    def setPressed(self, pressed):
        self.pressed = pressed

    def setColor(self, color):
        self.color = color

    def setMaskColor(self, color):
        self.mask_color = color

    def __repr__(self):
        qualifiers = ["KeyboardWidget"]
        if self.desc.row is not None:
            qualifiers.append("matrix:{},{}".format(self.desc.row, self.desc.col))
        if self.desc.layout_index != -1:
            qualifiers.append("layout:{},{}".format(self.desc.layout_index, self.desc.layout_option))
        return " ".join(qualifiers)


class EncoderWidget(KeyWidget):

    def calculate_background_draw_path(self):
        path = QPainterPath()
        path.addEllipse(round(self.x), round(self.y), round(self.w), round(self.h))
        return path

    def calculate_foreground_draw_path(self):
        path = QPainterPath()
        path.addEllipse(
            round(self.x + self.size * SHADOW_SIDE_PADDING),
            round(self.y + self.size * SHADOW_TOP_PADDING),
            round(self.w - 2 * self.size * SHADOW_SIDE_PADDING),
            round(self.h - self.size * (SHADOW_BOTTOM_PADDING + SHADOW_TOP_PADDING))
        )
        return path

    def calculate_extra_draw_path(self):
        path = QPainterPath()
        # midpoint of arrow triangle
        p = self.h
        x = self.x
        y = self.y + p / 2
        if self.desc.encoder_dir == 0:
            # counterclockwise - pointing down
            path.moveTo(round(x), round(y))
            path.lineTo(round(x + p / 10), round(y - p / 10))
            path.lineTo(round(x), round(y + p / 10))
            path.lineTo(round(x - p / 10), round(y - p / 10))
            path.lineTo(round(x), round(y))
        else:
            # clockwise - pointing up
            path.moveTo(round(x), round(y))
            path.lineTo(round(x + p / 10), round(y + p / 10))
            path.lineTo(round(x), round(y - p / 10))
            path.lineTo(round(x - p / 10), round(y + p / 10))
            path.lineTo(round(x), round(y))
        return path

    def __repr__(self):
        return "EncoderWidget"


class KeyboardWidget(QWidget):

    clicked = pyqtSignal()
    deselected = pyqtSignal()
    anykey = pyqtSignal()

    def __init__(self, layout_editor):
        super().__init__()

        self.enabled = True
        self.scale = 1
        self.padding = KEYBOARD_WIDGET_PADDING

        self.setMouseTracking(True)

        self.layout_editor = layout_editor

        # widgets common for all layouts
        self.common_widgets = []

        # layout-specific widgets
        self.widgets_for_layout = []

        # widgets in current layout
        self.widgets = []

        self.width = self.height = 0
        self.active_key = None
        self.active_mask = False

        # Serial assignment mode for select_next()
        self.serial_mode = SerialMode.TOP_TO_BOTTOM
        self._widget_order_cache = None
        self._matrix_cols = 6  # Set by keymap_editor for CLUSTER mode

        # Current layer for modified key detection
        self.current_layer = 0

    def set_keys(self, keys, encoders):
        self.common_widgets = []
        self.widgets_for_layout = []

        self.add_keys([(x, KeyWidget) for x in keys] + [(x, EncoderWidget) for x in encoders])
        self.update_layout()

    def add_keys(self, keys):
        scale_factor = self.fontMetrics().height()

        for key, cls in keys:
            if key.layout_index == -1:
                self.common_widgets.append(cls(key, scale_factor))
            else:
                self.widgets_for_layout.append(cls(key, scale_factor))

    def place_widgets(self):
        scale_factor = self.fontMetrics().height()

        self.widgets = []

        # place common widgets, that is, ones which are always displayed and require no extra transforms
        for widget in self.common_widgets:
            widget.update_position(scale_factor)
            self.widgets.append(widget)

        # top-left position for specific layout
        layout_x = defaultdict(lambda: defaultdict(lambda: 1e6))
        layout_y = defaultdict(lambda: defaultdict(lambda: 1e6))

        # determine top-left position for every layout option
        for widget in self.widgets_for_layout:
            widget.update_position(scale_factor)
            idx, opt = widget.desc.layout_index, widget.desc.layout_option
            p = widget.polygon.boundingRect().topLeft()
            layout_x[idx][opt] = min(layout_x[idx][opt], p.x())
            layout_y[idx][opt] = min(layout_y[idx][opt], p.y())

        # obtain widgets for all layout options now that we know how to shift them
        for widget in self.widgets_for_layout:
            idx, opt = widget.desc.layout_index, widget.desc.layout_option
            if opt == self.layout_editor.get_choice(idx):
                shift_x = layout_x[idx][opt] - layout_x[idx][0]
                shift_y = layout_y[idx][opt] - layout_y[idx][0]
                widget.update_position(scale_factor, -shift_x, -shift_y)
                self.widgets.append(widget)

        # at this point some widgets on left side might be cutoff, or there may be too much empty space
        # calculate top left position of visible widgets and shift everything around
        top_x = top_y = 1e6
        for widget in self.widgets:
            if not widget.desc.decal:
                p = widget.polygon.boundingRect().topLeft()
                top_x = min(top_x, p.x())
                top_y = min(top_y, p.y())
        for widget in self.widgets:
            widget.update_position(widget.scale, widget.shift_x - top_x + self.padding,
                                   widget.shift_y - top_y + self.padding)

    def update_layout(self):
        """ Updates self.widgets for the currently active layout """

        # Invalidate widget order cache when layout changes
        self._widget_order_cache = None

        # determine widgets for current layout
        self.place_widgets()
        self.widgets = list(filter(lambda w: not w.desc.decal, self.widgets))

        self.widgets.sort(key=lambda w: (w.y, w.x))

        # determine maximum width and height of container
        max_w = max_h = 0
        for key in self.widgets:
            p = key.polygon.boundingRect().bottomRight()
            max_w = max(max_w, p.x() * self.scale)
            max_h = max(max_h, p.y() * self.scale)

        self.width = round(max_w + 2 * self.padding)
        self.height = round(max_h + 2 * self.padding)

        self.update()
        self.updateGeometry()

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        qp.setRenderHint(QPainter.Antialiasing)

        palette = QApplication.palette()

        # Text pen
        text_pen = qp.pen()
        text_pen.setColor(palette.color(QPalette.ButtonText))

        # Border pen for normal keys
        border_pen = qp.pen()
        border_pen.setColor(palette.color(QPalette.Mid))
        border_pen.setWidthF(2.0)

        # Border pen for selected keys (uses Highlight/selection color)
        active_pen = qp.pen()
        active_pen.setColor(palette.color(QPalette.Highlight))
        active_pen.setWidthF(2.0)

        # Background brush for normal keys
        background_brush = QBrush()
        background_brush.setColor(palette.color(QPalette.Button))
        background_brush.setStyle(Qt.SolidPattern)

        # Background brush for pressed keys (matrix tester)
        pressed_brush = QBrush()
        pressed_brush.setColor(palette.color(QPalette.Highlight))
        pressed_brush.setStyle(Qt.SolidPattern)

        # Background brush for "on" keys
        on_brush = QBrush()
        on_brush.setColor(palette.color(QPalette.Highlight).darker(150))
        on_brush.setStyle(Qt.SolidPattern)

        # Mask area brush (for mod-tap inner key)
        mask_brush = QBrush()
        mask_brush.setColor(palette.color(QPalette.Button).lighter(Theme.mask_light_factor()))
        mask_brush.setStyle(Qt.SolidPattern)

        # Encoder arrow
        extra_brush = QBrush()
        extra_brush.setColor(palette.color(QPalette.ButtonText))
        extra_brush.setStyle(Qt.SolidPattern)

        mask_font = qp.font()
        mask_font.setPointSize(round(mask_font.pointSize() * 0.8))

        # Smaller font for longer labels (e.g., macro text)
        small_font = qp.font()
        small_font.setPointSize(round(small_font.pointSize() * 0.7))

        default_font = qp.font()

        # Modified key tint brush (accent color at ~20% opacity)
        accent_color = palette.color(QPalette.Link)
        tint_color = QColor(accent_color.red(), accent_color.green(), accent_color.blue(), 50)
        modified_tint_brush = QBrush(tint_color, Qt.SolidPattern)

        # Active/selected key tint brush (highlight color at ~20% opacity)
        highlight_color = palette.color(QPalette.Highlight)
        highlight_tint_color = QColor(highlight_color.red(), highlight_color.green(), highlight_color.blue(), 50)
        highlight_tint_brush = QBrush(highlight_tint_color, Qt.SolidPattern)

        # Modified key border
        modified_pen = QPen(accent_color)
        modified_pen.setWidthF(2.0)

        cm = ChangeManager.instance()

        for idx, key in enumerate(self.widgets):
            qp.save()

            qp.scale(self.scale, self.scale)
            qp.translate(key.shift_x, key.shift_y)
            qp.translate(key.rotation_x, key.rotation_y)
            qp.rotate(key.rotation_angle)
            qp.translate(-key.rotation_x, -key.rotation_y)

            active = key.active or (self.active_key == key and not self.active_mask)

            # Check if key has pending modifications
            if key.desc.row is not None:
                change_key = ('keymap', self.current_layer, key.desc.row, key.desc.col)
            elif key.desc.encoder_idx is not None:
                change_key = ('encoder', self.current_layer, key.desc.encoder_idx, key.desc.encoder_dir)
            else:
                change_key = None
            is_modified = change_key and cm.is_modified(change_key)

            # Choose brush based on key state
            if key.pressed:
                brush = pressed_brush
            elif key.on:
                brush = on_brush
            else:
                brush = background_brush

            # Draw keycap: flat style with border
            # Active border takes priority - modified state shown via tint overlay
            if active:
                qp.setPen(active_pen)
            elif is_modified:
                qp.setPen(modified_pen)
            else:
                qp.setPen(border_pen)
            qp.setBrush(brush)
            qp.drawPath(key.background_draw_path)

            # Draw key text
            if key.masked:
                # Draw the outer legend (smaller font)
                qp.setFont(mask_font)
                qp.setPen(key.color if key.color else text_pen)
                qp.drawText(key.nonmask_rect, Qt.AlignCenter, key.text)

                # Draw the inner key area
                mask_active = self.active_key == key and self.active_mask
                qp.setPen(active_pen if mask_active else border_pen)
                qp.setBrush(mask_brush)
                qp.drawRoundedRect(key.mask_rect, key.corner, key.corner)

                # Draw the inner legend
                qp.setPen(key.mask_color if key.mask_color else text_pen)
                qp.drawText(key.mask_rect, Qt.AlignCenter, key.mask_text)
            else:
                # Draw the legend
                qp.setPen(key.color if key.color else text_pen)
                # Use smaller font for longer single-line text or macro previews
                # Macro previews have format "M{digit(s)}\n{text}" - center M#, left-align preview
                is_macro_preview = False
                if '\n' in key.text:
                    first_line = key.text.split('\n', 1)[0]
                    # Must be exactly "M" followed by digits (e.g., "M0", "M12")
                    is_macro_preview = (first_line.startswith('M') and
                                        len(first_line) > 1 and
                                        first_line[1:].isdigit())
                use_small_font = is_macro_preview or (len(key.text) > 6 and '\n' not in key.text)
                if use_small_font:
                    qp.setFont(small_font)
                else:
                    qp.setFont(default_font)
                if is_macro_preview:
                    parts = key.text.split('\n', 1)
                    font_height = qp.fontMetrics().height()
                    gap = font_height // 3  # Small gap between lines
                    total_height = font_height * 2 + gap
                    top_offset = (key.rect.height() - total_height) // 2
                    # Draw M# centered, preview left-aligned below
                    top_rect = key.rect.adjusted(0, top_offset, 0, 0)
                    bot_rect = key.rect.adjusted(2, top_offset + font_height + gap, -2, 0)
                    qp.drawText(top_rect, Qt.AlignHCenter | Qt.AlignTop, parts[0])
                    qp.drawText(bot_rect, Qt.AlignLeft | Qt.AlignTop, parts[1] if len(parts) > 1 else "")
                else:
                    qp.drawText(key.rect, Qt.AlignCenter, key.text)

            # Draw tint overlay (active takes priority over modified)
            if active:
                qp.setPen(Qt.NoPen)
                qp.setBrush(highlight_tint_brush)
                qp.drawPath(key.background_draw_path)
            elif is_modified:
                qp.setPen(Qt.NoPen)
                qp.setBrush(modified_tint_brush)
                qp.drawPath(key.background_draw_path)
                if key.masked:
                    qp.drawRoundedRect(key.mask_rect, key.corner, key.corner)

            # Draw the extra shape (encoder arrow)
            qp.setPen(text_pen)
            qp.setBrush(extra_brush)
            qp.drawPath(key.extra_draw_path)

            qp.restore()

        qp.end()

    def minimumSizeHint(self):
        return QSize(self.width, self.height)

    def sizeHint(self):
        return QSize(self.width, self.height)

    def hit_test(self, pos):
        """ Returns key, hit_masked_part """

        for key in self.widgets:
            if key.masked and key.mask_polygon.containsPoint(pos/self.scale, Qt.OddEvenFill):
                return key, True
            if key.polygon.containsPoint(pos/self.scale, Qt.OddEvenFill):
                return key, False

        return None, False

    def mousePressEvent(self, ev):
        if not self.enabled:
            return

        self.active_key, self.active_mask = self.hit_test(ev.pos())
        if self.active_key is not None:
            self.clicked.emit()
        else:
            self.deselected.emit()
        self.update()

    def resizeEvent(self, ev):
        if self.isEnabled():
            self.update_layout()

    def set_serial_mode(self, mode):
        """Set the serial assignment mode for select_next()."""
        if self.serial_mode != mode:
            self.serial_mode = mode
            self._widget_order_cache = None

    def _get_ordered_widgets(self):
        """Get widgets ordered according to serial_mode."""
        if self._widget_order_cache is not None:
            return self._widget_order_cache

        if self.serial_mode == SerialMode.TOP_TO_BOTTOM:
            # (y, x) ordering - Vial default
            ordered = sorted(self.widgets, key=lambda w: (w.y, w.x))
        elif self.serial_mode == SerialMode.LEFT_TO_RIGHT:
            # (x, y) ordering
            ordered = sorted(self.widgets, key=lambda w: (w.x, w.y))
        elif self.serial_mode == SerialMode.CLUSTER:
            # By finger cluster with proper direction order within each cluster
            # Build set of existing keymap IDs
            existing_ids = set()
            id_to_widget = {}
            for w in self.widgets:
                if w.desc.row is not None:
                    keymap_id = w.desc.row * self._matrix_cols + w.desc.col
                    existing_ids.add(keymap_id)
                    id_to_widget[keymap_id] = w
            # Get cluster order for existing keys
            cluster_order = get_svalboard_cluster_order(existing_ids)
            ordered = [id_to_widget[kid] for kid in cluster_order]
            # Add any widgets not in the cluster order (non-matrix keys)
            for w in self.widgets:
                if w not in ordered:
                    ordered.append(w)
        elif self.serial_mode == SerialMode.DIRECTION:
            # Svalboard direction ordering from hardcoded list
            id_to_widget = {}
            for w in self.widgets:
                if w.desc.row is not None:
                    keymap_id = w.desc.row * self._matrix_cols + w.desc.col
                    id_to_widget[keymap_id] = w
            ordered = []
            for keymap_id in SVALBOARD_DIRECTION_ORDER:
                if keymap_id in id_to_widget:
                    ordered.append(id_to_widget[keymap_id])
            # Add any widgets not in the direction order list
            for w in self.widgets:
                if w not in ordered:
                    ordered.append(w)
        else:
            ordered = self.widgets

        self._widget_order_cache = ordered
        return ordered

    def select_next(self):
        """Selects next key based on serial assignment mode."""
        ordered = self._get_ordered_widgets()
        if not ordered:
            return

        keys_looped = ordered + [ordered[0]]
        for x, key in enumerate(keys_looped):
            if key == self.active_key:
                self.active_key = keys_looped[x + 1]
                self.active_mask = False
                self.clicked.emit()
                return

    def deselect(self):
        if self.active_key is not None:
            self.active_key = None
            self.deselected.emit()
            self.update()

    def event(self, ev):
        if not self.enabled:
            super().event(ev)

        if ev.type() == QEvent.ToolTip:
            key = self.hit_test(ev.pos())[0]
            if key is not None:
                QToolTip.showText(ev.globalPos(), key.tooltip)
            else:
                QToolTip.hideText()
        elif ev.type() == QEvent.LayoutRequest:
            self.update_layout()
        elif ev.type() == QEvent.MouseButtonDblClick and self.active_key:
            self.anykey.emit()
        return super().event(ev)

    def set_enabled(self, val):
        self.enabled = val

    def set_scale(self, scale):
        if self.scale != scale:
            self.scale = scale
            self.update_layout()

    def get_scale(self):
        return self.scale
