"""Shared device state models, backup serialization, and Waybar formatting."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class DpiStage:
    """Single DPI stage with optional independent X/Y sensitivity and LED indicator color."""

    x: int
    y: int
    color: str = "#ff0000"

    @property
    def is_xy_split(self) -> bool:
        return self.x != self.y


@dataclass
class ButtonBinding:
    """Decoded binding for one physical mouse button slot."""

    slot: int
    name: str
    label_en: str
    label_vi: str
    kind: str
    action_id: str
    action_label_en: str
    action_label_vi: str
    keys: list[int] = field(default_factory=list)
    macro_id: int | None = None
    macro_loop: int | None = None
    raw: list[int] = field(default_factory=lambda: [0, 0, 0, 0])


@dataclass
class MacroEvent:
    """Single press/release action + delay inside a macro sequence."""

    device: str  # "keyboard" | "mouse"
    code: int  # USB HID key usage ID, or mouse button 1..5 / 240..244
    down: bool
    delay_ms: int = 20


@dataclass
class MacroSlot:
    """Stored macro slot (0..15) with repeat count and event list."""

    slot: int
    name: str
    repeat: int = 1
    events: list[MacroEvent] = field(default_factory=list)


@dataclass
class BatteryInfo:
    """Mouse power & wireless state summary."""

    percent: int | None
    is_wireless: bool
    is_sleep: bool
    connected: bool
    device_name: str
    vid_pid: str
    firmware: str = ""
    note: str = ""

    def to_waybar_json(self) -> dict[str, str]:
        if not self.connected:
            return {
                "text": "🖱 VGN offline",
                "tooltip": self.note or "VGN mouse not detected",
                "class": "disconnected",
            }
        mode = "2.4GHz" if self.is_wireless else "USB"
        if self.is_sleep:
            pct_str = f" ({self.percent}%)" if self.percent is not None else ""
            return {
                "text": f"💤 VGN{pct_str}",
                "tooltip": f"{self.device_name} [{mode}]\nStatus: Sleeping (move/click mouse to wake)",
                "class": "sleep",
            }
        if self.percent is not None:
            css = "low" if self.percent <= 20 else "ok"
            icon = "🪫" if self.percent <= 20 else "🖱"
            return {
                "text": f"{icon} {self.percent}%",
                "tooltip": f"{self.device_name} [{mode} fw {self.firmware}]\nBattery: {self.percent}%",
                "class": css,
            }
        return {
            "text": "🖱 VGN",
            "tooltip": f"{self.device_name} [{mode}]\n{self.note}",
            "class": "ok",
        }


@dataclass
class MouseState:
    """Complete snapshot of a connected mouse's active profile and telemetry."""

    device_name: str
    slug: str
    vid_pid: str
    hidraw_path: str
    is_wireless: bool
    is_sleep: bool
    firmware: str
    dongle_firmware: str
    battery: int
    profile: int
    profile_count: int
    sensor: str
    dpi_min: int
    dpi_max: int
    dpi_step: int
    max_dpi_stages: int
    active_dpi: int
    dpi_stages: list[DpiStage]
    polling_hz: int
    lod_mm: str
    lod_code: int
    debounce_ms: int
    sleep_seconds: int
    motion_sync: bool
    angle_snap: bool
    ripple_control: bool
    latency_mode: int
    fps_mode: int
    sensor_rotation: int
    buttons: list[ButtonBinding]
    supports_sensor_rotation: bool = True
    supports_fps_20k: bool = True
    supports_latency_mode: bool = True
    max_polling_hz: int = 8000
    lod_options: list[dict[str, object]] = field(default_factory=list)
    polling_options: list[int] = field(default_factory=list)
    is_demo: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_backup_dict(self) -> dict[str, object]:
        return {
            "schema": "vgn-hub-linux-backup-v1",
            "device": {
                "name": self.device_name,
                "slug": self.slug,
                "vid_pid": self.vid_pid,
                "firmware": self.firmware,
                "sensor": self.sensor,
            },
            "profile": self.profile,
            "active_dpi": self.active_dpi,
            "dpi_stages": [asdict(st) for st in self.dpi_stages],
            "polling_hz": self.polling_hz,
            "lod_mm": self.lod_mm,
            "debounce_ms": self.debounce_ms,
            "sleep_seconds": self.sleep_seconds,
            "motion_sync": self.motion_sync,
            "angle_snap": self.angle_snap,
            "ripple_control": self.ripple_control,
            "latency_mode": self.latency_mode,
            "fps_mode": self.fps_mode,
            "sensor_rotation": self.sensor_rotation,
            "buttons": [
                {
                    "slot": b.slot,
                    "name": b.name,
                    "action_id": b.action_id,
                    "keys": b.keys,
                    "macro_id": b.macro_id,
                    "macro_loop": b.macro_loop,
                    "raw": b.raw,
                }
                for b in self.buttons
            ],
        }
