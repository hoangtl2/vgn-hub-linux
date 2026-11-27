"""Pure stdlib configuration, wallpaper storage, and device serialization helpers."""

from __future__ import annotations

import copy
import json
import shutil
import time
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "vgn-hub-linux"
CONFIG_FILE = CONFIG_DIR / "config.json"
WALLPAPER_DIR = CONFIG_DIR / "wallpapers"

WALLPAPER_PRESET_IDS = (
    "vgn-crimson",
    "obsidian-aurora",
    "cyber-indigo",
    "dragonfly-gold",
    "emerald-pulse",
    "pure-minimal",
)
ALLOWED_WALLPAPER_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".avif", ".gif")
MAX_WALLPAPER_BYTES = 30 * 1024 * 1024
MOUSE_FINISHES = ("obsidian", "frost", "sakura", "sunset")


def _default_wallpaper() -> dict[str, Any]:
    """Return default wallpaper appearance settings."""
    return {
        "mode": "preset",
        "preset": "vgn-crimson",
        "custom_path": "",
        "custom_url": "",
        "blur": 0,
        "dim": 28,
        "opacity": 88,
    }


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        num = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, num))


def _normalize_wallpaper(raw: Any, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize and validate wallpaper settings, resolving any existing custom image URI."""
    wp = copy.deepcopy(fallback) if isinstance(fallback, dict) else _default_wallpaper()
    if isinstance(raw, dict):
        preset = raw.get("preset")
        if preset in WALLPAPER_PRESET_IDS:
            wp["preset"] = preset
        mode = raw.get("mode")
        if mode in ("preset", "custom"):
            wp["mode"] = mode
        if "custom_path" in raw:
            wp["custom_path"] = str(raw.get("custom_path") or "")
        if "blur" in raw:
            wp["blur"] = _clamp_int(raw.get("blur"), 0, 24, int(wp.get("blur", 0)))
        if "dim" in raw:
            wp["dim"] = _clamp_int(raw.get("dim"), 0, 85, int(wp.get("dim", 28)))
        if "opacity" in raw:
            wp["opacity"] = _clamp_int(raw.get("opacity"), 25, 100, int(wp.get("opacity", 88)))

    if wp.get("preset") not in WALLPAPER_PRESET_IDS:
        wp["preset"] = "vgn-crimson"
    if wp.get("mode") not in ("preset", "custom"):
        wp["mode"] = "preset"

    custom_path_str = str(wp.get("custom_path") or "").strip()
    resolved_url = ""
    if custom_path_str:
        try:
            p = Path(custom_path_str)
            if p.is_file():
                resolved_url = f"{p.resolve().as_uri()}?v={p.stat().st_mtime_ns}"
            else:
                custom_path_str = ""
        except OSError:
            custom_path_str = ""

    wp["custom_path"] = custom_path_str
    wp["custom_url"] = resolved_url
    if not resolved_url and wp["mode"] == "custom":
        wp["mode"] = "preset"

    return wp


def _install_custom_wallpaper(src_path: Path, wallpaper_dir: Path | None = None) -> Path:
    """Validate and copy a user-selected image into the app wallpaper directory."""
    if not src_path.is_file():
        raise ValueError(f"Wallpaper image not found: {src_path}")
    suffix = src_path.suffix.lower()
    if suffix not in ALLOWED_WALLPAPER_SUFFIXES:
        raise ValueError(
            f"Unsupported wallpaper format '{suffix or 'unknown'}'. "
            f"Allowed: {', '.join(ALLOWED_WALLPAPER_SUFFIXES)}"
        )
    size = src_path.stat().st_size
    if size > MAX_WALLPAPER_BYTES:
        raise ValueError("Wallpaper image exceeds 30 MiB size limit.")

    target_dir = wallpaper_dir or WALLPAPER_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / f"custom_{int(time.time() * 1000)}{suffix}"
    shutil.copy2(src_path, dest)

    for existing in target_dir.glob("custom_*"):
        if existing != dest and existing.is_file():
            try:
                existing.unlink()
            except OSError:
                pass

    return dest


def _clear_custom_wallpaper_files(wallpaper_dir: Path | None = None) -> None:
    """Delete any custom wallpaper files managed by VGN Hub."""
    target_dir = wallpaper_dir or WALLPAPER_DIR
    if not target_dir.is_dir():
        return
    for existing in target_dir.glob("custom_*"):
        if existing.is_file():
            try:
                existing.unlink()
            except OSError:
                pass


def _serialize_device(dev: Any) -> dict[str, Any]:
    """Serialize a discovered HidDeviceInfo object to a JSON-safe dictionary."""
    spec = getattr(dev, "spec", None)
    return {
        "path": str(getattr(dev, "path", "")),
        "vid": int(getattr(dev, "vid", 0)),
        "pid": int(getattr(dev, "pid", 0)),
        "vid_pid": str(getattr(dev, "vid_pid", "")),
        "name": str(getattr(dev, "name", "")),
        "bcd_device": str(getattr(dev, "bcd_device", "")),
        "phys": str(getattr(dev, "phys", "")),
        "accessible": bool(getattr(dev, "accessible", False)),
        "error": str(getattr(dev, "error", "")),
        "is_wireless": bool(getattr(dev, "is_wireless", False)),
        "slug": str(spec.slug) if spec is not None else "",
        "sensor": str(spec.sensor) if spec is not None else "",
        "dpi_max": int(spec.dpi_max) if spec is not None else 0,
        "max_polling_hz": int(spec.max_polling_hz) if spec is not None else 0,
        "model_name": str(spec.name) if spec is not None else str(getattr(dev, "name", "")),
    }


def _default_config() -> dict[str, Any]:
    return {
        "lang": "vi",
        "theme": "glass",
        "mouse_finish": "obsidian",
        "wallpaper": _default_wallpaper(),
        "macros": [
            {"slot": i, "name": f"Macro {i + 1}", "repeat": 1, "events": []}
            for i in range(16)
        ],
    }


def _load_config() -> dict[str, Any]:
    cfg = _default_config()
    try:
        if CONFIG_FILE.is_file():
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                if raw.get("lang") in ("vi", "en"):
                    cfg["lang"] = raw["lang"]
                if raw.get("theme") in ("glass", "solid"):
                    cfg["theme"] = raw["theme"]
                if raw.get("mouse_finish") in MOUSE_FINISHES:
                    cfg["mouse_finish"] = raw["mouse_finish"]
                cfg["wallpaper"] = _normalize_wallpaper(raw.get("wallpaper"), cfg["wallpaper"])
                if isinstance(raw.get("macros"), list):
                    by_slot = {int(m["slot"]): m for m in raw["macros"] if isinstance(m, dict) and "slot" in m}
                    merged = []
                    for i in range(16):
                        m = by_slot.get(i, {})
                        merged.append(
                            {
                                "slot": i,
                                "name": str(m.get("name") or f"Macro {i + 1}"),
                                "repeat": max(1, int(m.get("repeat", 1))),
                                "events": m.get("events", []) if isinstance(m.get("events"), list) else [],
                            }
                        )
                    cfg["macros"] = merged
    except Exception:
        pass
    return cfg


def _save_config(cfg: dict[str, Any]) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass
