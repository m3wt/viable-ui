# GUI Protocol Understanding

Two protocols are used:
1. **0xDF (Viable)** - Keyboard-independent dynamic features (tap dance, combos, key overrides)
2. **VIA custom values (0x07/0x08/0x09)** - Keyboard-specific settings (Svalboard DPI, layer colors, etc.)

---

## Viable Protocol (0xDF)

Direct protocol for dynamic features. Packet format:

```
Request:  [0xDF] [cmd] [data...]
Response: [0xDF] [cmd] [data...]
```

All multi-byte values are little-endian.

---

## Viable Commands (0xDF)

From `viable.h`:

| ID | Name | Direction |
|----|------|-----------|
| 0x00 | Get Protocol Info | GET |
| 0x01 | Tap Dance Get | GET |
| 0x02 | Tap Dance Set | SET |
| 0x03 | Combo Get | GET |
| 0x04 | Combo Set | SET |
| 0x05 | Key Override Get | GET |
| 0x06 | Key Override Set | SET |
| 0x07 | Alt Repeat Key Get | GET |
| 0x08 | Alt Repeat Key Set | SET |
| 0x09 | One Shot Get | GET |
| 0x0A | One Shot Set | SET |
| 0x0B | Save to EEPROM | — |
| 0x0C | Reset to Defaults | — |
| 0x0D | Get Definition Size | GET |
| 0x0E | Get Definition Chunk | GET |
| 0x10 | QMK Settings Query | GET |
| 0x11 | QMK Settings Get | GET |
| 0x12 | QMK Settings Set | SET |
| 0x13 | QMK Settings Reset | — |
| 0x14 | Leader Get | GET |
| 0x15 | Leader Set | SET |
| 0x16 | Layer State Get | GET |
| 0x17 | Layer State Set | SET |
| 0x18 | Fragment Get Hardware | GET |
| 0x19 | Fragment Get Selections | GET |
| 0x1A | Fragment Set Selections | SET |

---

## 0x00: Get Protocol Info

**Request:** `[0xDF] [0x00]`

**Response:** `[0xDF] [0x00] [ver0-3] [uid0-7] [flags]`

- `ver0-3`: uint32_t protocol version (little-endian), offset 2-5
- `uid0-7`: 8-byte keyboard UID, offset 6-13 (for save file matching)
- `flags`: uint8_t feature flags, offset 14

**Feature flags:**
| Bit | Feature |
|-----|---------|
| 0 | Tap Dance |
| 1 | Combo |
| 2 | Key Override |
| 3 | Leader |

**Note:** Feature counts (tap dance, combo, key override, alt repeat key, leader) are no longer
in the protocol info response. They are now defined in the keyboard's `viable.json` under the
`"viable"` object, providing unlimited extensibility:

```json
{
  "name": "Svalboard",
  "viable": {
    "tap_dance": 50,
    "combo": 50,
    "key_override": 30,
    "alt_repeat_key": 16,
    "leader": 32
  },
  ...
}
```

Features not listed get 0 entries (disabled) and their code is excluded from the firmware build.

---

## 0x01: Tap Dance Get

**Request:** `[0xDF] [0x01] [index]`

**Response:** `[0xDF] [0x01] [index] [10 bytes entry]`

**Entry format (10 bytes):**
```c
struct tap_dance_entry_t {
    uint16_t on_tap;
    uint16_t on_hold;
    uint16_t on_double_tap;
    uint16_t on_tap_hold;
    uint16_t custom_tapping_term;  // bit 15 = enabled, bits 0-14 = ms
};
```

**Enabled:** When `custom_tapping_term & 0x8000`

---

## 0x02: Tap Dance Set

**Request:** `[0xDF] [0x02] [index] [10 bytes entry]`

**Response:** `[0xDF] [0x02] [status]`

---

## 0x03: Combo Get

**Request:** `[0xDF] [0x03] [index]`

**Response:** `[0xDF] [0x03] [index] [12 bytes entry]`

**Entry format (12 bytes):**
```c
struct combo_entry_t {
    uint16_t input[4];          // trigger keys, 0x0000 = unused
    uint16_t output;            // output keycode
    uint16_t custom_combo_term; // bit 15 = enabled, bits 0-14 = ms
};
```

**Enabled:** When `custom_combo_term & 0x8000`

---

## 0x04: Combo Set

**Request:** `[0xDF] [0x04] [index] [12 bytes entry]`

**Response:** `[0xDF] [0x04] [status]`

---

## 0x05: Key Override Get

**Request:** `[0xDF] [0x05] [index]`

**Response:** `[0xDF] [0x05] [index] [12 bytes entry]`

**Entry format (12 bytes):**
```c
struct key_override_entry_t {
    uint16_t trigger;           // trigger keycode
    uint16_t replacement;       // replacement keycode
    uint32_t layers;            // 32-bit layer mask
    uint8_t  trigger_mods;      // required modifiers
    uint8_t  negative_mod_mask; // modifiers that cancel override
    uint8_t  suppressed_mods;   // modifiers to suppress
    uint8_t  options;           // bit 7 = enabled
};
```

**Enabled:** When `options & 0x80`

---

## 0x06: Key Override Set

**Request:** `[0xDF] [0x06] [index] [12 bytes entry]`

**Response:** `[0xDF] [0x06] [status]`

---

## 0x07: Alt Repeat Key Get

**Request:** `[0xDF] [0x07] [index]`

**Response:** `[0xDF] [0x07] [index] [6 bytes entry]`

**Entry format (6 bytes):**
```c
struct alt_repeat_key_entry_t {
    uint16_t keycode;      // original keycode to match
    uint16_t alt_keycode;  // alternate keycode on repeat
    uint8_t  allowed_mods; // modifier mask for matching
    uint8_t  options;      // bit 3 = enabled
};
```

**Enabled:** When `options & 0x08`

---

## 0x08: Alt Repeat Key Set

**Request:** `[0xDF] [0x08] [index] [6 bytes entry]`

**Response:** `[0xDF] [0x08] [status]`

---

## 0x09: One Shot Get

**Request:** `[0xDF] [0x09]`

**Response:** `[0xDF] [0x09] [timeout_lo] [timeout_hi] [tap_toggle]`

- `timeout`: uint16_t ms (0 = disabled)
- `tap_toggle`: uint8_t number of taps to toggle

---

## 0x0A: One Shot Set

**Request:** `[0xDF] [0x0A] [timeout_lo] [timeout_hi] [tap_toggle]`

**Response:** `[0xDF] [0x0A]`

---

## 0x0B: Save to EEPROM

**Request:** `[0xDF] [0x0B]`

**Response:** `[0xDF] [0x0B]`

---

## 0x0C: Reset to Defaults

**Request:** `[0xDF] [0x0C]`

**Response:** `[0xDF] [0x0C]`

---

## 0x0D: Get Definition Size

**Request:** `[0xDF] [0x0D]`

**Response:** `[0xDF] [0x0D] [size0] [size1] [size2] [size3]`

- `size`: uint32_t LZMA-compressed definition size (little-endian)

---

## 0x0E: Get Definition Chunk

**Request:** `[0xDF] [0x0E] [offset_lo] [offset_hi]`

**Response:** `[0xDF] [0x0E] [offset_lo] [offset_hi] [28 bytes data]`

Read chunks until offset >= size.

---

## 0x14: Leader Get

**Request:** `[0xDF] [0x14] [index]`

**Response:** `[0xDF] [0x14] [index] [14 bytes entry]`

**Entry format (14 bytes):**
```c
struct leader_entry_t {
    uint16_t sequence[5];  // Up to 5 trigger keys in order (0x0000 = unused/end)
    uint16_t output;       // Output keycode
    uint16_t options;      // bit 15 = enabled, bits 0-14 = reserved
};
```

**Enabled:** When `options & 0x8000`

---

## 0x15: Leader Set

**Request:** `[0xDF] [0x15] [index] [14 bytes entry]`

**Response:** `[0xDF] [0x15] [status]`

---

## 0x16: Layer State Get

Query the current active layer state.

**Request:** `[0xDF] [0x16]`

**Response:** `[0xDF] [0x16] [state0] [state1] [state2] [state3]`

- `state0-3`: uint32_t layer bitmask (little-endian)
  - Bit 0 = layer 0 active
  - Bit 1 = layer 1 active
  - etc.

**Example:** `0x05` (binary `0101`) means layers 0 and 2 are active.

---

## 0x17: Layer State Set

Set the active layer state.

**Request:** `[0xDF] [0x17] [state0] [state1] [state2] [state3]`

- `state0-3`: uint32_t layer bitmask (little-endian)

**Response:** `[0xDF] [0x17]`

**Note:** This directly sets `layer_state`, activating/deactivating layers.
Use with caution as it bypasses normal layer switching logic.

---

## 0x18: Fragment Get Hardware

Query hardware-detected fragments for each instance position.

**Request:** `[0xDF] [0x18]`

**Response:** `[0xDF] [0x18] [count] [21 bytes data]`

- `count`: Number of selectable instances
- `data`: Fixed 21-byte array, one byte per instance position
  - Each byte is a **fragment ID** (from fragment definition's `id` field)
  - `0xFF` = no hardware detection / unused slot

**Note:** Hardware detection is optional. Keyboards without hardware detection
return `0xFF` for all positions. The GUI uses this to show "detected: X" labels
and optionally lock selections when `allow_override: false`.

---

## 0x19: Fragment Get Selections

Query user's saved fragment selections from EEPROM.

**Request:** `[0xDF] [0x19]`

**Response:** `[0xDF] [0x19] [count] [21 bytes data]`

- `count`: Number of selectable instances
- `data`: Fixed 21-byte array, one byte per instance position
  - Each byte is an **option index** (0-254) into the instance's `fragment_options` array
  - `0xFF` = no selection (use default or hardware detection)

**Important:** EEPROM stores option indices, NOT fragment IDs. Option index 0
means the first option in `fragment_options`, index 1 means the second, etc.

---

## 0x1A: Fragment Set Selections

Save user's fragment selections to EEPROM.

**Request:** `[0xDF] [0x1A] [count] [21 bytes data]`

- `count`: Number of selectable instances
- `data`: Fixed 21-byte array, one byte per instance position
  - Each byte is an **option index** (0-254) into the instance's `fragment_options` array
  - `0xFF` = clear selection (use default or hardware detection)

**Response:** `[0xDF] [0x1A] [status]`

- `status`: `0x00` = success

---

## Entry Sizes Summary

| Feature | Entry Size | Enabled Flag |
|---------|------------|--------------|
| Tap Dance | 10 bytes | `custom_tapping_term & 0x8000` |
| Combo | 12 bytes | `custom_combo_term & 0x8000` |
| Key Override | 12 bytes | `options & 0x80` |
| Alt Repeat Key | 6 bytes | `options & 0x08` |
| Leader | 14 bytes | `options & 0x8000` |

---

## VIA Custom Values (Keyboard-Specific)

For keyboard-specific settings (not Viable), use VIA's custom value protocol:

```
SET: [0x07] [channel] [value_id] [data...]
GET: [0x08] [channel] [value_id] [data...]
SAVE: [0x09] [channel]
```

Channel 0x00 = keyboard custom settings.

See `keyboards/svalboard/svalboard.c` for reference implementation with value IDs for DPI, scroll, automouse, layer colors, etc.

---

## Fragment Composition (JSON)

Fragments enable modular keyboard layouts where physical components can be swapped.
The JSON definition includes two sections:

### `fragments` section

Defines available fragment types with their visual layout (KLE) and unique ID:

```json
{
  "fragments": {
    "finger_5": {
      "id": 0,
      "description": "5-key finger cluster (no 2S)",
      "kle": [...]
    },
    "thumb_left": {
      "id": 2,
      "description": "Left thumb cluster (6 keys)",
      "kle": [...]
    }
  }
}
```

- `id`: Numeric fragment ID (0-254) used in hardware detection protocol
- `description`: Human-readable name shown in GUI
- `kle`: KLE layout data for visual rendering

### `composition.instances` section

Defines where fragments are placed and what options are available:

```json
{
  "composition": {
    "instances": [
      {
        "id": "left_pinky",
        "fragment_options": [
          {
            "fragment": "finger_5",
            "placement": {"x": 0, "y": 1.5},
            "matrix_map": [[4,3], [4,4], [4,2], [4,1], [4,0]]
          },
          {
            "fragment": "finger_6",
            "placement": {"x": 0, "y": 1.5},
            "matrix_map": [[4,3], [4,4], [4,2], [4,1], [4,0], [4,5]]
          }
        ]
      }
    ]
  }
}
```

- `id`: String identifier for the instance position (used in keymap files)
- `fragment_options`: Array of available fragments for this position
  - **First option is the default** (option index 0)
  - `fragment`: Reference to fragment name in `fragments` section
  - `placement`: X/Y offset for visual positioning
  - `matrix_map`: Array of [row, col] pairs mapping keys to matrix positions
- `allow_override`: If `false`, hardware detection cannot be overridden by user

### Resolution Priority

When determining which fragment to display:

1. If hardware detected AND `allow_override: false`: hardware wins
2. Keymap file selection (loaded .vil file)
3. EEPROM selection (user's saved choice)
4. Hardware detection (if `allow_override: true`)
5. Default (first option in `fragment_options`)
