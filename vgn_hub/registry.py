"""Extensible USB device registry for VGN mice and future VGN peripherals."""

from __future__ import annotations

from dataclasses import dataclass

from . import VGN_VENDOR_ID


@dataclass(frozen=True)
class DeviceSpec:
    """Hardware capabilities and protocol metadata for a supported VGN device."""

    vid: int
    pid: int
    name: str
    slug: str
    protocol_family: str
    is_wireless_receiver: bool
    usage_page: int = 0xFFFF
    usage: int = 0x0002
    event_usage_page: int = 0xFFFF
    event_usage: int = 0x0001
    event_report_id: int = 5
    sensor: str = "PAW3950"
    dpi_min: int = 50
    dpi_max: int = 42000
    dpi_step: int = 50
    max_dpi_stages: int = 6
    max_polling_hz: int = 8000
    button_count: int = 6
    profile_count: int = 4
    supports_sensor_rotation: bool = True
    supports_fps_20k: bool = True
    supports_latency_mode: bool = True

    @property
    def vid_pid(self) -> str:
        return f"{self.vid:04x}:{self.pid:04x}"

    @property
    def lod_options(self) -> tuple[tuple[int, str], ...]:
        if self.sensor == "PAW3395":
            return ((0, "1mm"), (1, "2mm"))
        return ((0, "0.7mm"), (1, "1mm"), (2, "2mm"))

    @property
    def polling_options(self) -> tuple[tuple[int, int], ...]:
        """Return (protocol_code, hz) pairs supported up to max_polling_hz."""
        all_rates = (
            (8, 125),
            (4, 250),
            (2, 500),
            (1, 1000),
            (132, 2000),
            (130, 4000),
            (129, 8000),
        )
        return tuple((code, hz) for code, hz in all_rates if hz <= self.max_polling_hz)


SUPPORTED_DEVICES: tuple[DeviceSpec, ...] = (
    # VGN Dragonfly 3 Ultra (PAW3950, 8KHz)
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1028,
        name="Dragonfly 3 Ultra",
        slug="dragonfly-3-ultra",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=False,
        sensor="PAW3950",
        dpi_min=50,
        dpi_max=42000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1A25,
        name="Dragonfly 3 Ultra",
        slug="dragonfly-3-ultra",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=True,
        sensor="PAW3950",
        dpi_min=50,
        dpi_max=42000,
    ),
    # Sibling vgn-ry-mouse models sharing the same 64-byte Feature protocol
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1004,
        name="Dragonfly 3 Pro Max",
        slug="dragonfly-3-pro-max",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=False,
        sensor="PAW3395",
        dpi_min=50,
        dpi_max=36000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1A04,
        name="Dragonfly 3 Pro Max",
        slug="dragonfly-3-pro-max",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=True,
        sensor="PAW3395",
        dpi_min=50,
        dpi_max=36000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1008,
        name="Dragonfly Y2 V2 Pro Max",
        slug="dragonfly-y2-v2-pro-max",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=False,
        sensor="PAW3395",
        dpi_min=50,
        dpi_max=36000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1A08,
        name="Dragonfly Y2 V2 Pro Max",
        slug="dragonfly-y2-v2-pro-max",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=True,
        sensor="PAW3395",
        dpi_min=50,
        dpi_max=36000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1015,
        name="Dragonfly F1 V2 Pro Max",
        slug="dragonfly-f1-v2-pro-max",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=False,
        sensor="PAW3395",
        dpi_min=50,
        dpi_max=36000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1A13,
        name="Dragonfly F1 V2 Pro Max",
        slug="dragonfly-f1-v2-pro-max",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=True,
        sensor="PAW3395",
        dpi_min=50,
        dpi_max=36000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x102F,
        name="Dragonfly F1 V5 Ultra",
        slug="dragonfly-f1-v5-ultra",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=False,
        sensor="PAW3950",
        dpi_min=50,
        dpi_max=42000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1A2B,
        name="Dragonfly F1 V5 Ultra",
        slug="dragonfly-f1-v5-ultra",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=True,
        sensor="PAW3950",
        dpi_min=50,
        dpi_max=42000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1048,
        name="Dragonfly F2 V2 Ultra",
        slug="dragonfly-f2-v2-ultra",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=False,
        sensor="PAW3950",
        dpi_min=50,
        dpi_max=42000,
    ),
    DeviceSpec(
        vid=VGN_VENDOR_ID,
        pid=0x1A41,
        name="Dragonfly F2 V2 Ultra",
        slug="dragonfly-f2-v2-ultra",
        protocol_family="vgn-ry-mouse",
        is_wireless_receiver=True,
        sensor="PAW3950",
        dpi_min=50,
        dpi_max=42000,
    ),
)

DEVICE_BY_VID_PID: dict[tuple[int, int], DeviceSpec] = {
    (spec.vid, spec.pid): spec for spec in SUPPORTED_DEVICES
}


def find_device_spec(vid: int, pid: int) -> DeviceSpec | None:
    """Look up a registered device spec by USB VID/PID."""
    return DEVICE_BY_VID_PID.get((vid, pid))


def list_supported_models() -> list[dict[str, object]]:
    """Return deduplicated model metadata for UI/CLI display."""
    grouped: dict[str, dict[str, object]] = {}
    for spec in SUPPORTED_DEVICES:
        entry = grouped.setdefault(
            spec.slug,
            {
                "name": spec.name,
                "slug": spec.slug,
                "protocol_family": spec.protocol_family,
                "sensor": spec.sensor,
                "dpi_max": spec.dpi_max,
                "max_polling_hz": spec.max_polling_hz,
                "wired_vid_pid": None,
                "wireless_vid_pid": None,
            },
        )
        if spec.is_wireless_receiver:
            entry["wireless_vid_pid"] = spec.vid_pid
        else:
            entry["wired_vid_pid"] = spec.vid_pid
    return list(grouped.values())
