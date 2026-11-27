"""Protocol implementation for vgn-ry-mouse devices (Dragonfly 3 Ultra & siblings)."""

from __future__ import annotations

import contextlib
import struct
import threading
import time
from typing import Any, Iterator

from ..keycodes import (
    DEFAULT_BUTTON_SLOTS,
    MACRO_MOUSE_BUTTON_CODES,
    decode_binding_bytes,
    encode_binding,
)
from ..registry import DeviceSpec, find_device_spec
from ..transport import FeatureTransport, HidDeviceInfo
from .base import BatteryInfo, ButtonBinding, DpiStage, MacroEvent, MacroSlot, MouseState

DEFAULT_DPI_COLORS: tuple[str, ...] = (
    "#ff0000",
    "#0000ff",
    "#00ff00",
    "#ffff00",
    "#00ffff",
    "#7d00ff",
)

# Read opcodes
CMD_GET_KEY_INDEX = 0x80       # 128
CMD_GET_ALL_KEY_INFO = 0x81    # 129
CMD_GET_PROFILE = 0x82         # 130
CMD_GET_MACRO = 0x83           # 131
CMD_GET_DEBOUNCE_TIME = 0x84   # 132
CMD_GET_SLEEP_TIME = 0x86      # 134
CMD_GET_REPORT_RATE = 0x88     # 136
CMD_GET_POWER_SUPPLY = 0x8A    # 138
CMD_GET_DELAY_MODE = 0x8C      # 140
CMD_GET_DEVICE_INFO = 0x8F     # 143
CMD_GET_DPI_INFO = 0x90        # 144
CMD_GET_LOD = 0x91             # 145
CMD_GET_ANGLE = 0x92           # 146
CMD_GET_RIPPLE = 0x93          # 147
CMD_GET_MOTION_SYNC = 0x94     # 148
CMD_GET_FPS = 0x95             # 149
CMD_GET_ANGLE_VALUE = 0x98     # 152
CMD_GET_CONFIG = 0x9F          # 159
CMD_GET_DONGLE_INFO = 0xF0     # 240
CMD_DONGLE_CMD_246 = 0xF6      # 246
CMD_DONGLE_STATUS = 0xF7       # 247
CMD_DONGLE_FETCH = 0xFC        # 252

# Write opcodes
CMD_SET_KEY_INDEX = 0x00       # 0
CMD_SET_PROFILE = 0x02         # 2
CMD_SET_MACRO = 0x03           # 3
CMD_SET_DEBOUNCE_TIME = 0x04   # 4
CMD_SET_SLEEP_TIME = 0x06      # 6
CMD_SET_BLU_SLEEP_TIME = 0x07  # 7
CMD_SET_REPORT_RATE = 0x08     # 8
CMD_SET_DELAY_MODE = 0x0C      # 12
CMD_RESTORE_FACTORY = 0x0E     # 14
CMD_SET_DPI_INFO = 0x10        # 16
CMD_SET_LOD = 0x11             # 17
CMD_SET_ANGLE = 0x12           # 18
CMD_SET_RIPPLE = 0x13          # 19
CMD_SET_MOTION_SYNC = 0x14     # 20
CMD_SET_FPS = 0x15             # 21
CMD_SET_ANGLE_VALUE = 0x18     # 24

POLLING_CODE_TO_HZ: dict[int, int] = {
    8: 125,
    4: 250,
    2: 500,
    1: 1000,
    132: 2000,
    130: 4000,
    129: 8000,
}
HZ_TO_POLLING_CODE: dict[int, int] = {hz: code for code, hz in POLLING_CODE_TO_HZ.items()}

VALID_DEBOUNCE_MS = (1, 2, 3, 4, 8, 15, 20)
VALID_SLEEP_SECONDS = (10, 30, 60, 120, 300, 600)


class ProtocolError(RuntimeError):
    """Raised when the mouse returns malformed data or sleeps on 2.4GHz."""


def compute_crc(header: bytes) -> int:
    """Compute VGN ry_mouse header checksum: 255 - (sum(header) & 0xFF)."""
    return (255 - (sum(header) & 0xFF)) & 0xFF


def build_packet(header: bytes, payload: bytes = b"") -> bytes:
    """Construct a 64-byte padded packet: header + crc + payload + zeros."""
    crc = compute_crc(header)
    raw = bytes(header) + bytes([crc]) + bytes(payload)
    if len(raw) > 64:
        raise ValueError(f"Packet overflow ({len(raw)} > 64 bytes)")
    return raw.ljust(64, b"\x00")


def encode_macro_payload(macro: MacroSlot) -> bytes:
    """Encode a MacroSlot into the <=256-byte binary format expected by SetMacro (0x03)."""
    if not (0 <= macro.repeat <= 65535):
        raise ValueError(f"Repeat count must be 0..65535, got {macro.repeat}")
    if len(macro.events) > 63:
        raise ValueError(f"Macro supports at most 63 events, got {len(macro.events)}")

    buf = bytearray()
    buf.extend(struct.pack("<H", int(macro.repeat)))

    for ev in macro.events:
        delay = int(ev.delay_ms)
        if not (0 <= delay <= 65535):
            raise ValueError(f"Macro event delay must be 0..65535ms, got {delay}")
        if delay == 256:
            delay = 255  # Firmware quirk handled in VGN Hub

        if ev.device == "mouse":
            code = MACRO_MOUSE_BUTTON_CODES.get(ev.code, int(ev.code) & 0xFF)
        else:
            code = int(ev.code) & 0xFF

        status = 0x80 if ev.down else 0x00
        buf.extend([code, status])
        buf.extend(struct.pack("<H", delay))

    buf.extend([0x00, 0x00])
    if len(buf) > 256:
        raise ValueError(f"Encoded macro exceeds 256 bytes ({len(buf)})")
    return bytes(buf)


def decode_macro_payload(slot: int, raw: bytes, name: str = "") -> MacroSlot:
    """Decode raw GetMacro bytes into a MacroSlot."""
    if len(raw) < 4 or not any(raw):
        return MacroSlot(slot=slot, name=name or f"Macro {slot + 1}", repeat=1, events=[])
    repeat = struct.unpack_from("<H", raw, 0)[0]
    events: list[MacroEvent] = []
    mouse_rev = {v: k for k, v in MACRO_MOUSE_BUTTON_CODES.items()}
    off = 2
    while off + 4 <= len(raw):
        code, status, delay = struct.unpack_from("<BBH", raw, off)
        if code == 0 and status == 0 and delay == 0:
            break
        down = (status & 0x80) != 0
        if code in mouse_rev:
            events.append(MacroEvent(device="mouse", code=mouse_rev[code], down=down, delay_ms=delay))
        else:
            events.append(MacroEvent(device="keyboard", code=code, down=down, delay_ms=delay))
        off += 4
    return MacroSlot(slot=slot, name=name or f"Macro {slot + 1}", repeat=repeat, events=events)


class RyMouseClient:
    """Protocol client for VGN Dragonfly 3 Ultra and vgn-ry-mouse siblings."""

    def __init__(self, transport: FeatureTransport, device_info: HidDeviceInfo | None = None) -> None:
        self._transport = transport
        self._info = device_info or transport.info
        if self._info and self._info.spec:
            self._spec = self._info.spec
        elif self._info:
            self._spec = find_device_spec(self._info.vid, self._info.pid) or find_device_spec(0x391D, 0x1028)  # type: ignore[assignment]
        else:
            self._spec = find_device_spec(0x391D, 0x1028)  # type: ignore[assignment]
        assert self._spec is not None

        self._raw_dpi_buf: bytearray | None = None
        self._battery: int = 0
        self._is_sleep: bool = False
        self._dongle_fw: str = ""
        self._sleep_fn = time.sleep
        self._op_lock = threading.RLock()

    @contextlib.contextmanager
    def _transaction(self) -> Iterator[None]:
        """Serialize multi-packet device operations across threads and transport locks."""
        with self._op_lock:
            tx_fn = getattr(self._transport, "transaction", None)
            if callable(tx_fn):
                with tx_fn():
                    yield
            else:
                yield

    @property
    def spec(self) -> DeviceSpec:
        return self._spec

    @property
    def is_wireless(self) -> bool:
        return self._spec.is_wireless_receiver

    # ---- Low-level wired/wireless command helpers ----

    def _send_cmd(self, header: bytes, read: bool = True, delay: float = 0.02) -> bytes:
        pkt = build_packet(header)
        return self._transport.xfer_feature(pkt, read=read, delay=delay)

    def _send_cmd_with_buffer(
        self, header: bytes, payload: bytes, read: bool = False, delay: float = 0.02
    ) -> bytes:
        pkt = build_packet(header, payload)
        return self._transport.xfer_feature(pkt, read=read, delay=delay)

    def _dongle_init(self) -> bool:
        status = self._send_cmd(bytes([CMD_DONGLE_STATUS, 0, 0, 0, 0, 0, 0]), read=True)
        self._battery = int(status[2])
        self._is_sleep = status[4] == 1
        if self._is_sleep:
            return False
        self._send_cmd(bytes([CMD_DONGLE_CMD_246, 5, 0, 0, 0, 0, 0]), read=True)
        return True

    def _get_dongle_data(self, wait_ready: bool = True, max_retries: int = 45) -> bytes:
        for _ in range(max_retries):
            self._sleep_fn(0.03)
            status = self._send_cmd(bytes([CMD_DONGLE_STATUS, 0, 0, 0, 0, 0, 0]), read=True)
            self._battery = int(status[2])
            self._is_sleep = status[4] == 1
            if self._is_sleep:
                if not wait_ready:
                    return status
                raise ProtocolError("Chuột đang ở chế độ ngủ (2.4GHz). Hãy di chuyển hoặc nhấp chuột.")
            if wait_ready and status[0] == 0:
                continue
            return self._send_cmd(bytes([CMD_DONGLE_FETCH, 0, 0, 0, 0, 0, 0]), read=True)
        raise ProtocolError("Hết thời gian chờ dongle 2.4GHz phản hồi từ chuột.")

    def _wait_dongle_ready(self, max_retries: int = 25) -> None:
        for _ in range(max_retries):
            status = self._send_cmd(bytes([CMD_DONGLE_STATUS, 0, 0, 0, 0, 0, 0]), read=True)
            self._battery = int(status[2])
            self._is_sleep = status[4] == 1
            if self._is_sleep:
                raise ProtocolError("Chuột đang ngủ (2.4GHz), hãy đánh thức chuột trước khi ghi.")
            if status[5] != 0:
                return
            self._sleep_fn(0.03)
        raise ProtocolError("Dongle 2.4GHz chưa sẵn sàng nhận lệnh ghi.")

    def _read_cmd(self, header: bytes) -> bytes:
        with self._transaction():
            resp = self._send_cmd(header, read=True)
            if self.is_wireless:
                return self._get_dongle_data(wait_ready=True)
            return resp

    def _read_cmd_checked(self, header: bytes, expected_opcode: int, retries: int = 2) -> bytes:
        with self._transaction():
            last = b""
            for attempt in range(retries + 1):
                resp = self._read_cmd(header)
                last = resp
                if len(resp) >= 64 and resp[0] == expected_opcode:
                    return resp
                if attempt < retries:
                    self._sleep_fn(0.05)
            got = f"0x{last[0]:02x}" if last else "empty"
            raise ProtocolError(
                f"Phản hồi HID không khớp opcode (chờ 0x{expected_opcode:02x}, nhận {got})."
            )

    def _write_cmd(self, header: bytes, payload: bytes = b"") -> None:
        with self._transaction():
            if self.is_wireless:
                self._wait_dongle_ready()
            self._send_cmd_with_buffer(header, payload, read=False)

    # ---- Telemetry & state reads ----

    def get_dongle_version(self) -> str:
        if not self.is_wireless:
            return ""
        with self._transaction():
            resp = self._send_cmd(bytes([CMD_GET_DONGLE_INFO, 0, 0, 0, 0, 0, 0]), read=True)
            self._dongle_fw = f"{resp[1]:02x}{resp[0]:02x}"
            return self._dongle_fw

    def get_firmware_version(self) -> str:
        resp = self._read_cmd(bytes([CMD_GET_DEVICE_INFO, 0, 0, 0, 0, 0, 0]))
        return f"{resp[6]:02x}{resp[5]:02x}"

    def get_battery(self) -> BatteryInfo:
        vid_pid = self._info.vid_pid if self._info else self._spec.vid_pid
        with self._transaction():
            if self.is_wireless:
                self._send_cmd(bytes([CMD_GET_POWER_SUPPLY, 0, 0, 0, 0, 0, 0]), read=True)
                self._get_dongle_data(wait_ready=False, max_retries=4)
                return BatteryInfo(
                    percent=None if self._is_sleep and self._battery == 0 else self._battery,
                    is_wireless=True,
                    is_sleep=self._is_sleep,
                    connected=True,
                    device_name=self._spec.name,
                    vid_pid=vid_pid,
                    firmware=self._dongle_fw,
                    note="Sleeping (2.4GHz)" if self._is_sleep else "2.4GHz Dongle",
                )

            resp = self._send_cmd(bytes([CMD_GET_POWER_SUPPLY, 0, 0, 0, 0, 0, 0]), read=True)
            self._battery = int(resp[1])
            self._is_sleep = False
            return BatteryInfo(
                percent=self._battery,
                is_wireless=False,
                is_sleep=False,
                connected=True,
                device_name=self._spec.name,
                vid_pid=vid_pid,
                firmware=self._info.bcd_device if self._info else "",
                note="Wired USB",
            )

    def _read_config(self) -> dict[str, object]:
        # Note: GetConfig (159) uses a 4-byte header [159, 0, 0, 0] (CRC at byte 4).
        r = self._read_cmd_checked(bytes([CMD_GET_CONFIG, 0, 0, 0]), CMD_GET_CONFIG)
        sleep_sec = struct.unpack_from("<H", r, 11)[0]
        polling_code = int(r[15])
        lod_code = int(r[16])
        lod_map = dict(self._spec.lod_options)
        return {
            "profile": int(r[8]),
            "debounce_ms": int(r[9]),
            "sleep_seconds": sleep_sec,
            "polling_code": polling_code,
            "polling_hz": POLLING_CODE_TO_HZ.get(polling_code, 1000),
            "lod_code": lod_code,
            "lod_mm": lod_map.get(lod_code, f"mode-{lod_code}"),
            "angle_snap": r[17] == 1,
            "ripple_control": r[18] == 1,
            "motion_sync": r[19] == 1,
            "latency_mode": int(r[40]),
        }

    @staticmethod
    def _decode_dpi_buf(buf: bytes | bytearray, max_stages: int) -> tuple[int, list[DpiStage]]:
        active = int(buf[2])
        count = max(1, min(max_stages, int(buf[3])))
        stages: list[DpiStage] = []
        for idx in range(count):
            x = struct.unpack_from("<H", buf, 8 + 2 * idx)[0]
            y = struct.unpack_from("<H", buf, 24 + 2 * idx)[0]
            red, green, blue = buf[40 + 3 * idx : 43 + 3 * idx]
            stages.append(DpiStage(x=x, y=y, color=f"#{red:02x}{green:02x}{blue:02x}"))
        active = max(0, min(count - 1, active))
        return active, stages

    def decode_cached_dpi(self) -> tuple[int, list[DpiStage]] | None:
        """Decode the cached DPI buffer without extra HID round-trips."""
        with self._op_lock:
            if self._raw_dpi_buf is None:
                return None
            return self._decode_dpi_buf(self._raw_dpi_buf, self._spec.max_dpi_stages)

    def sync_active_dpi_cache(self, stage_index: int) -> None:
        """Keep the cached active DPI stage aligned with hardware DPI-button events."""
        with self._op_lock:
            if self._raw_dpi_buf is None:
                return
            count = max(1, min(self._spec.max_dpi_stages, int(self._raw_dpi_buf[3])))
            if 0 <= stage_index < count:
                self._raw_dpi_buf[2] = stage_index

    def _read_dpi_info(self, profile: int) -> tuple[int, list[DpiStage]]:
        r = self._read_cmd_checked(
            bytes([CMD_GET_DPI_INFO, profile & 0xFF, 0, 0, 0, 0, 0]),
            CMD_GET_DPI_INFO,
        )
        self._raw_dpi_buf = bytearray(r)
        return self._decode_dpi_buf(r, self._spec.max_dpi_stages)

    def _read_buttons(self, profile: int) -> list[ButtonBinding]:
        r = self._read_cmd(bytes([CMD_GET_ALL_KEY_INFO, profile & 0xFF, 0, 0, 0, 0, 0]))
        buttons: list[ButtonBinding] = []
        for slot, name, label_en, label_vi in DEFAULT_BUTTON_SLOTS[: self._spec.button_count]:
            raw4 = r[4 * slot : 4 * slot + 4]
            decoded = decode_binding_bytes(raw4)
            buttons.append(
                ButtonBinding(
                    slot=slot,
                    name=name,
                    label_en=label_en,
                    label_vi=label_vi,
                    kind=str(decoded["kind"]),
                    action_id=str(decoded["action_id"]),
                    action_label_en=str(decoded["label_en"]),
                    action_label_vi=str(decoded["label_vi"]),
                    keys=list(decoded["keys"]),  # type: ignore[arg-type]
                    macro_id=decoded["macro_id"],  # type: ignore[arg-type]
                    macro_loop=decoded["macro_loop"],  # type: ignore[arg-type]
                    raw=list(decoded["raw"]),  # type: ignore[arg-type]
                )
            )
        return buttons

    def _read_fps_mode(self) -> int:
        r = self._read_cmd_checked(bytes([CMD_GET_FPS, 0, 0, 0, 0, 0, 0]), CMD_GET_FPS)
        return 0 if r[1] == 0 else 1

    def _read_sensor_rotation(self) -> int:
        r = self._read_cmd_checked(
            bytes([CMD_GET_ANGLE_VALUE, 0, 0, 0, 0, 0, 0]),
            CMD_GET_ANGLE_VALUE,
        )
        val = int(r[1]) & 0xFF
        return val - 256 if val > 127 else val

    def read_all_state(self) -> MouseState:
        """Read full active profile configuration and battery telemetry from the mouse."""
        with self._transaction():
            if self.is_wireless:
                if not self._dongle_init():
                    raise ProtocolError("Chuột đang ở chế độ ngủ (2.4GHz). Hãy di chuyển hoặc nhấp chuột.")
                self._sleep_fn(0.015)
                self.get_dongle_version()
                self._sleep_fn(0.015)

            bat = self.get_battery()
            self._sleep_fn(0.015)
            cfg = self._read_config()
            self._sleep_fn(0.015)
            fw = self.get_firmware_version()
            self._sleep_fn(0.015)
            profile = int(cfg["profile"])  # type: ignore[arg-type]
            buttons = self._read_buttons(profile)
            self._sleep_fn(0.015)
            active_dpi, dpi_stages = self._read_dpi_info(profile)
            self._sleep_fn(0.015)
            fps_mode = self._read_fps_mode()
            self._sleep_fn(0.015)
            rotation = self._read_sensor_rotation()

            return MouseState(
                device_name=self._spec.name,
                slug=self._spec.slug,
                vid_pid=self._info.vid_pid if self._info else self._spec.vid_pid,
                hidraw_path=self._info.path if self._info else "",
                is_wireless=self.is_wireless,
                is_sleep=self._is_sleep,
                firmware=fw,
                dongle_firmware=self._dongle_fw,
                battery=bat.percent if bat.percent is not None else self._battery,
                profile=profile,
                profile_count=self._spec.profile_count,
                sensor=self._spec.sensor,
                dpi_min=self._spec.dpi_min,
                dpi_max=self._spec.dpi_max,
                dpi_step=self._spec.dpi_step,
                max_dpi_stages=self._spec.max_dpi_stages,
                active_dpi=active_dpi,
                dpi_stages=dpi_stages,
                polling_hz=int(cfg["polling_hz"]),  # type: ignore[arg-type]
                lod_mm=str(cfg["lod_mm"]),
                lod_code=int(cfg["lod_code"]),  # type: ignore[arg-type]
                debounce_ms=int(cfg["debounce_ms"]),  # type: ignore[arg-type]
                sleep_seconds=int(cfg["sleep_seconds"]),  # type: ignore[arg-type]
                motion_sync=bool(cfg["motion_sync"]),
                angle_snap=bool(cfg["angle_snap"]),
                ripple_control=bool(cfg["ripple_control"]),
                latency_mode=int(cfg["latency_mode"]),  # type: ignore[arg-type]
                fps_mode=fps_mode,
                sensor_rotation=rotation,
                buttons=buttons,
                supports_sensor_rotation=self._spec.supports_sensor_rotation,
                supports_fps_20k=self._spec.supports_fps_20k,
                supports_latency_mode=self._spec.supports_latency_mode,
                max_polling_hz=self._spec.max_polling_hz,
                lod_options=[{"code": c, "label": lbl} for c, lbl in self._spec.lod_options],
                polling_options=[hz for _, hz in self._spec.polling_options],
            )

    # ---- Profile & parameter setters ----

    def set_profile(self, profile: int) -> None:
        if not (0 <= profile < self._spec.profile_count):
            raise ValueError(f"Profile must be 0..{self._spec.profile_count - 1}, got {profile}")
        with self._transaction():
            self._write_cmd(bytes([CMD_SET_PROFILE, profile, 0, 0, 0, 0, 0]))
            self._raw_dpi_buf = None

    def set_polling_rate(self, hz: int) -> None:
        if hz not in HZ_TO_POLLING_CODE or hz > self._spec.max_polling_hz:
            valid = [h for _, h in self._spec.polling_options]
            raise ValueError(f"Unsupported polling rate {hz}Hz. Supported: {valid}")
        code = HZ_TO_POLLING_CODE[hz]
        self._write_cmd(bytes([CMD_SET_REPORT_RATE, code, 0, 0, 0, 0, 0]))

    def set_lod(self, lod_code_or_label: int | str) -> None:
        options = self._spec.lod_options
        code: int | None = None
        if isinstance(lod_code_or_label, str):
            norm = lod_code_or_label.strip().lower().removesuffix("mm")
            for c, lbl in options:
                if lbl.lower().removesuffix("mm") == norm or str(c) == norm:
                    code = c
                    break
        else:
            for c, _ in options:
                if c == lod_code_or_label:
                    code = c
                    break
        if code is None:
            raise ValueError(f"Unsupported LOD {lod_code_or_label!r} for {self._spec.sensor}")
        self._write_cmd(bytes([CMD_SET_LOD, code, 0, 0, 0, 0, 0]))

    def set_debounce(self, ms: int) -> None:
        val = int(ms)
        if val not in VALID_DEBOUNCE_MS:
            raise ValueError(f"Debounce must be one of {VALID_DEBOUNCE_MS}, got {val}")
        self._write_cmd(bytes([CMD_SET_DEBOUNCE_TIME, val, 0, 0, 0, 0, 0]))

    def set_sleep_time(self, seconds: int) -> None:
        sec = int(seconds)
        if sec not in VALID_SLEEP_SECONDS:
            raise ValueError(f"Sleep timer must be one of {VALID_SLEEP_SECONDS}s, got {sec}")
        lo, hi = sec & 0xFF, (sec >> 8) & 0xFF
        with self._transaction():
            self._write_cmd(bytes([CMD_SET_SLEEP_TIME, lo, hi, 0, 0, 0, 0]))
            self._sleep_fn(0.05)
            self._write_cmd(bytes([CMD_SET_BLU_SLEEP_TIME, lo, hi, 0, 0, 0, 0]))

    def set_motion_sync(self, enabled: bool) -> None:
        self._write_cmd(bytes([CMD_SET_MOTION_SYNC, 1 if enabled else 0, 0, 0, 0, 0, 0]))

    def set_angle_snap(self, enabled: bool) -> None:
        self._write_cmd(bytes([CMD_SET_ANGLE, 1 if enabled else 0, 0, 0, 0, 0, 0]))

    def set_ripple_control(self, enabled: bool) -> None:
        self._write_cmd(bytes([CMD_SET_RIPPLE, 1 if enabled else 0, 0, 0, 0, 0, 0]))

    def set_latency_mode(self, mode: int | str) -> None:
        if isinstance(mode, str):
            norm = mode.strip().lower()
            val = 1 if norm in ("extreme", "1") else 0 if norm in ("stable", "0") else -1
        else:
            val = int(mode)
        if val not in (0, 1):
            raise ValueError(f"Latency mode must be 0 (Stable) or 1 (Extreme), got {mode!r}")
        self._write_cmd(bytes([CMD_SET_DELAY_MODE, val, 0, 0, 0, 0, 0]))

    def set_fps_mode(self, mode: int | str) -> None:
        if isinstance(mode, str):
            norm = mode.strip().lower()
            val = 1 if norm in ("20k", "supreme", "competitive", "1") else 0 if norm in ("basic", "0") else -1
        else:
            val = int(mode)
        if val not in (0, 1):
            raise ValueError(f"FPS mode must be 0 (Basic) or 1 (20K/Supreme), got {mode!r}")
        self._write_cmd(bytes([CMD_SET_FPS, val, 0, 0, 0, 0, 0]))

    def set_sensor_rotation(self, degrees: int) -> None:
        deg = int(degrees)
        if not (-90 <= deg <= 90):
            raise ValueError(f"Sensor rotation must be -90..90 degrees, got {deg}")
        self._write_cmd(bytes([CMD_SET_ANGLE_VALUE, deg & 0xFF, 0, 0, 0, 0, 0]))

    # ---- DPI stage configuration ----

    def _ensure_dpi_buf(self, profile: int | None = None) -> bytearray:
        if self._raw_dpi_buf is None:
            prof = profile if profile is not None else int(self._read_config()["profile"])  # type: ignore[arg-type]
            self._read_dpi_info(prof)
        assert self._raw_dpi_buf is not None
        return bytearray(self._raw_dpi_buf)

    def _commit_dpi_buf(self, buf: bytearray) -> None:
        count = max(1, min(self._spec.max_dpi_stages, int(buf[3])))
        buf[3] = count
        buf[2] = max(0, min(count - 1, int(buf[2])))
        buf[0] = CMD_SET_DPI_INFO
        header = bytes(buf[:7])
        payload = bytes(buf[8:64])
        self._write_cmd(header, payload)
        buf[7] = compute_crc(header)
        self._raw_dpi_buf = bytearray(buf)

    def _clamp_dpi(self, val: int) -> int:
        step = self._spec.dpi_step
        v = max(self._spec.dpi_min, min(self._spec.dpi_max, int(val)))
        return round(v / step) * step

    @staticmethod
    def _parse_hex_rgb(color: str) -> tuple[int, int, int]:
        s = color.strip().lstrip("#")
        if len(s) != 6:
            raise ValueError(f"Hex color must be #RRGGBB, got {color!r}")
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

    def set_current_dpi(self, stage_index: int) -> None:
        with self._transaction():
            buf = self._ensure_dpi_buf()
            count = max(1, min(self._spec.max_dpi_stages, int(buf[3])))
            if not (0 <= stage_index < count):
                raise ValueError(f"Active DPI stage must be 0..{count - 1}, got {stage_index}")
            buf[2] = stage_index
            self._commit_dpi_buf(buf)

    def set_dpi_stage(
        self, stage_index: int, x: int, y: int | None = None, color: str | None = None
    ) -> None:
        with self._transaction():
            buf = self._ensure_dpi_buf()
            count = max(1, min(self._spec.max_dpi_stages, int(buf[3])))
            if not (0 <= stage_index < count):
                raise ValueError(f"DPI stage index must be 0..{count - 1}, got {stage_index}")
            cx = self._clamp_dpi(x)
            cy = self._clamp_dpi(x if y is None else y)
            struct.pack_into("<H", buf, 8 + 2 * stage_index, cx)
            struct.pack_into("<H", buf, 24 + 2 * stage_index, cy)
            if color is not None:
                r, g, b = self._parse_hex_rgb(color)
                buf[40 + 3 * stage_index : 43 + 3 * stage_index] = bytes([r, g, b])
            self._commit_dpi_buf(buf)

    def set_dpi_color(self, stage_index: int, color: str) -> None:
        with self._transaction():
            buf = self._ensure_dpi_buf()
            count = max(1, min(self._spec.max_dpi_stages, int(buf[3])))
            if not (0 <= stage_index < count):
                raise ValueError(f"DPI stage index must be 0..{count - 1}, got {stage_index}")
            r, g, b = self._parse_hex_rgb(color)
            buf[40 + 3 * stage_index : 43 + 3 * stage_index] = bytes([r, g, b])
            self._commit_dpi_buf(buf)

    def set_dpi_stages(self, stages: list[DpiStage], active_index: int | None = None) -> None:
        if not (1 <= len(stages) <= self._spec.max_dpi_stages):
            raise ValueError(f"Stage count must be 1..{self._spec.max_dpi_stages}, got {len(stages)}")
        with self._transaction():
            buf = self._ensure_dpi_buf()
            buf[3] = len(stages)
            cur_active = int(buf[2]) if active_index is None else int(active_index)
            buf[2] = max(0, min(len(stages) - 1, cur_active))

            # Preserve tail bytes [58..64], clear [8..58] before writing
            buf[8:58] = b"\x00" * 50
            for idx, st in enumerate(stages):
                cx = self._clamp_dpi(st.x)
                cy = self._clamp_dpi(st.y)
                r, g, b = self._parse_hex_rgb(st.color)
                struct.pack_into("<H", buf, 8 + 2 * idx, cx)
                struct.pack_into("<H", buf, 24 + 2 * idx, cy)
                buf[40 + 3 * idx : 43 + 3 * idx] = bytes([r, g, b])
            self._commit_dpi_buf(buf)

    def set_dpi_count(self, count: int) -> None:
        cnt = int(count)
        if not (1 <= cnt <= self._spec.max_dpi_stages):
            raise ValueError(f"DPI stage count must be 1..{self._spec.max_dpi_stages}, got {cnt}")
        with self._transaction():
            buf = self._ensure_dpi_buf()
            old_cnt = max(1, min(self._spec.max_dpi_stages, int(buf[3])))
            defaults = [400, 800, 1600, 3200, 6400, 12800]
            stages: list[DpiStage] = []
            for idx in range(cnt):
                if idx < old_cnt:
                    x = struct.unpack_from("<H", buf, 8 + 2 * idx)[0] or defaults[idx]
                    y = struct.unpack_from("<H", buf, 24 + 2 * idx)[0] or x
                    r, g, b = buf[40 + 3 * idx : 43 + 3 * idx]
                    color = f"#{r:02x}{g:02x}{b:02x}"
                else:
                    x = defaults[idx]
                    y = defaults[idx]
                    color = DEFAULT_DPI_COLORS[idx % len(DEFAULT_DPI_COLORS)]
                stages.append(DpiStage(x=x, y=y, color=color))
            self.set_dpi_stages(stages, active_index=min(int(buf[2]), cnt - 1))

    # ---- Button bindings & macros ----

    def set_button_binding(
        self,
        slot: int,
        *,
        action_id: str | None = None,
        keys: list[int] | None = None,
        macro_id: int | None = None,
        macro_loop: int = 2,
        raw: list[int] | tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int, int, int]:
        if not (0 <= slot < self._spec.button_count):
            raise ValueError(f"Button slot must be 0..{self._spec.button_count - 1}, got {slot}")
        payload4 = encode_binding(
            action_id=action_id,
            keys=keys,
            macro_id=macro_id,
            macro_loop=macro_loop,
            raw=raw,
        )
        self._write_cmd(bytes([CMD_SET_KEY_INDEX, slot, 0, 0, 0, 0, 0]), bytes(payload4))
        return payload4

    def get_macro(self, macro_id: int, name: str = "") -> MacroSlot:
        if not (0 <= macro_id < 16):
            raise ValueError(f"Macro ID must be 0..15, got {macro_id}")
        raw = self._read_cmd(bytes([CMD_GET_MACRO, macro_id, 0, 0, 0, 0, 0]))
        return decode_macro_payload(macro_id, raw, name=name)

    def set_macro(self, macro: MacroSlot) -> None:
        if not (0 <= macro.slot < 16):
            raise ValueError(f"Macro ID must be 0..15, got {macro.slot}")
        data = encode_macro_payload(macro)
        total_chunks_minus_1 = len(data) // 56
        with self._transaction():
            for chunk_idx in range(total_chunks_minus_1 + 1):
                is_last = 1 if chunk_idx == total_chunks_minus_1 else 0
                chunk = data[chunk_idx * 56 : (chunk_idx + 1) * 56]
                self._write_cmd(
                    bytes([CMD_SET_MACRO, macro.slot, chunk_idx, len(data), is_last, 0, 0]),
                    chunk,
                )
                self._sleep_fn(0.1)

    def restore_factory(self) -> None:
        with self._transaction():
            self._write_cmd(bytes([CMD_RESTORE_FACTORY, 0, 0, 0, 0, 0, 0]))
            self._raw_dpi_buf = None
            self._sleep_fn(2.0)

    # ---- Backup / Restore ----

    def export_backup(self) -> dict[str, object]:
        return self.read_all_state().to_backup_dict()

    def import_backup(self, data: dict[str, object]) -> None:
        with self._transaction():
            if "profile" in data and isinstance(data["profile"], int):
                self.set_profile(data["profile"])
                self._sleep_fn(0.05)

            if "dpi_stages" in data and isinstance(data["dpi_stages"], list):
                stages = [
                    DpiStage(
                        x=int(item["x"]),
                        y=int(item.get("y", item["x"])),
                        color=str(item.get("color", "#ff0000")),
                    )
                    for item in data["dpi_stages"]
                ]
                active = data.get("active_dpi")
                self.set_dpi_stages(stages, active_index=int(active) if active is not None else None)
                self._sleep_fn(0.03)

            if "polling_hz" in data:
                self.set_polling_rate(int(data["polling_hz"]))  # type: ignore[arg-type]
                self._sleep_fn(0.03)
            if "lod_mm" in data:
                self.set_lod(str(data["lod_mm"]))
                self._sleep_fn(0.03)
            if "debounce_ms" in data:
                self.set_debounce(int(data["debounce_ms"]))  # type: ignore[arg-type]
                self._sleep_fn(0.03)
            if "sleep_seconds" in data:
                self.set_sleep_time(int(data["sleep_seconds"]))  # type: ignore[arg-type]
                self._sleep_fn(0.03)
            if "motion_sync" in data:
                self.set_motion_sync(bool(data["motion_sync"]))
                self._sleep_fn(0.03)
            if "angle_snap" in data:
                self.set_angle_snap(bool(data["angle_snap"]))
                self._sleep_fn(0.03)
            if "ripple_control" in data:
                self.set_ripple_control(bool(data["ripple_control"]))
                self._sleep_fn(0.03)
            if "latency_mode" in data and self._spec.supports_latency_mode:
                self.set_latency_mode(int(data["latency_mode"]))  # type: ignore[arg-type]
                self._sleep_fn(0.03)
            if "fps_mode" in data and self._spec.supports_fps_20k:
                self.set_fps_mode(int(data["fps_mode"]))  # type: ignore[arg-type]
                self._sleep_fn(0.03)
            if "sensor_rotation" in data and self._spec.supports_sensor_rotation:
                self.set_sensor_rotation(int(data["sensor_rotation"]))  # type: ignore[arg-type]
                self._sleep_fn(0.03)

            if "buttons" in data and isinstance(data["buttons"], list):
                for btn in data["buttons"]:
                    slot = int(btn["slot"])
                    self.set_button_binding(
                        slot,
                        action_id=btn.get("action_id"),
                        keys=btn.get("keys"),
                        macro_id=btn.get("macro_id"),
                        macro_loop=int(btn.get("macro_loop") or 2),
                        raw=btn.get("raw"),
                    )
                    self._sleep_fn(0.03)


def apply_local_state_update(
    state: MouseState,
    action: str,
    params: dict[str, Any],
    *,
    dpi_result: tuple[int, list[DpiStage]] | None = None,
    button_raw: tuple[int, int, int, int] | None = None,
    lod_map: dict[int, str] | None = None,
) -> MouseState:
    """Apply a single validated write mutation to an in-memory MouseState without full re-read."""
    if action in ("set_current_dpi", "set_dpi_stage", "set_dpi_color", "set_dpi_stages"):
        if dpi_result is not None:
            state.active_dpi, state.dpi_stages = dpi_result
    elif action == "set_polling_rate":
        state.polling_hz = int(params["hz"])
    elif action == "set_lod":
        code = int(params["code"])
        state.lod_code = code
        if lod_map and code in lod_map:
            state.lod_mm = lod_map[code]
    elif action == "set_debounce":
        state.debounce_ms = int(params["ms"])
    elif action == "set_sleep_time":
        state.sleep_seconds = int(params["seconds"])
    elif action == "set_motion_sync":
        state.motion_sync = bool(params["enabled"])
    elif action == "set_angle_snap":
        state.angle_snap = bool(params["enabled"])
    elif action == "set_ripple_control":
        state.ripple_control = bool(params["enabled"])
    elif action == "set_latency_mode":
        state.latency_mode = int(params["mode"])
    elif action == "set_fps_mode":
        state.fps_mode = int(params["mode"])
    elif action == "set_sensor_rotation":
        state.sensor_rotation = int(params["degrees"])
    elif action == "set_button_binding" and button_raw is not None:
        slot = int(params["slot"])
        dec = decode_binding_bytes(button_raw)
        for btn in state.buttons:
            if btn.slot == slot:
                btn.kind = str(dec["kind"])
                btn.action_id = str(dec["action_id"])
                btn.action_label_en = str(dec["label_en"])
                btn.action_label_vi = str(dec["label_vi"])
                btn.keys = list(dec["keys"])  # type: ignore[arg-type]
                btn.macro_id = dec["macro_id"]  # type: ignore[arg-type]
                btn.macro_loop = dec["macro_loop"]  # type: ignore[arg-type]
                btn.raw = list(dec["raw"])  # type: ignore[arg-type]
                break
    return state
