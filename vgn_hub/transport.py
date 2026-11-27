"""Linux /dev/hidraw discovery, ioctl Feature Report transport, and DPI event listener."""

from __future__ import annotations

import fcntl
import os
import select
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .registry import DeviceSpec, find_device_spec

REPORT_SIZE = 64
PACKET_SIZE = 65  # 1-byte leading report ID (0x00) + 64-byte payload


def _ioc(direction: int, typ: str, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord(typ) << 8) | nr


HIDIOCSFEATURE_65 = _ioc(3, "H", 0x06, PACKET_SIZE)
HIDIOCGFEATURE_65 = _ioc(3, "H", 0x07, PACKET_SIZE)


class TransportError(OSError):
    """Raised when opening or communicating with a HID device fails."""


class FeatureTransport(Protocol):
    """Protocol implemented by FeatureHidTransport and mock test transports."""

    @property
    def info(self) -> HidDeviceInfo | None:
        ...

    def xfer_feature(self, payload: bytes, read: bool = True, delay: float = 0.02) -> bytes:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class HidDeviceInfo:
    """Discovered Linux hidraw device paired with its DeviceSpec and sibling event node."""

    path: str
    vid: int
    pid: int
    name: str
    bcd_device: str
    phys: str
    usage_page: int
    usage: int
    accessible: bool
    error: str = ""
    spec: DeviceSpec | None = None
    event_path: str | None = None

    @property
    def vid_pid(self) -> str:
        return f"{self.vid:04x}:{self.pid:04x}"

    @property
    def is_wireless(self) -> bool:
        return bool(self.spec and self.spec.is_wireless_receiver)


def _parse_uevent(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _read_usb_bcd_device(sys_device_dir: Path) -> str:
    cur = sys_device_dir.resolve()
    for _ in range(6):
        bcd_file = cur / "bcdDevice"
        if bcd_file.is_file():
            raw = bcd_file.read_text(encoding="utf-8", errors="ignore").strip()
            if len(raw) == 4:
                return raw
            return raw
        if cur.parent == cur:
            break
        cur = cur.parent
    return ""


def _parse_hid_descriptor(desc: bytes) -> dict[str, object]:
    """Extract (usage_page, usage) collections, report IDs, and 64-byte feature capability."""
    collections: set[tuple[int, int]] = set()
    report_ids: set[int] = set()
    has_feature = False
    has_feature_64 = False

    usage_page: int | None = None
    pending_usages: list[int] = []
    report_count: int | None = None

    i = 0
    while i < len(desc):
        b = desc[i]
        if b == 0xFE:
            if i + 1 >= len(desc):
                break
            i += 3 + desc[i + 1]
            continue
        sz_code = b & 0x03
        sz = 4 if sz_code == 3 else sz_code
        tag = b & 0xFC
        if i + 1 + sz > len(desc):
            break
        val = int.from_bytes(desc[i + 1 : i + 1 + sz], "little")

        if tag == 0x04:  # Usage Page
            usage_page = val
        elif tag == 0x08:  # Usage
            pending_usages.append(val)
            if usage_page is not None:
                collections.add((usage_page, val))
        elif tag == 0xA0:  # Collection
            if usage_page is not None and pending_usages:
                collections.add((usage_page, pending_usages[0]))
            pending_usages.clear()
        elif tag == 0xC0:  # End Collection
            pending_usages.clear()
        elif tag == 0x84:  # Report ID
            report_ids.add(val)
        elif tag == 0x94:  # Report Count
            report_count = val
        elif tag == 0xB0:  # Feature
            has_feature = True
            if report_count == 64:
                has_feature_64 = True
        elif tag in (0x80, 0x90):  # Input / Output
            pending_usages.clear()

        i += 1 + sz

    first_pair = next(iter(sorted(collections)), (0, 0))
    return {
        "collections": collections,
        "report_ids": report_ids,
        "has_feature": has_feature,
        "has_feature_64": has_feature_64,
        "first_pair": first_pair,
    }


def _check_rw_access(dev_path: str) -> tuple[bool, str]:
    try:
        fd = os.open(dev_path, os.O_RDWR | os.O_NONBLOCK)
        os.close(fd)
        return True, ""
    except OSError as exc:
        return False, exc.strerror or str(exc)


def _usb_root_phys(phys: str) -> str:
    return phys.split("/input")[0] if "/input" in phys else phys


def discover_devices() -> list[HidDeviceInfo]:
    """Scan /sys/class/hidraw for supported VGN control interfaces."""
    sys_root = Path("/sys/class/hidraw")
    if not sys_root.is_dir():
        return []

    raw_nodes: list[dict[str, object]] = []
    for entry in sorted(sys_root.iterdir(), key=lambda p: p.name):
        dev_dir = entry / "device"
        uevent_path = dev_dir / "uevent"
        desc_path = dev_dir / "report_descriptor"
        if not uevent_path.is_file() or not desc_path.is_file():
            continue

        uevent = _parse_uevent(uevent_path.read_text(encoding="utf-8", errors="ignore"))
        hid_id = uevent.get("HID_ID", "")
        parts = hid_id.split(":")
        if len(parts) != 3:
            continue
        try:
            vid = int(parts[1], 16)
            pid = int(parts[2], 16)
        except ValueError:
            continue

        spec = find_device_spec(vid, pid)
        if spec is None:
            continue

        try:
            desc = desc_path.read_bytes()
        except OSError:
            continue

        parsed = _parse_hid_descriptor(desc)
        raw_nodes.append(
            {
                "path": f"/dev/{entry.name}",
                "vid": vid,
                "pid": pid,
                "name": uevent.get("HID_NAME", "").strip() or spec.name,
                "bcd_device": _read_usb_bcd_device(dev_dir),
                "phys": uevent.get("HID_PHYS", ""),
                "spec": spec,
                "parsed": parsed,
            }
        )

    # Map sibling event nodes (e.g., usage 0xFFFF:0x01 with Report ID 5 for live DPI switches)
    event_by_key: dict[tuple[int, int, str], str] = {}
    for node in raw_nodes:
        spec = node["spec"]
        parsed = node["parsed"]
        assert isinstance(spec, DeviceSpec) and isinstance(parsed, dict)
        cols = parsed["collections"]
        rids = parsed["report_ids"]
        assert isinstance(cols, set) and isinstance(rids, set)
        if (spec.event_usage_page, spec.event_usage) in cols and spec.event_report_id in rids:
            key = (int(node["vid"]), int(node["pid"]), _usb_root_phys(str(node["phys"])))
            event_by_key[key] = str(node["path"])

    found: list[HidDeviceInfo] = []
    for node in raw_nodes:
        spec = node["spec"]
        parsed = node["parsed"]
        assert isinstance(spec, DeviceSpec) and isinstance(parsed, dict)
        cols = parsed["collections"]
        assert isinstance(cols, set)
        if (spec.usage_page, spec.usage) not in cols:
            continue
        if not parsed["has_feature"]:
            continue

        dev_path = str(node["path"])
        accessible, err = _check_rw_access(dev_path)
        key = (int(node["vid"]), int(node["pid"]), _usb_root_phys(str(node["phys"])))
        found.append(
            HidDeviceInfo(
                path=dev_path,
                vid=int(node["vid"]),
                pid=int(node["pid"]),
                name=str(node["name"]),
                bcd_device=str(node["bcd_device"]),
                phys=str(node["phys"]),
                usage_page=spec.usage_page,
                usage=spec.usage,
                accessible=accessible,
                error=err,
                spec=spec,
                event_path=event_by_key.get(key),
            )
        )

    found.sort(key=lambda d: (not d.accessible, d.is_wireless, d.path))
    return found


class FeatureHidTransport:
    """Thread-safe Linux /dev/hidrawX 64-byte HID Feature Report transport."""

    def __init__(self, device_path: str | None = None) -> None:
        self._requested_path = device_path
        self._info: HidDeviceInfo | None = None
        self._fd: int | None = None
        self._lock = threading.Lock()
        self._event_stop = threading.Event()
        self._event_thread: threading.Thread | None = None

    @property
    def info(self) -> HidDeviceInfo | None:
        return self._info

    @property
    def is_open(self) -> bool:
        return self._fd is not None

    def open(self) -> HidDeviceInfo:
        with self._lock:
            return self._open_locked()

    def _open_locked(self) -> HidDeviceInfo:
        if self._fd is not None and self._info is not None:
            return self._info

        devices = discover_devices()
        target: HidDeviceInfo | None = None

        if self._requested_path:
            for d in devices:
                if d.path == self._requested_path:
                    target = d
                    break
            if target is None:
                if not Path(self._requested_path).exists():
                    raise TransportError(f"Không tìm thấy thiết bị {self._requested_path}")
                target = HidDeviceInfo(
                    path=self._requested_path,
                    vid=0x391D,
                    pid=0x1028,
                    name=Path(self._requested_path).name,
                    bcd_device="",
                    phys="",
                    usage_page=0xFFFF,
                    usage=0x0002,
                    accessible=True,
                    spec=find_device_spec(0x391D, 0x1028),
                )
        else:
            if not devices:
                raise TransportError(
                    "Không tìm thấy chuột VGN (391d:1028 / 391d:1a25). "
                    "Hãy kiểm tra cáp USB hoặc receiver 2.4GHz."
                )
            target = devices[0]

        if not target.accessible and target.error:
            raise TransportError(
                f"Không có quyền truy cập {target.path} ({target.error}). "
                "Hãy cài udev rule 99-vgn-hub.rules cho 391d và cắm lại thiết bị."
            )

        try:
            fd = os.open(target.path, os.O_RDWR)
        except OSError as exc:
            raise TransportError(f"Không thể mở {target.path}: {exc}") from exc

        self._fd = fd
        self._info = target
        return target

    def close(self) -> None:
        self.stop_event_listener()
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

    def xfer_feature(self, payload: bytes, read: bool = True, delay: float = 0.02) -> bytes:
        """Send 64-byte Feature Report (with leading 0x00) and optionally read back 64 bytes."""
        if len(payload) > REPORT_SIZE:
            raise ValueError(f"Feature payload max {REPORT_SIZE} bytes, got {len(payload)}")
        pkt = bytearray([0x00]) + bytearray(payload).ljust(REPORT_SIZE, b"\x00")

        with self._lock:
            if self._fd is None:
                self._open_locked()
            assert self._fd is not None
            try:
                fcntl.ioctl(self._fd, HIDIOCSFEATURE_65, pkt)
                if not read:
                    if delay > 0:
                        time.sleep(delay)
                    return b""
                if delay > 0:
                    time.sleep(delay)
                resp = bytearray(PACKET_SIZE)
                resp[0] = 0x00
                fcntl.ioctl(self._fd, HIDIOCGFEATURE_65, resp)
                return bytes(resp[1:])
            except OSError as exc:
                self._close_locked()
                raise TransportError(f"Lỗi giao tiếp HID Feature: {exc}") from exc

    def start_event_listener(self, on_dpi_change: Callable[[int], None]) -> bool:
        """Listen on sibling input hidraw node (Report ID 5) for hardware DPI button switches."""
        self.stop_event_listener()
        info = self._info or self.open()
        if not info.event_path or not Path(info.event_path).exists():
            return False

        self._event_stop.clear()

        def _worker() -> None:
            try:
                efd = os.open(info.event_path, os.O_RDONLY | os.O_NONBLOCK)  # type: ignore[arg-type]
            except OSError:
                return
            try:
                while not self._event_stop.is_set():
                    ready, _, _ = select.select([efd], [], [], 0.25)
                    if not ready:
                        continue
                    try:
                        data = os.read(efd, 64)
                    except OSError:
                        break
                    # Linux hidraw includes Report ID byte: [0x05, 0x0C, dpi_index, ...]
                    if len(data) >= 3 and data[0] == 0x05 and data[1] == 0x0C:
                        on_dpi_change(int(data[2]))
            finally:
                try:
                    os.close(efd)
                except OSError:
                    pass

        self._event_thread = threading.Thread(target=_worker, name="vgn-dpi-events", daemon=True)
        self._event_thread.start()
        return True

    def stop_event_listener(self) -> None:
        self._event_stop.set()
        if self._event_thread is not None and self._event_thread.is_alive():
            self._event_thread.join(timeout=0.6)
        self._event_thread = None
