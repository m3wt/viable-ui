# SPDX-License-Identifier: GPL-2.0-or-later

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTabWidget, QWidget, QScrollArea, QApplication, QVBoxLayout, QHBoxLayout, \
    QPushButton, QLabel, QFrame, QGridLayout, QSizePolicy
from PyQt5.QtGui import QPalette

from constants import KEYCODE_BTN_RATIO
from widgets.display_keyboard import DisplayKeyboard
from widgets.display_keyboard_defs import ansi_100, ansi_80, ansi_70
from widgets.flowlayout import FlowLayout
from keycodes.keycodes import KEYCODES_BASIC, KEYCODES_ISO, KEYCODES_MACRO, KEYCODES_LAYERS, KEYCODES_QUANTUM, \
    KEYCODES_BOOT, KEYCODES_MODIFIERS, \
    KEYCODES_BACKLIGHT, KEYCODES_MEDIA, KEYCODES_SPECIAL, KEYCODES_SHIFTED, KEYCODES_USER, Keycode, \
    KEYCODES_TAP_DANCE, KEYCODES_MIDI, KEYCODES_BASIC_NUMPAD, KEYCODES_BASIC_NAV, KEYCODES_ISO_KR, \
    KEYCODES_JOYSTICK, KEYCODES_PROGRAMMABLE_BUTTON, KEYCODES_STENO, \
    KEYCODES_STENO_CONTROL, KEYCODES_STENO_LEFT, KEYCODES_STENO_CENTER, KEYCODES_STENO_RIGHT
from widgets.square_button import SquareButton
from util import tr, KeycodeDisplay


def get_layer_keycodes_by_section():
    """Return layer keycodes organized by function type, no headers"""
    sections = [
        ("MO", []),      # Momentary
        ("TG", []),      # Toggle
        ("TT", []),      # Tap Toggle
        ("OSL", []),     # One Shot Layer
        ("TO", []),      # Turn On
        ("LT", []),      # Layer Tap
        ("Other", []),
        ("DF", []),      # Default Layer - less used, at bottom
        ("PDF", []),     # Previous Default Layer - less used, at bottom
    ]

    section_map = {
        "MO(": 0,
        "TG(": 1,
        "TT(": 2,
        "OSL(": 3,
        "TO(": 4,
        "LT": 5,
        "DF(": 7,
        "PDF(": 8,
    }

    for kc in KEYCODES_LAYERS:
        placed = False
        for prefix, idx in section_map.items():
            if kc.qmk_id.startswith(prefix):
                sections[idx][1].append(kc)
                placed = True
                break
        if not placed:
            sections[6][1].append(kc)  # Other

    # Filter out empty sections
    return [(name, codes) for name, codes in sections if codes]


def get_media_keycodes_by_section():
    """Return media/mouse keycodes organized by category with headers"""
    mouse_button_ids = {"KC_BTN1", "KC_BTN2", "KC_BTN3", "KC_BTN4", "KC_BTN5",
                        "KC_BTN6", "KC_BTN7", "KC_BTN8"}
    mouse_other_ids = {"KC_MS_U", "KC_MS_D", "KC_MS_L", "KC_MS_R",
                       "KC_WH_U", "KC_WH_D", "KC_WH_L", "KC_WH_R",
                       "KC_ACL0", "KC_ACL1", "KC_ACL2"}
    media_ids = {"KC_MPRV", "KC_MNXT", "KC_MUTE", "KC_VOLD", "KC_VOLU", "KC__VOLDOWN",
                 "KC__VOLUP", "KC_MSTP", "KC_MPLY", "KC_MRWD", "KC_MFFD", "KC_EJCT"}
    app_ids = {"KC_CALC", "KC_MAIL", "KC_MSEL", "KC_MYCM", "KC_WSCH", "KC_WHOM",
               "KC_WBAK", "KC_WFWD", "KC_WSTP", "KC_WREF", "KC_WFAV"}
    system_ids = {"KC_PWR", "KC_SLEP", "KC_WAKE", "KC_BRIU", "KC_BRID"}

    sections = [
        ("Mouse Buttons", []),
        ("Mouse", []),
        ("Media", []),
        ("Apps & Browser", []),
        ("System", []),
        ("Other", []),
    ]

    for kc in KEYCODES_MEDIA:
        if kc.qmk_id in mouse_button_ids or kc.qmk_id.startswith("KC_BTN"):
            sections[0][1].append(kc)
        elif kc.qmk_id in mouse_other_ids or any(kc.qmk_id.startswith(a) for a in ["KC_MS_", "KC_WH_", "KC_ACL"]):
            sections[1][1].append(kc)
        elif kc.qmk_id in media_ids:
            sections[2][1].append(kc)
        elif kc.qmk_id in app_ids:
            sections[3][1].append(kc)
        elif kc.qmk_id in system_ids:
            sections[4][1].append(kc)
        else:
            sections[5][1].append(kc)

    return [(name, codes) for name, codes in sections if codes]


def get_modifier_keycodes_by_section():
    """Return modifier-related keycodes: OSM (Callum mods), Space Cadet"""
    sections = [
        ("One-Shot LHS (Callum mods)", []),
        ("One-Shot RHS (Callum mods)", []),
        ("Space Cadet", []),
    ]

    for kc in KEYCODES_MODIFIERS:
        qmk = kc.qmk_id
        # Skip mod-tap keys - ModsBar handles these now
        if qmk.endswith("_T(kc)"):
            continue
        # Skip masked modifier wrappers
        if kc.masked:
            continue

        if qmk.startswith("OSM("):
            if "MOD_R" in qmk and "MOD_L" not in qmk:
                sections[1][1].append(kc)  # RHS
            else:
                sections[0][1].append(kc)  # LHS
        elif qmk.startswith("KC_"):
            # Space cadet keys (KC_LSPO, KC_RSPC, etc.)
            sections[2][1].append(kc)

    return [(name, codes) for name, codes in sections if codes]


def get_settings_keycodes_by_section():
    """Return settings/magic keycodes organized by category"""
    sections = [
        ("Boot & Lock", []),
        ("Magic - Caps/Ctrl", []),
        ("Magic - Ctrl/GUI", []),
        ("Magic - Alt/GUI", []),
        ("Magic - Other", []),
        ("Audio", []),
        ("Haptic", []),
        ("Auto-Shift", []),
        ("Other", []),
    ]

    for kc in KEYCODES_BOOT:
        sections[0][1].append(kc)

    for kc in KEYCODES_QUANTUM:
        qmk = kc.qmk_id
        if qmk.startswith("QK_LOCK") or qmk.startswith("QK_SECURE"):
            sections[0][1].append(kc)
        elif "CAPSLOCK" in qmk or "CL_" in qmk:
            sections[1][1].append(kc)
        elif "CTL_GUI" in qmk or "LCTL_LGUI" in qmk or "RCTL_RGUI" in qmk or qmk in ["CG_SWAP", "CG_NORM", "CG_TOGG", "LCG_SWP", "LCG_NRM", "RCG_SWP", "RCG_NRM"]:
            sections[2][1].append(kc)
        elif "ALT_GUI" in qmk or "LALT_LGUI" in qmk or "RALT_RGUI" in qmk or qmk in ["AG_SWAP", "AG_NORM", "AG_TOGG", "LAG_SWP", "LAG_NRM", "RAG_SWP", "RAG_NRM"]:
            sections[3][1].append(kc)
        elif qmk.startswith("MAGIC_") or qmk.startswith("GUI_") or qmk.startswith("GE_") or qmk.startswith("BS_") or qmk.startswith("NK_") or qmk.startswith("EH_"):
            sections[4][1].append(kc)
        elif qmk.startswith("AU_") or qmk.startswith("MU_") or qmk.startswith("CK_") or qmk.startswith("CLICKY"):
            sections[5][1].append(kc)
        elif qmk.startswith("HPT_"):
            sections[6][1].append(kc)
        elif qmk.startswith("KC_AS") or "AUTO" in qmk.upper() and "SHIFT" in qmk.upper():
            sections[7][1].append(kc)
        else:
            sections[8][1].append(kc)

    return [(name, codes) for name, codes in sections if codes]


class ModsBar(QWidget):
    """Compact modifier toggle bar with special keys (KC_NO, KC_TRNS)"""

    keycode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.mods = {
            'shift': False,
            'ctrl': False,
            'gui': False,
            'alt': False,
            'right': False,
            'mod_tap': False,
        }

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        # Mods label
        layout.addWidget(QLabel("Mods:"))

        # Right-hand toggle (at start to set context)
        self.right_btn = QPushButton("RHS")
        self.right_btn.setCheckable(True)
        self.right_btn.setFixedHeight(24)
        self.right_btn.setMinimumWidth(36)
        self.right_btn.setToolTip("Use right-hand modifiers (RShift, RCtrl, etc.)")
        self.right_btn.clicked.connect(lambda checked: self._toggle_mod('right', checked))
        self.right_btn.setStyleSheet("QPushButton:checked { background-color: #9b59b6; color: #ffffff; }")
        layout.addWidget(self.right_btn)

        # Modifier toggle buttons
        self.mod_buttons = {}
        for mod, label in [('shift', 'Shift'), ('ctrl', 'Ctrl'), ('gui', 'GUI'), ('alt', 'Alt')]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setMinimumWidth(40)
            btn.clicked.connect(lambda checked, m=mod: self._toggle_mod(m, checked))
            btn.setStyleSheet("QPushButton:checked { background-color: #3498db; color: #ffffff; }")
            self.mod_buttons[mod] = btn
            layout.addWidget(btn)

        # Mod-Tap toggle
        self.mod_tap_btn = QPushButton("Mod-Tap")
        self.mod_tap_btn.setCheckable(True)
        self.mod_tap_btn.setFixedHeight(24)
        self.mod_tap_btn.setMinimumWidth(56)
        self.mod_tap_btn.setToolTip("Mod-Tap: modifier when held, key when tapped")
        self.mod_tap_btn.clicked.connect(lambda checked: self._toggle_mod('mod_tap', checked))
        self.mod_tap_btn.setStyleSheet("QPushButton:checked { background-color: #e67e22; color: #ffffff; }")
        layout.addWidget(self.mod_tap_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # Special label
        layout.addWidget(QLabel("Special:"))

        # KC_NO button (empty/disabled key)
        no_btn = QPushButton(" ")
        no_btn.setFixedSize(28, 24)
        no_btn.setToolTip("KC_NO - Disabled key")
        no_btn.clicked.connect(lambda: self.keycode_changed.emit("KC_NO"))
        layout.addWidget(no_btn)

        # KC_TRNS button (transparent)
        trns_btn = QPushButton("▽")
        trns_btn.setFixedSize(28, 24)
        trns_btn.setToolTip("KC_TRNS - Transparent (fall through to layer below)")
        trns_btn.clicked.connect(lambda: self.keycode_changed.emit("KC_TRNS"))
        layout.addWidget(trns_btn)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)

        # Custom Keycode button (opens Any dialog)
        custom_btn = QPushButton("Custom")
        custom_btn.setFixedHeight(24)
        custom_btn.setToolTip("Enter a custom keycode manually")
        custom_btn.clicked.connect(lambda: self.keycode_changed.emit("Any"))
        layout.addWidget(custom_btn)

        layout.addStretch()
        self.setLayout(layout)

    def _toggle_mod(self, mod, checked):
        self.mods[mod] = checked

    def wrap_keycode(self, keycode):
        """Wrap a keycode with active modifiers or mod-tap"""
        if not Keycode.is_basic(keycode):
            return keycode

        s = self.mods['shift']
        c = self.mods['ctrl']
        a = self.mods['alt']
        g = self.mods['gui']
        right = self.mods['right']
        mod_tap = self.mods['mod_tap']

        if not any([s, c, a, g]):
            return keycode

        if mod_tap:
            # Mod-Tap: use combined keycodes
            return self._get_mod_tap_keycode(s, c, a, g, right, keycode)
        else:
            # Regular modifier wrapping
            result = keycode
            prefix = "R" if right else "L"

            if s:
                result = f"{prefix}SFT({result})"
            if c:
                result = f"{prefix}CTL({result})"
            if a:
                result = f"{prefix}ALT({result})"
            if g:
                result = f"{prefix}GUI({result})"

            return result

    def _get_mod_tap_keycode(self, s, c, a, g, right, keycode):
        """Get the appropriate mod-tap keycode for the active modifiers"""
        # Build a key from the active mods (order: S, C, A, G)
        mods_key = (s, c, a, g)

        # Mapping of modifier combinations to keycode names
        # Left-hand variants
        left_map = {
            (True, False, False, False): "LSFT_T",
            (False, True, False, False): "LCTL_T",
            (False, False, True, False): "LALT_T",
            (False, False, False, True): "LGUI_T",
            (True, True, False, False): "C_S_T",  # or LCS_T
            (False, True, True, False): "LCA_T",
            (False, True, False, True): "LCG_T",
            (True, False, True, False): "LSA_T",
            (False, False, True, True): "LAG_T",
            (True, False, False, True): "SGUI_T",  # or LSG_T
            (True, True, True, False): "MEH_T",
            (False, True, True, True): "LCAG_T",
            (True, True, False, True): "LSCG_T",
            (True, False, True, True): "LSAG_T",
            (True, True, True, True): "ALL_T",
        }

        # Right-hand variants
        right_map = {
            (True, False, False, False): "RSFT_T",
            (False, True, False, False): "RCTL_T",
            (False, False, True, False): "RALT_T",
            (False, False, False, True): "RGUI_T",
            (True, True, False, False): "RSC_T",
            (False, True, True, False): "RCA_T",
            (False, True, False, True): "RCG_T",
            (True, False, True, False): "RSA_T",
            (False, False, True, True): "RAG_T",
            (True, False, False, True): "RSG_T",
            (True, True, True, False): "RSCA_T",
            (False, True, True, True): "RCAG_T",
            (True, True, False, True): "RSCG_T",
            (True, False, True, True): "RSAG_T",
            (True, True, True, True): "RSCAG_T",
        }

        mod_map = right_map if right else left_map
        mod_name = mod_map.get(mods_key)

        if mod_name:
            return f"{mod_name}({keycode})"
        return keycode

    def has_active_mods(self):
        return any([self.mods['shift'], self.mods['ctrl'], self.mods['gui'], self.mods['alt']])


class AlternativeDisplay(QWidget):

    keycode_changed = pyqtSignal(str)

    def __init__(self, kbdef, keycodes, prefix_buttons):
        super().__init__()

        self.kb_display = None
        self.keycodes = keycodes
        self.buttons = []

        self.key_layout = FlowLayout()

        if prefix_buttons:
            for title, code in prefix_buttons:
                btn = SquareButton()
                btn.setRelSize(KEYCODE_BTN_RATIO)
                btn.setText(title)
                # Emit code if it's a string, otherwise emit title
                emit_val = code if isinstance(code, str) else title
                btn.clicked.connect(lambda st, v=emit_val: self.keycode_changed.emit(v))
                self.key_layout.addWidget(btn)

        layout = QVBoxLayout()
        if kbdef:
            self.kb_display = DisplayKeyboard(kbdef)
            self.kb_display.keycode_changed.connect(self.keycode_changed)
            layout.addWidget(self.kb_display)
            layout.setAlignment(self.kb_display, Qt.AlignHCenter)
        layout.addLayout(self.key_layout)
        self.setLayout(layout)

    def recreate_buttons(self, keycode_filter):
        for btn in self.buttons:
            btn.hide()
            btn.deleteLater()
        self.buttons = []

        for keycode in self.keycodes:
            if keycode.hidden or not keycode_filter(keycode.qmk_id):
                continue
            btn = SquareButton()
            btn.setRelSize(KEYCODE_BTN_RATIO)
            btn.setToolTip(Keycode.tooltip(keycode.qmk_id))
            btn.clicked.connect(lambda st, k=keycode: self.keycode_changed.emit(k.qmk_id))
            btn.keycode = keycode
            self.key_layout.addWidget(btn)
            self.buttons.append(btn)

        self.relabel_buttons()

    def relabel_buttons(self):
        if self.kb_display:
            self.kb_display.relabel_buttons()

        KeycodeDisplay.relabel_buttons(self.buttons)

    def required_width(self):
        return self.kb_display.sizeHint().width() if self.kb_display else 0

    def required_height(self):
        """Return the height needed to display this alternative without scrolling"""
        height = 0
        if self.kb_display:
            height += self.kb_display.sizeHint().height()
        # Add flow layout height (estimate based on content)
        height += self.key_layout.heightForWidth(self.key_layout.geometry().width() or 400)
        return height

    def has_buttons(self):
        return len(self.buttons) > 0


class Tab(QScrollArea):

    keycode_changed = pyqtSignal(str)

    def __init__(self, parent, label, alts, prefix_buttons=None, with_mods_bar=False):
        super().__init__(parent)

        self.label = label
        self.mods_bar = None
        self.inner_scroll = None  # Only used when mods_bar is present

        self.scroll_content = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.alternatives = []
        for kb, keys in alts:
            alt = AlternativeDisplay(kb, keys, prefix_buttons)
            alt.keycode_changed.connect(self._on_keycode_changed)
            self.layout.addWidget(alt)
            self.alternatives.append(alt)

        self.scroll_content.setLayout(self.layout)

        if with_mods_bar:
            # With mods bar: container with mods bar at top, scrollable content below
            self.mods_bar = ModsBar()
            self.mods_bar.keycode_changed.connect(self.keycode_changed)

            self.inner_scroll = QScrollArea()
            self.inner_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.inner_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.inner_scroll.setWidgetResizable(True)
            self.inner_scroll.setWidget(self.scroll_content)
            self.inner_scroll.setFrameShape(QFrame.NoFrame)

            container_layout = QVBoxLayout()
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            container_layout.addWidget(self.mods_bar)
            container_layout.addWidget(self.inner_scroll, 1)

            container = QWidget()
            container.setLayout(container_layout)

            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setWidgetResizable(True)
            self.setFrameShape(QFrame.NoFrame)
            self.setWidget(container)
        else:
            # Without mods bar: simple scroll area (original behavior)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setWidgetResizable(True)
            self.setWidget(self.scroll_content)

    def _on_keycode_changed(self, keycode):
        """Handle keycode changes, wrapping with mods if active"""
        if self.mods_bar and self.mods_bar.has_active_mods():
            keycode = self.mods_bar.wrap_keycode(keycode)
        self.keycode_changed.emit(keycode)

    def recreate_buttons(self, keycode_filter):
        for alt in self.alternatives:
            alt.recreate_buttons(keycode_filter)
        self.setVisible(self.has_buttons())

    def relabel_buttons(self):
        for alt in self.alternatives:
            alt.relabel_buttons()

    def has_buttons(self):
        for alt in self.alternatives:
            if alt.has_buttons():
                return True
        return False

    def select_alternative(self):
        # hide everything first
        for alt in self.alternatives:
            alt.hide()

        scroll_area = self.inner_scroll if self.inner_scroll else self
        scroll_width = scroll_area.width() - scroll_area.verticalScrollBar().width()
        scroll_height = scroll_area.height()
        if self.mods_bar:
            scroll_height -= self.mods_bar.height()

        # Find first alternative that fits both width and height
        shown = False
        width_fits = []
        for alt in self.alternatives:
            if scroll_width > alt.required_width():
                width_fits.append(alt)
                # Check if it also fits height
                if scroll_height >= alt.required_height():
                    alt.show()
                    shown = True
                    break

        # If none fit both, show first that fits width (will scroll vertically)
        if not shown and width_fits:
            width_fits[0].show()
            shown = True

        # Fallback: always show last alternative (simplest layout) if nothing else fits
        if not shown and self.alternatives:
            self.alternatives[-1].show()

    def resizeEvent(self, evt):
        super().resizeEvent(evt)
        self.select_alternative()

    def showEvent(self, evt):
        super().showEvent(evt)
        # Defer selection to ensure layout is complete
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self.select_alternative)


class SimpleTab(Tab):

    def __init__(self, parent, label, keycodes):
        super().__init__(parent, label, [(None, keycodes)])


class StenoTab(QScrollArea):
    """Tab that displays steno keycodes in a grid matching the physical steno keyboard layout"""

    keycode_changed = pyqtSignal(str)

    # Left hand layout (row, col within left grid)
    LEFT_LAYOUT = [
        ("STN_N1", 0, 0), ("STN_N2", 0, 1), ("STN_N3", 0, 2), ("STN_N4", 0, 3), ("STN_N5", 0, 4),
        ("STN_S1", 1, 0), ("STN_TL", 1, 1), ("STN_PL", 1, 2), ("STN_HL", 1, 3),
        ("STN_S2", 2, 0), ("STN_KL", 2, 1), ("STN_WL", 2, 2), ("STN_RL", 2, 3),
        ("STN_A", 3, 2), ("STN_O", 3, 3),
    ]

    # Center column: * keys vertically (1-4 top to bottom)
    CENTER_LAYOUT = [
        ("STN_ST1", 0, 0),
        ("STN_ST2", 1, 0),
        ("STN_ST3", 2, 0),
        ("STN_ST4", 3, 0),
    ]

    # Right hand layout (row, col within right grid)
    # #6-#9 in number row, #A #B #C in column on right edge
    RIGHT_LAYOUT = [
        ("STN_N6", 0, 0), ("STN_N7", 0, 1), ("STN_N8", 0, 2), ("STN_N9", 0, 3), ("STN_NA", 0, 5),
        ("STN_FR", 1, 0), ("STN_PR", 1, 1), ("STN_LR", 1, 2), ("STN_TR", 1, 3), ("STN_DR", 1, 4), ("STN_NB", 1, 5),
        ("STN_RR", 2, 0), ("STN_BR", 2, 1), ("STN_GR", 2, 2), ("STN_SR", 2, 3), ("STN_ZR", 2, 4), ("STN_NC", 2, 5),
        ("STN_E", 3, 1), ("STN_U", 3, 2),
    ]

    def __init__(self, parent, label):
        super().__init__(parent)

        self.label = label
        self.buttons = []

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # Control row at top (Bolt, Gemini, etc.)
        self.control_layout = FlowLayout()
        main_layout.addLayout(self.control_layout)

        # Steno keyboard: left group | center #6 | right group
        hands_layout = QHBoxLayout()
        hands_layout.setSpacing(8)

        # Left hand grid
        self.left_grid = QGridLayout()
        self.left_grid.setSpacing(2)
        left_widget = QWidget()
        left_widget.setLayout(self.left_grid)
        left_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hands_layout.addWidget(left_widget, 0, Qt.AlignTop)

        # Center column: * keys vertically
        self.center_grid = QGridLayout()
        self.center_grid.setSpacing(2)
        center_widget = QWidget()
        center_widget.setLayout(self.center_grid)
        center_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hands_layout.addWidget(center_widget, 0, Qt.AlignTop)

        # Right hand grid
        self.right_grid = QGridLayout()
        self.right_grid.setSpacing(2)
        right_widget = QWidget()
        right_widget.setLayout(self.right_grid)
        right_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hands_layout.addWidget(right_widget, 0, Qt.AlignTop)

        hands_layout.addStretch()
        main_layout.addLayout(hands_layout)
        main_layout.addStretch()

        container = QWidget()
        container.setLayout(main_layout)
        self.setWidget(container)

    def _create_button(self, keycode, keycode_filter):
        """Create a steno key button"""
        if keycode.hidden or not keycode_filter(keycode.qmk_id):
            return None
        btn = SquareButton()
        btn.setRelSize(KEYCODE_BTN_RATIO)
        btn.setToolTip(Keycode.tooltip(keycode.qmk_id))
        btn.clicked.connect(lambda st, k=keycode: self.keycode_changed.emit(k.qmk_id))
        btn.keycode = keycode
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.buttons.append(btn)
        return btn

    def recreate_buttons(self, keycode_filter):
        # Clear existing buttons
        for btn in self.buttons:
            btn.hide()
            btn.deleteLater()
        self.buttons = []

        # Clear all layouts
        for layout in [self.control_layout, self.left_grid, self.center_grid, self.right_grid]:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        # Build keycode lookup
        all_steno = KEYCODES_STENO_LEFT + KEYCODES_STENO_CENTER + KEYCODES_STENO_RIGHT
        keycode_map = {kc.qmk_id: kc for kc in all_steno}

        # Control keycodes (Bolt, Gemini, etc.)
        for keycode in KEYCODES_STENO_CONTROL:
            btn = self._create_button(keycode, keycode_filter)
            if btn:
                self.control_layout.addWidget(btn)

        # Left hand
        for qmk_id, row, col in self.LEFT_LAYOUT:
            keycode = keycode_map.get(qmk_id)
            if keycode:
                btn = self._create_button(keycode, keycode_filter)
                if btn:
                    self.left_grid.addWidget(btn, row, col)

        # Center column: * keys
        for qmk_id, row, col in self.CENTER_LAYOUT:
            keycode = keycode_map.get(qmk_id)
            if keycode:
                btn = self._create_button(keycode, keycode_filter)
                if btn:
                    self.center_grid.addWidget(btn, row, col)

        # Right hand
        for qmk_id, row, col in self.RIGHT_LAYOUT:
            keycode = keycode_map.get(qmk_id)
            if keycode:
                btn = self._create_button(keycode, keycode_filter)
                if btn:
                    self.right_grid.addWidget(btn, row, col)

        self.relabel_buttons()

    def relabel_buttons(self):
        KeycodeDisplay.relabel_buttons(self.buttons)

    def has_buttons(self):
        return len(self.buttons) > 0

    def required_width(self):
        return 0

    def required_height(self):
        return 0


class SectionedTab(QScrollArea):
    """Tab that displays keycodes in labeled rows (label on left, buttons flowing right)"""

    keycode_changed = pyqtSignal(str)

    def __init__(self, parent, label, sections_or_func):
        """
        sections_or_func: list of (section_name, keycodes_list) tuples, or a callable that returns such a list
        """
        super().__init__(parent)

        self.label = label
        self.sections_func = sections_or_func if callable(sections_or_func) else lambda: sections_or_func
        self.buttons = []
        self.row_widgets = []

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(2)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)

        w = QWidget()
        w.setLayout(self.layout)
        self.setWidget(w)

    def recreate_buttons(self, keycode_filter):
        # Clear existing buttons and row widgets
        for btn in self.buttons:
            btn.hide()
            btn.deleteLater()
        self.buttons = []

        for widget in self.row_widgets:
            widget.hide()
            widget.deleteLater()
        self.row_widgets = []

        # Clear the layout
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get current sections
        sections = self.sections_func()

        for section_name, keycodes in sections:
            # Filter visible keycodes
            visible_keycodes = [kc for kc in keycodes if not kc.hidden and keycode_filter(kc.qmk_id)]
            if not visible_keycodes:
                continue

            # Row container
            row = QWidget()
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            # Label on left
            lbl = QLabel(section_name)
            lbl.setFixedWidth(32)
            lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
            row_layout.addWidget(lbl)

            # Buttons flow to the right
            for keycode in visible_keycodes:
                btn = SquareButton()
                btn.setRelSize(KEYCODE_BTN_RATIO)
                btn.setToolTip(Keycode.tooltip(keycode.qmk_id))
                btn.clicked.connect(lambda st, k=keycode: self.keycode_changed.emit(k.qmk_id))
                btn.keycode = keycode
                row_layout.addWidget(btn)
                self.buttons.append(btn)

            row_layout.addStretch()
            row.setLayout(row_layout)
            self.layout.addWidget(row)
            self.row_widgets.append(row)

        self.layout.addStretch()
        self.relabel_buttons()
        self.setVisible(self.has_buttons())

    def relabel_buttons(self):
        KeycodeDisplay.relabel_buttons(self.buttons)

    def has_buttons(self):
        return len(self.buttons) > 0

    def select_alternative(self):
        pass  # No alternatives in sectioned tab

    def resizeEvent(self, evt):
        super().resizeEvent(evt)


class HeaderedSectionedTab(QScrollArea):
    """Tab that displays keycodes in sections with headers above each section"""

    keycode_changed = pyqtSignal(str)

    def __init__(self, parent, label, sections_or_func):
        super().__init__(parent)

        self.label = label
        self.sections_func = sections_or_func if callable(sections_or_func) else lambda: sections_or_func
        self.buttons = []
        self.section_widgets = []

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(8)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)

        w = QWidget()
        w.setLayout(self.layout)
        self.setWidget(w)

    def recreate_buttons(self, keycode_filter):
        # Clear existing
        for btn in self.buttons:
            btn.hide()
            btn.deleteLater()
        self.buttons = []

        for widget in self.section_widgets:
            widget.hide()
            widget.deleteLater()
        self.section_widgets = []

        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sections = self.sections_func()

        for section_name, keycodes in sections:
            visible_keycodes = [kc for kc in keycodes if not kc.hidden and keycode_filter(kc.qmk_id)]
            if not visible_keycodes:
                continue

            # Section header
            header = QLabel(section_name)
            header.setStyleSheet("font-weight: bold; font-size: 12px; color: #888; margin-top: 4px;")
            self.layout.addWidget(header)
            self.section_widgets.append(header)

            # Flow layout for buttons
            flow_container = QWidget()
            flow = FlowLayout()
            flow.setSpacing(2)

            for keycode in visible_keycodes:
                btn = SquareButton()
                btn.setRelSize(KEYCODE_BTN_RATIO)
                btn.setToolTip(Keycode.tooltip(keycode.qmk_id))
                btn.clicked.connect(lambda st, k=keycode: self.keycode_changed.emit(k.qmk_id))
                btn.keycode = keycode
                flow.addWidget(btn)
                self.buttons.append(btn)

            flow_container.setLayout(flow)
            self.layout.addWidget(flow_container)
            self.section_widgets.append(flow_container)

        self.layout.addStretch()
        self.relabel_buttons()
        self.setVisible(self.has_buttons())

    def relabel_buttons(self):
        KeycodeDisplay.relabel_buttons(self.buttons)

    def has_buttons(self):
        return len(self.buttons) > 0

    def select_alternative(self):
        pass

    def resizeEvent(self, evt):
        super().resizeEvent(evt)


def keycode_filter_any(kc):
    return True


def keycode_filter_masked(kc):
    return Keycode.is_basic(kc)


class FilteredTabbedKeycodes(QTabWidget):

    keycode_changed = pyqtSignal(str)
    anykey = pyqtSignal()

    def __init__(self, parent=None, keycode_filter=keycode_filter_any):
        super().__init__(parent)

        self.keycode_filter = keycode_filter

        self.tabs = [
            Tab(self, "Basic", [
                (ansi_100, KEYCODES_SHIFTED + KEYCODES_ISO),
                (ansi_80, KEYCODES_BASIC_NUMPAD + KEYCODES_SHIFTED + KEYCODES_ISO),
                (ansi_70, KEYCODES_BASIC_NUMPAD + KEYCODES_BASIC_NAV + KEYCODES_SHIFTED + KEYCODES_ISO),
                (None, KEYCODES_BASIC + KEYCODES_SHIFTED + KEYCODES_ISO),
            ], prefix_buttons=[(" ", "KC_NO"), ("▽", "KC_TRNS")], with_mods_bar=True),
            SectionedTab(self, "Layers", get_layer_keycodes_by_section),
            HeaderedSectionedTab(self, "One Shot", get_modifier_keycodes_by_section),
            HeaderedSectionedTab(self, "App, Media and Mouse", get_media_keycodes_by_section),
            SimpleTab(self, "User", KEYCODES_USER),  # Renamed to "Svalboard" when Svalboard connected
            SimpleTab(self, "Backlight", KEYCODES_BACKLIGHT),
            SimpleTab(self, "Tap Dance", KEYCODES_TAP_DANCE),
            SimpleTab(self, "Macro", KEYCODES_MACRO),
            HeaderedSectionedTab(self, "Settings", get_settings_keycodes_by_section),
            SimpleTab(self, "MIDI", KEYCODES_MIDI),
            SimpleTab(self, "Joystick", KEYCODES_JOYSTICK),
            SimpleTab(self, "Prog. Button", KEYCODES_PROGRAMMABLE_BUTTON),
            StenoTab(self, "Steno"),
        ]

        for tab in self.tabs:
            tab.keycode_changed.connect(self.on_keycode_changed)

        self.recreate_keycode_buttons()
        KeycodeDisplay.notify_keymap_override(self)

    def on_keycode_changed(self, code):
        if code == "Any":
            self.anykey.emit()
        else:
            self.keycode_changed.emit(Keycode.normalize(code))

    def recreate_keycode_buttons(self):
        prev_tab = self.tabText(self.currentIndex()) if self.currentIndex() >= 0 else ""
        while self.count() > 0:
            self.removeTab(0)

        for tab in self.tabs:
            tab.recreate_buttons(self.keycode_filter)
            if tab.has_buttons():
                self.addTab(tab, tr("TabbedKeycodes", tab.label))
                if tab.label == prev_tab:
                    self.setCurrentIndex(self.count() - 1)

    def on_keymap_override(self):
        for tab in self.tabs:
            tab.relabel_buttons()

    def set_user_tab_label(self, label):
        """Update the User tab's label (e.g., to 'Svalboard' when Svalboard connected)"""
        for i, tab in enumerate(self.tabs):
            if tab.label == "User" or tab.label == "Svalboard":
                tab.label = label
                # Update the visible tab text if it's currently shown
                for tab_idx in range(self.count()):
                    if self.widget(tab_idx) == tab:
                        self.setTabText(tab_idx, tr("TabbedKeycodes", label))
                        break
                break


class TabbedKeycodes(QWidget):

    keycode_changed = pyqtSignal(str)
    anykey = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.target = None
        self.is_tray = False

        self.layout = QVBoxLayout()

        self.all_keycodes = FilteredTabbedKeycodes()
        self.basic_keycodes = FilteredTabbedKeycodes(keycode_filter=keycode_filter_masked)
        for opt in [self.all_keycodes, self.basic_keycodes]:
            opt.keycode_changed.connect(self.keycode_changed)
            opt.anykey.connect(self.anykey)
            self.layout.addWidget(opt)

        self.setLayout(self.layout)
        self.set_keycode_filter(keycode_filter_any)

    @classmethod
    def set_tray(cls, tray):
        cls.tray = tray

    @classmethod
    def open_tray(cls, target, keycode_filter=None):
        cls.tray.set_keycode_filter(keycode_filter)
        cls.tray.show()
        if cls.tray.target is not None and cls.tray.target != target:
            cls.tray.target.deselect()
        cls.tray.target = target

    @classmethod
    def close_tray(cls):
        if cls.tray.target is not None:
            cls.tray.target.deselect()
        cls.tray.target = None
        cls.tray.hide()

    def make_tray(self):
        self.is_tray = True
        TabbedKeycodes.set_tray(self)

        self.keycode_changed.connect(self.on_tray_keycode_changed)
        self.anykey.connect(self.on_tray_anykey)

    def on_tray_keycode_changed(self, kc):
        if self.target is not None:
            self.target.on_keycode_changed(kc)

    def on_tray_anykey(self):
        if self.target is not None:
            self.target.on_anykey()

    def recreate_keycode_buttons(self):
        for opt in [self.all_keycodes, self.basic_keycodes]:
            opt.recreate_keycode_buttons()

    def set_keycode_filter(self, keycode_filter):
        if keycode_filter == keycode_filter_masked:
            self.all_keycodes.hide()
            self.basic_keycodes.show()
        else:
            self.all_keycodes.show()
            self.basic_keycodes.hide()

    def set_user_tab_label(self, label):
        """Update the User tab's label (e.g., to 'Svalboard' when Svalboard connected)"""
        for opt in [self.all_keycodes, self.basic_keycodes]:
            opt.set_user_tab_label(label)

    @classmethod
    def update_user_tab_label(cls, is_svalboard):
        """Class method to update the User tab label for the tray and all instances"""
        label = "Svalboard" if is_svalboard else "User"
        if hasattr(cls, 'tray') and cls.tray:
            cls.tray.set_user_tab_label(label)
