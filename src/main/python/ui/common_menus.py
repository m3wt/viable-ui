# SPDX-License-Identifier: GPL-2.0-or-later
"""
VIA3 common menu definitions.

These match the built-in menus from VIA:
https://caniusevia.com/docs/built_in_menus

Channel IDs (from via.h):
- 0: id_custom_channel (keyboard-specific)
- 1: id_qmk_backlight_channel
- 2: id_qmk_rgblight_channel
- 3: id_qmk_rgb_matrix_channel
- 4: id_qmk_audio_channel
- 5: id_qmk_led_matrix_channel
"""

# QMK Backlight - Channel 1
QMK_BACKLIGHT = {
    "label": "Lighting",
    "content": [
        {
            "label": "Backlight",
            "content": [
                {
                    "label": "Brightness",
                    "type": "range",
                    "options": [0, 255],
                    "content": ["id_qmk_backlight_brightness", 1, 1]
                },
                {
                    "label": "Effect",
                    "type": "dropdown",
                    "options": [
                        ["Off", 0],
                        ["Breathing", 1]
                    ],
                    "content": ["id_qmk_backlight_effect", 1, 2]
                }
            ]
        }
    ]
}

# QMK RGBLight - Channel 2
QMK_RGBLIGHT = {
    "label": "Lighting",
    "content": [
        {
            "label": "Underglow",
            "content": [
                {
                    "label": "Brightness",
                    "type": "range",
                    "options": [0, 255],
                    "content": ["id_qmk_rgblight_brightness", 2, 1]
                },
                {
                    "label": "Effect",
                    "type": "dropdown",
                    "options": [
                        ["All Off", 0],
                        ["Solid Color", 1],
                        ["Breathing 1", 2],
                        ["Breathing 2", 3],
                        ["Breathing 3", 4],
                        ["Breathing 4", 5],
                        ["Rainbow Mood 1", 6],
                        ["Rainbow Mood 2", 7],
                        ["Rainbow Mood 3", 8],
                        ["Rainbow Swirl 1", 9],
                        ["Rainbow Swirl 2", 10],
                        ["Rainbow Swirl 3", 11],
                        ["Rainbow Swirl 4", 12],
                        ["Rainbow Swirl 5", 13],
                        ["Rainbow Swirl 6", 14],
                        ["Snake 1", 15],
                        ["Snake 2", 16],
                        ["Snake 3", 17],
                        ["Snake 4", 18],
                        ["Snake 5", 19],
                        ["Snake 6", 20],
                        ["Knight 1", 21],
                        ["Knight 2", 22],
                        ["Knight 3", 23],
                        ["Christmas", 24],
                        ["Gradient 1", 25],
                        ["Gradient 2", 26],
                        ["Gradient 3", 27],
                        ["Gradient 4", 28],
                        ["Gradient 5", 29],
                        ["Gradient 6", 30],
                        ["Gradient 7", 31],
                        ["Gradient 8", 32],
                        ["Gradient 9", 33],
                        ["Gradient 10", 34],
                        ["RGB Test", 35],
                        ["Alternating", 36],
                        ["Twinkle 1", 37],
                        ["Twinkle 2", 38],
                        ["Twinkle 3", 39],
                        ["Twinkle 4", 40],
                        ["Twinkle 5", 41],
                        ["Twinkle 6", 42]
                    ],
                    "content": ["id_qmk_rgblight_effect", 2, 2]
                },
                {
                    "label": "Effect Speed",
                    "type": "range",
                    "options": [0, 255],
                    "content": ["id_qmk_rgblight_effect_speed", 2, 3]
                },
                {
                    "label": "Color",
                    "type": "color",
                    "content": ["id_qmk_rgblight_color", 2, 4]
                }
            ]
        }
    ]
}

# QMK RGB Matrix - Channel 3
QMK_RGB_MATRIX = {
    "label": "Lighting",
    "content": [
        {
            "label": "Per-Key RGB",
            "content": [
                {
                    "label": "Brightness",
                    "type": "range",
                    "options": [0, 255],
                    "content": ["id_qmk_rgb_matrix_brightness", 3, 1]
                },
                {
                    "label": "Effect",
                    "type": "dropdown",
                    "options": [
                        ["All Off", 0],
                        ["Solid Color", 1],
                        ["Alphas Mods", 2],
                        ["Gradient Up Down", 3],
                        ["Gradient Left Right", 4],
                        ["Breathing", 5],
                        ["Band Sat", 6],
                        ["Band Val", 7],
                        ["Band Pinwheel Sat", 8],
                        ["Band Pinwheel Val", 9],
                        ["Band Spiral Sat", 10],
                        ["Band Spiral Val", 11],
                        ["Cycle All", 12],
                        ["Cycle Left Right", 13],
                        ["Cycle Up Down", 14],
                        ["Cycle Out In", 15],
                        ["Cycle Out In Dual", 16],
                        ["Rainbow Moving Chevron", 17],
                        ["Cycle Pinwheel", 18],
                        ["Cycle Spiral", 19],
                        ["Dual Beacon", 20],
                        ["Rainbow Beacon", 21],
                        ["Rainbow Pinwheels", 22],
                        ["Raindrops", 23],
                        ["Jellybean Raindrops", 24],
                        ["Hue Breathing", 25],
                        ["Hue Pendulum", 26],
                        ["Hue Wave", 27],
                        ["Pixel Fractal", 28],
                        ["Pixel Flow", 29],
                        ["Pixel Rain", 30],
                        ["Typing Heatmap", 31],
                        ["Digital Rain", 32],
                        ["Solid Reactive Simple", 33],
                        ["Solid Reactive", 34],
                        ["Solid Reactive Wide", 35],
                        ["Solid Reactive Multiwide", 36],
                        ["Solid Reactive Cross", 37],
                        ["Solid Reactive Multicross", 38],
                        ["Solid Reactive Nexus", 39],
                        ["Solid Reactive Multinexus", 40],
                        ["Splash", 41],
                        ["Multisplash", 42],
                        ["Solid Splash", 43],
                        ["Solid Multisplash", 44]
                    ],
                    "content": ["id_qmk_rgb_matrix_effect", 3, 2]
                },
                {
                    "label": "Effect Speed",
                    "type": "range",
                    "options": [0, 255],
                    "content": ["id_qmk_rgb_matrix_effect_speed", 3, 3]
                },
                {
                    "label": "Color",
                    "type": "color",
                    "content": ["id_qmk_rgb_matrix_color", 3, 4]
                }
            ]
        }
    ]
}

# QMK Audio - Channel 4
QMK_AUDIO = {
    "label": "Audio",
    "content": [
        {
            "label": "General",
            "content": [
                {
                    "label": "Enable Audio",
                    "type": "toggle",
                    "content": ["id_qmk_audio_enable", 4, 1]
                },
                {
                    "label": "Enable Audio Clicky",
                    "type": "toggle",
                    "content": ["id_qmk_audio_clicky_enable", 4, 2]
                }
            ]
        }
    ]
}

# QMK LED Matrix - Channel 5
QMK_LED_MATRIX = {
    "label": "Lighting",
    "content": [
        {
            "label": "LED Matrix",
            "content": [
                {
                    "label": "Brightness",
                    "type": "range",
                    "options": [0, 255],
                    "content": ["id_qmk_led_matrix_brightness", 5, 1]
                },
                {
                    "label": "Effect",
                    "type": "dropdown",
                    "options": [
                        ["All Off", 0],
                        ["Solid", 1],
                        ["Alphas Mods", 2],
                        ["Breathing", 3],
                        ["Band", 4],
                        ["Band Pinwheel", 5],
                        ["Band Spiral", 6],
                        ["Cycle Left Right", 7],
                        ["Cycle Up Down", 8],
                        ["Cycle Out In", 9],
                        ["Dual Beacon", 10],
                        ["Wave Left Right", 11],
                        ["Wave Up Down", 12]
                    ],
                    "content": ["id_qmk_led_matrix_effect", 5, 2]
                },
                {
                    "label": "Effect Speed",
                    "type": "range",
                    "options": [0, 255],
                    "content": ["id_qmk_led_matrix_effect_speed", 5, 3]
                }
            ]
        }
    ]
}

# Combined backlight + rgblight (avoids duplicate "Lighting" tabs)
QMK_BACKLIGHT_RGBLIGHT = {
    "label": "Lighting",
    "content": [
        QMK_BACKLIGHT["content"][0],  # Backlight section
        QMK_RGBLIGHT["content"][0]    # Underglow section
    ]
}

# Registry of common menus
COMMON_MENUS = {
    "qmk_backlight": QMK_BACKLIGHT,
    "qmk_rgblight": QMK_RGBLIGHT,
    "qmk_rgb_matrix": QMK_RGB_MATRIX,
    "qmk_audio": QMK_AUDIO,
    "qmk_led_matrix": QMK_LED_MATRIX,
    "qmk_backlight_rgblight": QMK_BACKLIGHT_RGBLIGHT,
}


def resolve_common_menu(name: str) -> dict:
    """Resolve a common menu name to its definition."""
    return COMMON_MENUS.get(name)
