"""Native GTK4 + WebKitGTK6 desktop GUI host for VGN Hub Linux."""

from __future__ import annotations

import copy
import json
import shutil
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
gi.require_version("JavaScriptCore", "6.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, JavaScriptCore, WebKit  # noqa: E402

from . import APP_ID, APP_NAME, __version__
from .keycodes import (
    DEFAULT_BUTTON_SLOTS,
    HID_KEY_LABELS,
    PREDEFINED_ACTIONS,
    decode_binding_bytes,
    encode_binding,
)
from .protocols import ProtocolError, RyMouseClient, create_client
from .protocols.base import (
    ButtonBinding,
    DpiStage,
    MacroEvent,
    MacroSlot,
    MouseState,
)
from .registry import list_supported_models
from .transport import FeatureHidTransport, TransportError, discover_devices

WEB_DIR = Path(__file__).resolve().parent / "web"
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

GTK_CSS = """
window.vgn-glass {
    background-color: rgba(14, 10, 20, 0.20);
}
window.vgn-solid {
    background-color: #111218;
}
"""


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
        "watermark": True,
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
        if "watermark" in raw:
            wp["watermark"] = bool(raw.get("watermark"))

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


class DemoMouseSession:
    """In-memory Dragonfly 3 Ultra simulator when running --demo or offline preview."""

    def __init__(self) -> None:
        self._profile = 0
        self._profiles: list[dict[str, Any]] = [self._make_default_profile(i) for i in range(4)]

    @staticmethod
    def _make_default_profile(profile_idx: int) -> dict[str, Any]:
        buttons = []
        defaults = [
            (0, "left", "Left Click", "Nút trái", (1, 0, 240, 0)),
            (1, "right", "Right Click", "Nút phải", (1, 0, 241, 0)),
            (2, "middle", "Middle Click", "Nút giữa (Cuộn)", (1, 0, 242, 0)),
            (3, "forward", "Forward", "Nút tiến (Bên hông)", (1, 0, 244, 0)),
            (4, "backward", "Backward", "Nút lùi (Bên hông)", (1, 0, 243, 0)),
            (5, "dpi", "DPI Button", "Nút DPI (Mặt đáy)", (20, 0, 0, 0)),
        ]
        for slot, name, lbl_en, lbl_vi, raw4 in defaults:
            dec = decode_binding_bytes(raw4)
            buttons.append(
                ButtonBinding(
                    slot=slot,
                    name=name,
                    label_en=lbl_en,
                    label_vi=lbl_vi,
                    kind=str(dec["kind"]),
                    action_id=str(dec["action_id"]),
                    action_label_en=str(dec["label_en"]),
                    action_label_vi=str(dec["label_vi"]),
                    keys=list(dec["keys"]),  # type: ignore[arg-type]
                    macro_id=dec["macro_id"],  # type: ignore[arg-type]
                    macro_loop=dec["macro_loop"],  # type: ignore[arg-type]
                    raw=list(dec["raw"]),  # type: ignore[arg-type]
                )
            )
        return {
            "active_dpi": 3 if profile_idx == 0 else 1,
            "dpi_stages": [
                DpiStage(400, 400, "#ff0000"),
                DpiStage(800, 800, "#0000ff"),
                DpiStage(1600, 1600, "#00ff00"),
                DpiStage(2000, 2000, "#ffff00"),
                DpiStage(6400, 6400, "#00ffff"),
                DpiStage(42000, 42000, "#7d00ff"),
            ],
            "polling_hz": 500 if profile_idx == 0 else 1000,
            "lod_code": 2,
            "lod_mm": "2mm",
            "debounce_ms": 4,
            "sleep_seconds": 300,
            "motion_sync": True,
            "angle_snap": False,
            "ripple_control": False,
            "latency_mode": 0,
            "fps_mode": 0,
            "sensor_rotation": 0,
            "buttons": buttons,
        }

    def read_state(self) -> MouseState:
        p = self._profiles[self._profile]
        return MouseState(
            device_name="Dragonfly 3 Ultra",
            slug="dragonfly-3-ultra",
            vid_pid="391d:1028",
            hidraw_path="DEMO",
            is_wireless=False,
            is_sleep=False,
            firmware="0807",
            dongle_firmware="",
            battery=100,
            profile=self._profile,
            profile_count=4,
            sensor="PAW3950",
            dpi_min=50,
            dpi_max=42000,
            dpi_step=50,
            max_dpi_stages=6,
            active_dpi=p["active_dpi"],
            dpi_stages=copy.deepcopy(p["dpi_stages"]),
            polling_hz=p["polling_hz"],
            lod_mm=p["lod_mm"],
            lod_code=p["lod_code"],
            debounce_ms=p["debounce_ms"],
            sleep_seconds=p["sleep_seconds"],
            motion_sync=p["motion_sync"],
            angle_snap=p["angle_snap"],
            ripple_control=p["ripple_control"],
            latency_mode=p["latency_mode"],
            fps_mode=p["fps_mode"],
            sensor_rotation=p["sensor_rotation"],
            buttons=copy.deepcopy(p["buttons"]),
            supports_sensor_rotation=True,
            supports_fps_20k=True,
            supports_latency_mode=True,
            max_polling_hz=8000,
            lod_options=[
                {"code": 0, "label": "0.7mm"},
                {"code": 1, "label": "1mm"},
                {"code": 2, "label": "2mm"},
            ],
            polling_options=[125, 250, 500, 1000, 2000, 4000, 8000],
            is_demo=True,
        )

    def apply(self, action: str, params: dict[str, Any]) -> None:
        p = self._profiles[self._profile]
        if action == "set_profile":
            self._profile = max(0, min(3, int(params["profile"])))
        elif action == "set_current_dpi":
            p["active_dpi"] = max(0, min(len(p["dpi_stages"]) - 1, int(params["stage"])))
        elif action == "set_dpi_stage":
            idx = int(params["stage"])
            st = p["dpi_stages"][idx]
            x = int(params["x"])
            y = int(params.get("y", x))
            st.x = max(50, min(42000, x))
            st.y = max(50, min(42000, y))
            if params.get("color"):
                st.color = str(params["color"])
        elif action == "set_dpi_color":
            p["dpi_stages"][int(params["stage"])].color = str(params["color"])
        elif action == "set_dpi_stages":
            p["dpi_stages"] = [
                DpiStage(int(s["x"]), int(s.get("y", s["x"])), str(s.get("color", "#ff0000")))
                for s in params["stages"]
            ]
            if params.get("active_dpi") is not None:
                p["active_dpi"] = max(0, min(len(p["dpi_stages"]) - 1, int(params["active_dpi"])))
            else:
                p["active_dpi"] = min(p["active_dpi"], len(p["dpi_stages"]) - 1)
        elif action == "set_polling_rate":
            p["polling_hz"] = int(params["hz"])
        elif action == "set_lod":
            lod_map = {0: "0.7mm", 1: "1mm", 2: "2mm"}
            code = int(params["code"])
            p["lod_code"] = code
            p["lod_mm"] = lod_map.get(code, "2mm")
        elif action == "set_debounce":
            p["debounce_ms"] = int(params["ms"])
        elif action == "set_sleep_time":
            p["sleep_seconds"] = int(params["seconds"])
        elif action == "set_motion_sync":
            p["motion_sync"] = bool(params["enabled"])
        elif action == "set_angle_snap":
            p["angle_snap"] = bool(params["enabled"])
        elif action == "set_ripple_control":
            p["ripple_control"] = bool(params["enabled"])
        elif action == "set_latency_mode":
            p["latency_mode"] = int(params["mode"])
        elif action == "set_fps_mode":
            p["fps_mode"] = int(params["mode"])
        elif action == "set_sensor_rotation":
            p["sensor_rotation"] = max(-90, min(90, int(params["degrees"])))
        elif action == "set_button_binding":
            slot = int(params["slot"])
            raw4 = encode_binding(
                action_id=params.get("action_id"),
                keys=params.get("keys"),
                macro_id=params.get("macro_id"),
                macro_loop=int(params.get("macro_loop") or 2),
                raw=params.get("raw"),
            )
            dec = decode_binding_bytes(raw4)
            _, name, lbl_en, lbl_vi = DEFAULT_BUTTON_SLOTS[slot]
            p["buttons"][slot] = ButtonBinding(
                slot=slot,
                name=name,
                label_en=lbl_en,
                label_vi=lbl_vi,
                kind=str(dec["kind"]),
                action_id=str(dec["action_id"]),
                action_label_en=str(dec["label_en"]),
                action_label_vi=str(dec["label_vi"]),
                keys=list(dec["keys"]),  # type: ignore[arg-type]
                macro_id=dec["macro_id"],  # type: ignore[arg-type]
                macro_loop=dec["macro_loop"],  # type: ignore[arg-type]
                raw=list(dec["raw"]),  # type: ignore[arg-type]
            )
        elif action == "restore_factory":
            self._profiles[self._profile] = self._make_default_profile(self._profile)


class VgnHubWindow(Adw.ApplicationWindow):
    """Main GTK4 + WebKitGTK6 container bridging native HID backend to the dark-glass UI."""

    def __init__(self, app: Adw.Application, demo: bool = False) -> None:
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(1240, 780)
        self.set_size_request(980, 640)

        self._config = _load_config()
        self._demo_mode = demo
        self._demo = DemoMouseSession()
        self._selected_device_path: str | None = None
        self._transport: FeatureHidTransport | None = None
        self._client: RyMouseClient | None = None
        self._hw_lock = threading.Lock()
        self._battery_timer_id: int | None = None

        self._apply_window_theme(self._config["theme"])

        ucm = WebKit.UserContentManager()
        ucm.register_script_message_handler("vgn", None)
        ucm.connect("script-message-received::vgn", self._on_js_message)

        self._webview = WebKit.WebView(user_content_manager=ucm)
        settings = self._webview.get_settings()
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_enable_smooth_scrolling(True)
        settings.set_javascript_can_access_clipboard(True)

        bg = Gdk.RGBA()
        bg.parse("rgba(0, 0, 0, 0)")
        self._webview.set_background_color(bg)
        self._webview.set_hexpand(True)
        self._webview.set_vexpand(True)
        self._webview.load_uri((WEB_DIR / "index.html").as_uri())

        self.set_content(self._webview)
        self.connect("close-request", self._on_close_request)

        self._battery_timer_id = GLib.timeout_add_seconds(30, self._on_battery_tick)

    def _apply_window_theme(self, theme: str) -> None:
        if theme == "solid":
            self.remove_css_class("vgn-glass")
            self.add_css_class("vgn-solid")
        else:
            self.remove_css_class("vgn-solid")
            self.add_css_class("vgn-glass")

    def _on_close_request(self, *_args: Any) -> bool:
        if self._battery_timer_id is not None:
            GLib.source_remove(self._battery_timer_id)
            self._battery_timer_id = None
        self._close_hardware()
        return False

    def _close_hardware(self) -> None:
        with self._hw_lock:
            if self._transport is not None:
                try:
                    self._transport.close()
                except Exception:
                    pass
                self._transport = None
                self._client = None

    def _ensure_hardware(self) -> RyMouseClient:
        with self._hw_lock:
            if self._client is not None and self._transport is not None and self._transport.is_open:
                return self._client
            transport = FeatureHidTransport(device_path=self._selected_device_path)
            info = transport.open()
            client = create_client(transport, info)
            transport.start_event_listener(self._on_hw_dpi_event)
            self._transport = transport
            self._client = client
            return client

    def _on_hw_dpi_event(self, dpi_idx: int) -> None:
        self._emit_event("dpi_changed", {"active_dpi": dpi_idx})

    def _on_battery_tick(self) -> bool:
        if self._demo_mode:
            return True

        def _poll() -> None:
            with self._hw_lock:
                client = self._client
                transport = self._transport
            if client is None or transport is None or not transport.is_open:
                return
            try:
                bat = client.get_battery()
                self._emit_event(
                    "battery",
                    {
                        "battery": bat.percent,
                        "is_sleep": bat.is_sleep,
                        "is_wireless": bat.is_wireless,
                    },
                )
            except Exception:
                pass

        threading.Thread(target=_poll, daemon=True).start()
        return True

    def _emit_event(self, event_name: str, payload: dict[str, Any]) -> None:
        name_js = json.dumps(event_name)
        data_js = json.dumps(payload, ensure_ascii=False)
        GLib.idle_add(self._eval_js, f"window.__vgnEvent && window.__vgnEvent({name_js}, {data_js});")

    def _eval_js(self, script: str) -> bool:
        self._webview.evaluate_javascript(script, -1, None, None, None, None, None)
        return False

    def _resolve_js(self, req_id: int, ok: bool, data: Any = None, error: str | None = None) -> None:
        payload = json.dumps({"ok": ok, "data": data, "error": error}, ensure_ascii=False)
        GLib.idle_add(self._eval_js, f"window.__vgnResolve && window.__vgnResolve({int(req_id)}, {payload});")

    def _on_js_message(self, _ucm: WebKit.UserContentManager, value: JavaScriptCore.Value) -> None:
        try:
            msg = json.loads(value.to_string())
            req_id = int(msg["id"])
            action = str(msg["action"])
            params = msg.get("params") or {}
        except Exception as exc:
            print(f"[vgn-hub-gui] Invalid IPC message: {exc}", file=sys.stderr)
            return

        # Dialog actions must initiate on GTK main thread
        if action == "export_backup_dialog":
            self._handle_export_dialog(req_id)
            return
        if action == "import_backup_dialog":
            self._handle_import_dialog(req_id)
            return
        if action == "choose_wallpaper_dialog":
            self._handle_choose_wallpaper_dialog(req_id)
            return

        threading.Thread(
            target=self._dispatch_worker,
            args=(req_id, action, params),
            daemon=True,
        ).start()

    def _dispatch_worker(self, req_id: int, action: str, params: dict[str, Any]) -> None:
        try:
            result = self._handle_action(action, params)
            self._resolve_js(req_id, True, data=result)
        except Exception as exc:
            self._resolve_js(req_id, False, error=str(exc))

    def _catalog_payload(self) -> dict[str, Any]:
        return {
            "app_version": __version__,
            "actions": [asdict(a) for a in PREDEFINED_ACTIONS],
            "hid_keys": [
                {"code": code, "label": label}
                for code, label in sorted(HID_KEY_LABELS.items(), key=lambda kv: kv[0])
            ],
            "supported_models": list_supported_models(),
            "udev_rule_installed": any(
                Path(p).is_file()
                for p in (
                    "/etc/udev/rules.d/99-vgn-hub.rules",
                    "/etc/udev/rules.d/99-vgn-dragonfly-hidraw.rules",
                )
            ),
        }

    def _safe_discover_devices(self) -> list[dict[str, Any]]:
        try:
            return [_serialize_device(d) for d in discover_devices()]
        except Exception:
            return []

    def _build_state_bundle(self) -> dict[str, Any]:
        self._config["wallpaper"] = _normalize_wallpaper(self._config.get("wallpaper"))
        if self._demo_mode:
            state = self._demo.read_state()
            devices: list[dict[str, Any]] = []
        else:
            self._close_hardware()
            client = self._ensure_hardware()
            state = client.read_all_state()
            devices = self._safe_discover_devices()
        return {
            "connected": True,
            "state": state.to_dict(),
            "devices": devices,
            "config": self._config,
            "catalog": self._catalog_payload(),
        }

    def _handle_action(self, action: str, params: dict[str, Any]) -> Any:
        if action == "init":
            try:
                return self._build_state_bundle()
            except (TransportError, ProtocolError) as exc:
                self._config["wallpaper"] = _normalize_wallpaper(self._config.get("wallpaper"))
                return {
                    "connected": False,
                    "error": str(exc),
                    "devices": self._safe_discover_devices(),
                    "config": self._config,
                    "catalog": self._catalog_payload(),
                }

        if action == "scan_devices":
            return {
                "devices": self._safe_discover_devices(),
                "udev_rule_installed": self._catalog_payload()["udev_rule_installed"],
            }

        if action == "enter_demo":
            self._selected_device_path = None
            self._close_hardware()
            self._demo_mode = True
            return self._build_state_bundle()

        if action == "connect_real":
            device_path = params.get("device_path")
            self._selected_device_path = str(device_path) if device_path else None
            self._close_hardware()
            self._demo_mode = False
            return self._build_state_bundle()

        if action == "refresh":
            return self._build_state_bundle()

        if action == "set_ui_prefs":
            if params.get("lang") in ("vi", "en"):
                self._config["lang"] = params["lang"]
            if params.get("theme") in ("glass", "solid"):
                self._config["theme"] = params["theme"]
                GLib.idle_add(self._apply_window_theme, self._config["theme"])
            if params.get("mouse_finish") in MOUSE_FINISHES:
                self._config["mouse_finish"] = params["mouse_finish"]
            if isinstance(params.get("wallpaper"), dict):
                self._config["wallpaper"] = _normalize_wallpaper(
                    params["wallpaper"],
                    fallback=self._config.get("wallpaper"),
                )
            _save_config(self._config)
            return {"config": self._config}

        if action == "clear_custom_wallpaper":
            _clear_custom_wallpaper_files()
            self._config["wallpaper"] = _normalize_wallpaper(
                {"mode": "preset", "custom_path": ""},
                fallback=self._config.get("wallpaper"),
            )
            _save_config(self._config)
            return {"config": self._config}

        if action == "save_macro":
            slot = int(params["slot"])
            name = str(params.get("name") or f"Macro {slot + 1}")
            repeat = max(1, min(65535, int(params.get("repeat", 1))))
            events_raw = params.get("events") or []
            macro = MacroSlot(
                slot=slot,
                name=name,
                repeat=repeat,
                events=[
                    MacroEvent(
                        device=str(ev.get("device", "keyboard")),
                        code=int(ev["code"]),
                        down=bool(ev["down"]),
                        delay_ms=max(0, min(65535, int(ev.get("delay_ms", 20)))),
                    )
                    for ev in events_raw
                ],
            )
            if not self._demo_mode:
                client = self._ensure_hardware()
                client.set_macro(macro)
            self._config["macros"][slot] = {
                "slot": slot,
                "name": name,
                "repeat": repeat,
                "events": [asdict(e) for e in macro.events],
            }
            _save_config(self._config)
            return {"macros": self._config["macros"]}

        if action == "read_macro":
            slot = int(params["slot"])
            if not self._demo_mode:
                client = self._ensure_hardware()
                local_name = str(self._config["macros"][slot]["name"])
                m = client.get_macro(slot, name=local_name)
                if m.events:
                    self._config["macros"][slot] = {
                        "slot": slot,
                        "name": m.name,
                        "repeat": m.repeat,
                        "events": [asdict(e) for e in m.events],
                    }
                    _save_config(self._config)
            return {"macro": self._config["macros"][slot]}

        # Hardware / Demo mutating actions
        if self._demo_mode:
            self._demo.apply(action, params)
            return {"state": self._demo.read_state().to_dict()}

        client = self._ensure_hardware()
        if action == "set_profile":
            client.set_profile(int(params["profile"]))
            return {"state": client.read_all_state().to_dict()}
        if action == "set_current_dpi":
            client.set_current_dpi(int(params["stage"]))
        elif action == "set_dpi_stage":
            client.set_dpi_stage(
                int(params["stage"]),
                int(params["x"]),
                y=int(params["y"]) if params.get("y") is not None else None,
                color=params.get("color"),
            )
        elif action == "set_dpi_color":
            client.set_dpi_color(int(params["stage"]), str(params["color"]))
        elif action == "set_dpi_stages":
            stages = [
                DpiStage(x=int(s["x"]), y=int(s.get("y", s["x"])), color=str(s.get("color", "#ff0000")))
                for s in params["stages"]
            ]
            active = int(params["active_dpi"]) if params.get("active_dpi") is not None else None
            client.set_dpi_stages(stages, active_index=active)
        elif action == "set_polling_rate":
            client.set_polling_rate(int(params["hz"]))
        elif action == "set_lod":
            client.set_lod(int(params["code"]))
        elif action == "set_debounce":
            client.set_debounce(int(params["ms"]))
        elif action == "set_sleep_time":
            client.set_sleep_time(int(params["seconds"]))
        elif action == "set_motion_sync":
            client.set_motion_sync(bool(params["enabled"]))
        elif action == "set_angle_snap":
            client.set_angle_snap(bool(params["enabled"]))
        elif action == "set_ripple_control":
            client.set_ripple_control(bool(params["enabled"]))
        elif action == "set_latency_mode":
            client.set_latency_mode(int(params["mode"]))
        elif action == "set_fps_mode":
            client.set_fps_mode(int(params["mode"]))
        elif action == "set_sensor_rotation":
            client.set_sensor_rotation(int(params["degrees"]))
        elif action == "set_button_binding":
            client.set_button_binding(
                int(params["slot"]),
                action_id=params.get("action_id"),
                keys=params.get("keys"),
                macro_id=params.get("macro_id"),
                macro_loop=int(params.get("macro_loop") or 2),
                raw=params.get("raw"),
            )
        elif action == "restore_factory":
            client.restore_factory()
        else:
            raise ValueError(f"Unknown action: {action}")

        return {"state": client.read_all_state().to_dict()}

    def _make_json_filter(self) -> Gio.ListStore:
        flt = Gtk.FileFilter()
        flt.set_name("JSON Backup (*.json)")
        flt.add_pattern("*.json")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        return store

    def _make_image_filter(self) -> Gio.ListStore:
        flt = Gtk.FileFilter()
        flt.set_name("Wallpaper Images (*.png, *.jpg, *.webp, *.bmp, *.avif, *.gif)")
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.avif", "*.gif"):
            flt.add_pattern(pattern)
        for mime in ("image/png", "image/jpeg", "image/webp", "image/bmp", "image/avif", "image/gif"):
            flt.add_mime_type(mime)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        return store

    def _handle_choose_wallpaper_dialog(self, req_id: int) -> None:
        dialog = Gtk.FileDialog(title="Choose App Wallpaper")
        dialog.set_filters(self._make_image_filter())

        def _done(dlg: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                gfile = dlg.open_finish(res)
            except GLib.Error:
                self._resolve_js(req_id, True, data={"cancelled": True})
                return
            path = gfile.get_path()
            if not path:
                self._resolve_js(req_id, False, error="No file path selected")
                return

            def _install() -> None:
                try:
                    dest = _install_custom_wallpaper(Path(path))
                    self._config["wallpaper"] = _normalize_wallpaper(
                        {"mode": "custom", "custom_path": str(dest)},
                        fallback=self._config.get("wallpaper"),
                    )
                    _save_config(self._config)
                    self._resolve_js(req_id, True, data={"cancelled": False, "config": self._config})
                except Exception as exc:
                    self._resolve_js(req_id, False, error=str(exc))

            threading.Thread(target=_install, daemon=True).start()

        dialog.open(self, None, _done)

    def _handle_export_dialog(self, req_id: int) -> None:
        dialog = Gtk.FileDialog(title="Export VGN Mouse Backup")
        dialog.set_initial_name("dragonfly-3-ultra-backup.json")
        dialog.set_filters(self._make_json_filter())

        def _done(dlg: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                gfile = dlg.save_finish(res)
            except GLib.Error:
                self._resolve_js(req_id, True, data={"cancelled": True})
                return
            path = gfile.get_path()
            if not path:
                self._resolve_js(req_id, False, error="No file path selected")
                return

            def _write() -> None:
                try:
                    backup = (
                        self._demo.read_state().to_backup_dict()
                        if self._demo_mode
                        else self._ensure_hardware().export_backup()
                    )
                    Path(path).write_text(
                        json.dumps(backup, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                    self._resolve_js(req_id, True, data={"path": path})
                except Exception as exc:
                    self._resolve_js(req_id, False, error=str(exc))

            threading.Thread(target=_write, daemon=True).start()

        dialog.save(self, None, _done)

    def _handle_import_dialog(self, req_id: int) -> None:
        dialog = Gtk.FileDialog(title="Import VGN Mouse Backup")
        dialog.set_filters(self._make_json_filter())

        def _done(dlg: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                gfile = dlg.open_finish(res)
            except GLib.Error:
                self._resolve_js(req_id, True, data={"cancelled": True})
                return
            path = gfile.get_path()
            if not path:
                self._resolve_js(req_id, False, error="No file path selected")
                return

            def _apply() -> None:
                try:
                    data = json.loads(Path(path).read_text(encoding="utf-8"))
                    if self._demo_mode:
                        if "profile" in data:
                            self._demo.apply("set_profile", {"profile": int(data["profile"])})
                        if "dpi_stages" in data:
                            self._demo.apply(
                                "set_dpi_stages",
                                {"stages": data["dpi_stages"], "active_dpi": data.get("active_dpi")},
                            )
                        if "polling_hz" in data:
                            self._demo.apply("set_polling_rate", {"hz": int(data["polling_hz"])})
                        if "debounce_ms" in data:
                            self._demo.apply("set_debounce", {"ms": int(data["debounce_ms"])})
                        if "sleep_seconds" in data:
                            self._demo.apply("set_sleep_time", {"seconds": int(data["sleep_seconds"])})
                        if "motion_sync" in data:
                            self._demo.apply("set_motion_sync", {"enabled": bool(data["motion_sync"])})
                        if "angle_snap" in data:
                            self._demo.apply("set_angle_snap", {"enabled": bool(data["angle_snap"])})
                        if "ripple_control" in data:
                            self._demo.apply("set_ripple_control", {"enabled": bool(data["ripple_control"])})
                        if "latency_mode" in data:
                            self._demo.apply("set_latency_mode", {"mode": int(data["latency_mode"])})
                        if "fps_mode" in data:
                            self._demo.apply("set_fps_mode", {"mode": int(data["fps_mode"])})
                        if "sensor_rotation" in data:
                            self._demo.apply("set_sensor_rotation", {"degrees": int(data["sensor_rotation"])})
                        for btn in data.get("buttons", []):
                            self._demo.apply("set_button_binding", btn)
                        state = self._demo.read_state()
                    else:
                        client = self._ensure_hardware()
                        client.import_backup(data)
                        state = client.read_all_state()
                    self._resolve_js(req_id, True, data={"path": path, "state": state.to_dict()})
                except Exception as exc:
                    self._resolve_js(req_id, False, error=str(exc))

            threading.Thread(target=_apply, daemon=True).start()

        dialog.open(self, None, _done)


class VgnHubApp(Adw.Application):
    def __init__(self, demo: bool = False, smoke_test: bool = False) -> None:
        super().__init__(application_id=APP_ID)
        self._demo = demo
        self._smoke_test = smoke_test
        self._window: VgnHubWindow | None = None

    def do_activate(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(GTK_CSS.encode("utf-8"))
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        style_mgr = Adw.StyleManager.get_default()
        style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        if self._window is None:
            self._window = VgnHubWindow(self, demo=self._demo or self._smoke_test)
        self._window.present()

        if self._smoke_test:
            GLib.timeout_add(300, self._finish_smoke_test)

    def _finish_smoke_test(self) -> bool:
        if self._window is not None:
            self._window.close()
        self.quit()
        return False


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else argv
    demo = "--demo" in raw
    smoke_test = "--smoke-test" in raw
    app = VgnHubApp(demo=demo, smoke_test=smoke_test)
    return app.run([])
