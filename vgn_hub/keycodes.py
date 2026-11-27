"""Mouse button action tables, USB HID keycodes, and 4-byte ry_mouse codecs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionDef:
    """Predefined non-keyboard mouse button binding definition."""

    id: str
    category: str  # disable | mouse | dpi | scroll | media | system
    label_en: str
    label_vi: str
    raw: tuple[int, int, int, int]


PREDEFINED_ACTIONS: tuple[ActionDef, ...] = (
    ActionDef("disable", "disable", "Disable", "Vô hiệu hóa", (0, 0, 0, 0)),
    # Core mouse buttons
    ActionDef("mouse_left", "mouse", "Left Click", "Chuột trái", (1, 0, 240, 0)),
    ActionDef("mouse_right", "mouse", "Right Click", "Chuột phải", (1, 0, 241, 0)),
    ActionDef("mouse_middle", "mouse", "Middle Click", "Chuột giữa", (1, 0, 242, 0)),
    ActionDef("mouse_back", "mouse", "Mouse Back", "Quay lại (Back)", (1, 0, 243, 0)),
    ActionDef("mouse_forward", "mouse", "Mouse Forward", "Tiến tới (Forward)", (1, 0, 244, 0)),
    # DPI controls
    ActionDef("dpi_cycle", "dpi", "DPI Cycle", "Xoay vòng DPI", (20, 0, 0, 0)),
    ActionDef("dpi_inc", "dpi", "DPI +", "Tăng DPI", (20, 0, 1, 0)),
    ActionDef("dpi_dec", "dpi", "DPI -", "Giảm DPI", (20, 0, 2, 0)),
    # Scroll / tilt wheel
    ActionDef("scroll_up", "scroll", "Scroll Up", "Cuộn lên", (1, 0, 245, 1)),
    ActionDef("scroll_down", "scroll", "Scroll Down", "Cuộn xuống", (1, 0, 245, 255)),
    ActionDef("tilt_left", "scroll", "Tilt Left", "Nghiêng trái", (1, 0, 245, 0)),
    ActionDef("tilt_right", "scroll", "Tilt Right", "Nghiêng phải", (1, 0, 246, 0)),
    # Multimedia & system shortcuts
    ActionDef("media_play_pause", "media", "Play / Pause", "Phát / Tạm dừng", (3, 0, 205, 0)),
    ActionDef("media_prev", "media", "Previous Track", "Bài trước", (3, 0, 182, 0)),
    ActionDef("media_next", "media", "Next Track", "Bài tiếp", (3, 0, 181, 0)),
    ActionDef("media_stop", "media", "Stop Media", "Dừng phát", (3, 0, 183, 0)),
    ActionDef("media_mute", "media", "Mute Volume", "Tắt tiếng", (3, 0, 226, 0)),
    ActionDef("media_vol_up", "media", "Volume +", "Tăng âm lượng", (3, 0, 233, 0)),
    ActionDef("media_vol_down", "media", "Volume -", "Giảm âm lượng", (3, 0, 234, 0)),
    ActionDef("sys_media_player", "system", "Media Player", "Trình phát nhạc", (3, 0, 131, 1)),
    ActionDef("sys_calculator", "system", "Calculator", "Máy tính", (3, 0, 146, 1)),
    ActionDef("sys_mail", "system", "Mail", "Ứng dụng Mail", (3, 0, 138, 1)),
    ActionDef("sys_explorer", "system", "File Explorer", "Quản lý tệp", (3, 0, 148, 1)),
    ActionDef("sys_search", "system", "Search", "Tìm kiếm", (3, 0, 33, 2)),
    ActionDef("sys_browser_home", "system", "Browser Home", "Trang chủ trình duyệt", (3, 0, 35, 2)),
    ActionDef("sys_refresh", "system", "Browser Refresh", "Tải lại trang", (3, 0, 39, 2)),
)

ACTION_BY_ID: dict[str, ActionDef] = {a.id: a for a in PREDEFINED_ACTIONS}
ACTION_BY_RAW: dict[tuple[int, int, int, int], ActionDef] = {a.raw: a for a in PREDEFINED_ACTIONS}

# USB HID Keyboard usage IDs -> short labels
HID_MODIFIER_LABELS: dict[int, str] = {
    224: "Ctrl",
    225: "Shift",
    226: "Alt",
    227: "Super",
    228: "RCtrl",
    229: "RShift",
    230: "RAlt",
    231: "RSuper",
}

HID_KEY_LABELS: dict[int, str] = {
    **HID_MODIFIER_LABELS,
    **{0x04 + i: chr(ord("A") + i) for i in range(26)},
    0x1E: "1",
    0x1F: "2",
    0x20: "3",
    0x21: "4",
    0x22: "5",
    0x23: "6",
    0x24: "7",
    0x25: "8",
    0x26: "9",
    0x27: "0",
    0x28: "Enter",
    0x29: "Esc",
    0x2A: "Backspace",
    0x2B: "Tab",
    0x2C: "Space",
    0x2D: "-",
    0x2E: "=",
    0x2F: "[",
    0x30: "]",
    0x31: "\\",
    0x33: ";",
    0x34: "'",
    0x35: "`",
    0x36: ",",
    0x37: ".",
    0x38: "/",
    0x39: "CapsLock",
    **{0x3A + i: f"F{i + 1}" for i in range(12)},
    0x46: "PrintScreen",
    0x47: "ScrollLock",
    0x48: "Pause",
    0x49: "Insert",
    0x4A: "Home",
    0x4B: "PageUp",
    0x4C: "Delete",
    0x4D: "End",
    0x4E: "PageDown",
    0x4F: "Right",
    0x50: "Left",
    0x51: "Down",
    0x52: "Up",
    0x53: "NumLock",
    0x54: "KP/",
    0x55: "KP*",
    0x56: "KP-",
    0x57: "KP+",
    0x58: "KPEnter",
    0x59: "KP1",
    0x5A: "KP2",
    0x5B: "KP3",
    0x5C: "KP4",
    0x5D: "KP5",
    0x5E: "KP6",
    0x5F: "KP7",
    0x60: "KP8",
    0x61: "KP9",
    0x62: "KP0",
    0x63: "KP.",
    0x65: "Menu",
}

HID_KEY_BY_NAME: dict[str, int] = {label.upper(): code for code, label in HID_KEY_LABELS.items()}
HID_KEY_BY_NAME.update(
    {
        "LCTRL": 224,
        "CONTROL": 224,
        "CTRL": 224,
        "LSHIFT": 225,
        "SHIFT": 225,
        "LALT": 226,
        "ALT": 226,
        "WIN": 227,
        "META": 227,
        "GUI": 227,
        "SUPER": 227,
        "RCTRL": 228,
        "RSHIFT": 229,
        "RALT": 230,
        "RSUPER": 231,
        "PGUP": 0x4B,
        "PGDN": 0x4E,
        "DEL": 0x4C,
        "INS": 0x49,
        "BKSP": 0x2A,
        "ESC": 0x29,
        "RETURN": 0x28,
    }
)

# Macro event mouse button map: logical button 1..5 -> VGN HID macro byte
MACRO_MOUSE_BUTTON_CODES: dict[int, int] = {
    1: 240,  # Left
    2: 241,  # Right
    3: 242,  # Middle
    4: 244,  # Forward
    5: 243,  # Backward
}

DEFAULT_BUTTON_SLOTS: tuple[tuple[int, str, str, str], ...] = (
    (0, "left", "Left Click", "Nút trái"),
    (1, "right", "Right Click", "Nút phải"),
    (2, "middle", "Middle Click", "Nút giữa (Cuộn)"),
    (3, "forward", "Forward", "Nút tiến (Bên hông)"),
    (4, "backward", "Backward", "Nút lùi (Bên hông)"),
    (5, "dpi", "DPI Button", "Nút DPI (Mặt đáy)"),
)


def hid_key_label(code: int) -> str:
    """Return display label for a USB HID keyboard usage ID."""
    return HID_KEY_LABELS.get(code, f"Key(0x{code:02X})")


def parse_key_combo(expr: str) -> list[int]:
    """Parse expressions like 'Ctrl + Shift + C' or 'F5' into up to 3 USB HID codes."""
    parts = [p.strip() for p in expr.split("+") if p.strip()]
    if not parts or len(parts) > 3:
        raise ValueError(f"Keyboard combo must have 1..3 keys, got {expr!r}")
    codes: list[int] = []
    for part in parts:
        up = part.upper()
        if up in HID_KEY_BY_NAME:
            codes.append(HID_KEY_BY_NAME[up])
        elif up.startswith("0X"):
            val = int(up, 16)
            if not (1 <= val <= 255):
                raise ValueError(f"Invalid HID keycode: {part!r}")
            codes.append(val)
        else:
            raise ValueError(f"Unknown key name: {part!r}")
    # Ensure modifiers come first, matching VGN Hub expectation
    mods = [c for c in codes if 224 <= c <= 231]
    non_mods = [c for c in codes if not (224 <= c <= 231)]
    return (mods + non_mods)[:3]


def decode_binding_bytes(raw4: bytes | list[int] | tuple[int, int, int, int]) -> dict[str, object]:
    """Decode a 4-byte ry_mouse button record into structured metadata."""
    if len(raw4) != 4:
        raise ValueError(f"Expected 4 bytes for button binding, got {len(raw4)}")
    b = (int(raw4[0]) & 0xFF, int(raw4[1]) & 0xFF, int(raw4[2]) & 0xFF, int(raw4[3]) & 0xFF)

    action = ACTION_BY_RAW.get(b)
    if action is not None:
        return {
            "kind": action.category,
            "action_id": action.id,
            "label_en": action.label_en,
            "label_vi": action.label_vi,
            "keys": [],
            "macro_id": None,
            "macro_loop": None,
            "raw": list(b),
        }

    if b[0] == 9:
        macro_id = b[2]
        loop_mode = b[1]  # 2 = finite repeat count, 1 = while held / toggle
        return {
            "kind": "macro",
            "action_id": f"macro_{macro_id}",
            "label_en": f"Macro {macro_id + 1}",
            "label_vi": f"Macro {macro_id + 1}",
            "keys": [],
            "macro_id": macro_id,
            "macro_loop": loop_mode,
            "raw": list(b),
        }

    if b[0] == 0:
        keys = [k for k in (b[1], b[2], b[3]) if k != 0]
        if keys:
            text = " + ".join(hid_key_label(k) for k in keys)
            return {
                "kind": "keyboard",
                "action_id": "keyboard",
                "label_en": text,
                "label_vi": text,
                "keys": keys,
                "macro_id": None,
                "macro_loop": None,
                "raw": list(b),
            }

    hex_str = " ".join(f"{x:02X}" for x in b)
    return {
        "kind": "unknown",
        "action_id": "unknown",
        "label_en": f"Custom [{hex_str}]",
        "label_vi": f"Tùy chỉnh [{hex_str}]",
        "keys": [],
        "macro_id": None,
        "macro_loop": None,
        "raw": list(b),
    }


def encode_binding(
    *,
    action_id: str | None = None,
    keys: list[int] | None = None,
    macro_id: int | None = None,
    macro_loop: int = 2,
    raw: list[int] | tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Encode a mouse button assignment into its 4-byte ry_mouse payload."""
    if raw is not None and action_id in (None, "unknown"):
        if len(raw) != 4:
            raise ValueError(f"Raw binding must be 4 bytes, got {len(raw)}")
        return (int(raw[0]) & 0xFF, int(raw[1]) & 0xFF, int(raw[2]) & 0xFF, int(raw[3]) & 0xFF)

    if action_id is not None and action_id in ACTION_BY_ID:
        return ACTION_BY_ID[action_id].raw

    if macro_id is not None or (action_id and action_id.startswith("macro_")):
        mid = macro_id if macro_id is not None else int(action_id.split("_", 1)[1])  # type: ignore[union-attr]
        if not (0 <= mid < 16):
            raise ValueError(f"macro_id must be 0..15, got {mid}")
        lm = 1 if int(macro_loop) == 1 else 2
        return (9, lm, mid, 0)

    if keys:
        clean = [int(k) & 0xFF for k in keys if int(k) > 0][:3]
        if not clean:
            return (0, 0, 0, 0)
        mods = [c for c in clean if 224 <= c <= 231]
        non_mods = [c for c in clean if not (224 <= c <= 231)]
        ordered = (mods + non_mods)[:3]
        while len(ordered) < 3:
            ordered.append(0)
        return (0, ordered[0], ordered[1], ordered[2])

    raise ValueError(f"Unsupported binding specification: action_id={action_id!r}, keys={keys!r}")
