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

---

## 0x00: Get Protocol Info

**Request:** `[0xDF] [0x00]`

**Response:** `[0xDF] [0x00] [ver0-3] [td_count] [combo_count] [ko_count] [ark_count] [flags] [uid0-7]`

- `ver0-3`: uint32_t protocol version (little-endian)
- `td_count`: uint8_t tap dance slot count
- `combo_count`: uint8_t combo slot count
- `ko_count`: uint8_t key override slot count
- `ark_count`: uint8_t alt repeat key slot count
- `flags`: uint8_t feature flags
- `uid0-7`: 8-byte keyboard UID

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

## Entry Sizes Summary

| Feature | Entry Size | Enabled Flag |
|---------|------------|--------------|
| Tap Dance | 10 bytes | `custom_tapping_term & 0x8000` |
| Combo | 12 bytes | `custom_combo_term & 0x8000` |
| Key Override | 12 bytes | `options & 0x80` |
| Alt Repeat Key | 6 bytes | `options & 0x08` |

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
