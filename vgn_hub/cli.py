"""Command-line interface for VGN Hub Linux (status, battery, DPI, polling, params, backup, GUI)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .protocols import ProtocolError, RyMouseClient, create_client
from .protocols.base import BatteryInfo
from .transport import FeatureHidTransport, TransportError, discover_devices


def _open_client(device_path: str | None = None) -> tuple[FeatureHidTransport, RyMouseClient]:
    transport = FeatureHidTransport(device_path=device_path)
    info = transport.open()
    return transport, create_client(transport, info)


def _format_sleep(seconds: int) -> str:
    return f"{seconds // 60}m" if seconds >= 60 and seconds % 60 == 0 else f"{seconds}s"


def _parse_bool_flag(value: str) -> bool:
    v = value.strip().lower()
    if v in ("1", "on", "true", "yes", "enable"):
        return True
    if v in ("0", "off", "false", "no", "disable"):
        return False
    raise argparse.ArgumentTypeError(f"Expected on/off, got {value!r}")


def _cmd_status(args: argparse.Namespace, device_path: str | None) -> int:
    devices = discover_devices()
    if not devices and not device_path:
        payload = {"connected": False, "devices": [], "error": "Không tìm thấy chuột VGN."}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"VGN Hub Linux v{__version__}")
            print("  Thiết bị : Không tìm thấy chuột VGN (391d:1028 / 391d:1a25).")
        return 1

    transport, client = _open_client(device_path)
    try:
        state = client.read_all_state()
    finally:
        transport.close()

    if args.json:
        print(json.dumps(state.to_dict(), indent=2, ensure_ascii=False))
        return 0

    mode = "2.4GHz Wireless" if state.is_wireless else "USB Wired"
    fps_label = "Supreme ≥20K FPS" if state.fps_mode == 1 else "Basic"
    lat_label = "Extreme" if state.latency_mode == 1 else "Stable"
    print(f"VGN Hub Linux v{__version__}")
    print(f"  Thiết bị : {state.device_name} ({state.vid_pid}) [{mode}]")
    print(f"  Cổng HID : {state.hidraw_path} | fw v{state.firmware}" + (f" | dongle v{state.dongle_firmware}" if state.dongle_firmware else ""))
    print(f"  Pin      : {state.battery}%")
    print(f"  Profile  : {state.profile + 1}/{state.profile_count} | Sensor: {state.sensor}")
    dpi_str = ", ".join(
        f"{'*' if i == state.active_dpi else ''}{s.x}" + (f"x{s.y}" if s.is_xy_split else "")
        for i, s in enumerate(state.dpi_stages)
    )
    active_stage = state.dpi_stages[state.active_dpi]
    print(f"  DPI      : Stage {state.active_dpi + 1}/{len(state.dpi_stages)} ({active_stage.x} DPI) | [{dpi_str}]")
    print(
        f"  Hiệu năng: {state.polling_hz}Hz | LOD {state.lod_mm} | Debounce {state.debounce_ms}ms | "
        f"Ngủ {_format_sleep(state.sleep_seconds)}"
    )
    print(
        f"  Cảm biến : MotionSync={'ON' if state.motion_sync else 'OFF'} | "
        f"AngleSnap={'ON' if state.angle_snap else 'OFF'} | "
        f"Ripple={'ON' if state.ripple_control else 'OFF'} | "
        f"FPS={fps_label} | Latency={lat_label} | Xoay={state.sensor_rotation}°"
    )
    return 0


def _cmd_battery(args: argparse.Namespace, device_path: str | None) -> int:
    devices = discover_devices()
    if not devices and not device_path:
        info = BatteryInfo(
            percent=None,
            is_wireless=False,
            is_sleep=False,
            connected=False,
            device_name="VGN Mouse",
            vid_pid="",
            note="Không tìm thấy chuột VGN (391d:1028 / 391d:1a25).",
        )
        if args.waybar:
            print(json.dumps(info.to_waybar_json(), ensure_ascii=False))
            return 0
        if args.json:
            print(json.dumps(asdict(info), indent=2, ensure_ascii=False))
            return 1
        print(info.note)
        return 1

    transport, client = _open_client(device_path)
    try:
        info = client.get_battery()
    finally:
        transport.close()

    if args.waybar:
        print(json.dumps(info.to_waybar_json(), ensure_ascii=False))
        return 0
    if args.json:
        print(json.dumps(asdict(info), indent=2, ensure_ascii=False))
        return 0
    if info.is_sleep:
        print(f"{info.device_name}: Đang ngủ ({info.percent if info.percent is not None else '?'}%)")
    else:
        print(f"{info.device_name}: Pin {info.percent}% [{'2.4GHz' if info.is_wireless else 'USB'}]")
    return 0


def _cmd_profile(args: argparse.Namespace, device_path: str | None) -> int:
    transport, client = _open_client(device_path)
    try:
        if args.number is None:
            state = client.read_all_state()
            print(f"Profile hiện tại: {state.profile + 1}/{state.profile_count}")
            return 0
        idx = args.number - 1
        client.set_profile(idx)
        print(f"Đã chuyển sang Profile {args.number}")
        return 0
    finally:
        transport.close()


def _cmd_dpi(args: argparse.Namespace, device_path: str | None) -> int:
    transport, client = _open_client(device_path)
    try:
        action = args.dpi_action or "list"
        if action == "list":
            state = client.read_all_state()
            for i, st in enumerate(state.dpi_stages):
                mark = "*" if i == state.active_dpi else " "
                xy = f"{st.x}" if not st.is_xy_split else f"X:{st.x} Y:{st.y}"
                print(f"  {mark} DPI {i + 1}: {xy:<14} {st.color}")
            return 0
        if action == "active":
            client.set_current_dpi(args.stage - 1)
            print(f"Đã chọn DPI {args.stage}")
            return 0
        if action == "count":
            client.set_dpi_count(args.stages)
            print(f"Đã đặt số nấc DPI = {args.stages}")
            return 0
        if action == "set":
            client.set_dpi_stage(args.stage - 1, args.value, y=args.y, color=args.color)
            y_val = args.y if args.y is not None else args.value
            print(f"Đã đặt DPI {args.stage}: X={args.value}, Y={y_val}" + (f", color={args.color}" if args.color else ""))
            return 0
        raise ValueError(f"Unknown dpi action: {action}")
    finally:
        transport.close()


def _cmd_polling(args: argparse.Namespace, device_path: str | None) -> int:
    transport, client = _open_client(device_path)
    try:
        if args.hz is None:
            state = client.read_all_state()
            print(f"Polling Rate: {state.polling_hz}Hz")
            return 0
        client.set_polling_rate(args.hz)
        print(f"Đã đặt Polling Rate = {args.hz}Hz")
        return 0
    finally:
        transport.close()


def _cmd_angle(args: argparse.Namespace, device_path: str | None) -> int:
    transport, client = _open_client(device_path)
    try:
        if args.degrees is None:
            state = client.read_all_state()
            print(f"Sensor Rotation: {state.sensor_rotation}°")
            return 0
        client.set_sensor_rotation(args.degrees)
        print(f"Đã đặt Sensor Rotation = {args.degrees}°")
        return 0
    finally:
        transport.close()


def _cmd_params(args: argparse.Namespace, device_path: str | None) -> int:
    has_write = any(
        getattr(args, field) is not None
        for field in (
            "lod",
            "debounce",
            "sleep",
            "motion_sync",
            "angle_snap",
            "ripple",
            "latency",
            "fps",
        )
    )
    transport, client = _open_client(device_path)
    try:
        if not has_write:
            state = client.read_all_state()
            print(f"LOD               : {state.lod_mm}")
            print(f"Debounce          : {state.debounce_ms}ms")
            print(f"Sleep Timer       : {_format_sleep(state.sleep_seconds)}")
            print(f"Motion Sync       : {'ON' if state.motion_sync else 'OFF'}")
            print(f"Straight-Line     : {'ON' if state.angle_snap else 'OFF'}")
            print(f"Wave Control      : {'ON' if state.ripple_control else 'OFF'}")
            print(f"Latency Mode      : {'Extreme' if state.latency_mode == 1 else 'Stable'}")
            print(f"Sensor Sampling   : {'Supreme ≥20K FPS' if state.fps_mode == 1 else 'Basic'}")
            return 0

        if args.lod is not None:
            client.set_lod(args.lod)
        if args.debounce is not None:
            client.set_debounce(args.debounce)
        if args.sleep is not None:
            client.set_sleep_time(args.sleep)
        if args.motion_sync is not None:
            client.set_motion_sync(args.motion_sync)
        if args.angle_snap is not None:
            client.set_angle_snap(args.angle_snap)
        if args.ripple is not None:
            client.set_ripple_control(args.ripple)
        if args.latency is not None:
            client.set_latency_mode(args.latency)
        if args.fps is not None:
            client.set_fps_mode(args.fps)
        print("Đã cập nhật thông số chuột.")
        return 0
    finally:
        transport.close()


def _cmd_backup(args: argparse.Namespace, device_path: str | None) -> int:
    transport, client = _open_client(device_path)
    try:
        data = client.export_backup()
    finally:
        transport.close()
    out = Path(args.file)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Đã sao lưu cấu hình ra {out}")
    return 0


def _cmd_restore(args: argparse.Namespace, device_path: str | None) -> int:
    src = Path(args.file)
    data = json.loads(src.read_text(encoding="utf-8"))
    transport, client = _open_client(device_path)
    try:
        client.import_backup(data)
    finally:
        transport.close()
    print(f"Đã khôi phục cấu hình từ {src}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--device", help="Đường dẫn /dev/hidrawX cụ thể")

    parser = argparse.ArgumentParser(
        prog="vgn-hub",
        description="VGN Hub Linux — Trình điều khiển chuột VGN (không tham số để mở GUI).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--device", dest="device_top", help="Đường dẫn /dev/hidrawX cụ thể")

    sub = parser.add_subparsers(dest="command")

    p_status = sub.add_parser("status", parents=[common], help="Xem thông tin chuột và cấu hình hiện tại")
    p_status.add_argument("--json", action="store_true", help="Xuất JSON")

    p_bat = sub.add_parser("battery", parents=[common], help="Đọc phần trăm pin chuột (hỗ trợ Waybar)")
    p_bat.add_argument("--waybar", action="store_true", help="Xuất JSON cho Waybar custom module")
    p_bat.add_argument("--json", action="store_true", help="Xuất JSON đầy đủ")

    p_prof = sub.add_parser("profile", parents=[common], help="Xem hoặc chuyển Profile 1..4")
    p_prof.add_argument("number", nargs="?", type=int, choices=[1, 2, 3, 4], help="Số profile (1..4)")

    p_dpi = sub.add_parser("dpi", parents=[common], help="Xem và chỉnh các nấc DPI")
    dpi_sub = p_dpi.add_subparsers(dest="dpi_action")
    dpi_sub.add_parser("list", parents=[common], help="Liệt kê các nấc DPI")
    p_dpi_act = dpi_sub.add_parser("active", parents=[common], help="Chọn nấc DPI đang dùng (1..6)")
    p_dpi_act.add_argument("stage", type=int, choices=[1, 2, 3, 4, 5, 6])
    p_dpi_cnt = dpi_sub.add_parser("count", parents=[common], help="Đổi tổng số nấc DPI (1..6)")
    p_dpi_cnt.add_argument("stages", type=int, choices=[1, 2, 3, 4, 5, 6])
    p_dpi_set = dpi_sub.add_parser("set", parents=[common], help="Chỉnh giá trị DPI và màu LED cho 1 nấc")
    p_dpi_set.add_argument("stage", type=int, choices=[1, 2, 3, 4, 5, 6])
    p_dpi_set.add_argument("value", type=int, help="DPI X (hoặc cả X/Y)")
    p_dpi_set.add_argument("--y", type=int, help="DPI Y riêng nếu tách X/Y")
    p_dpi_set.add_argument("--color", help="Màu LED nấc DPI dạng #RRGGBB")

    p_poll = sub.add_parser("polling", parents=[common], help="Xem hoặc đặt Polling Rate (Hz)")
    p_poll.add_argument(
        "hz",
        nargs="?",
        type=int,
        choices=[125, 250, 500, 1000, 2000, 4000, 8000],
        help="Tần số lấy mẫu (Hz)",
    )

    p_angle = sub.add_parser("angle", parents=[common], help="Xem hoặc đặt góc xoay cảm biến (-90..90)")
    p_angle.add_argument("degrees", nargs="?", type=int, help="Góc xoay (-90..90)")

    p_params = sub.add_parser("params", parents=[common], help="Xem hoặc chỉnh LOD, Debounce, Motion Sync, Sleep...")
    p_params.add_argument("--lod", choices=["0.7", "1", "2"], help="Khoảng cách nhấc chuột (mm)")
    p_params.add_argument("--debounce", type=int, choices=[1, 2, 3, 4, 8, 15, 20], help="Debounce (ms)")
    p_params.add_argument("--sleep", type=int, choices=[10, 30, 60, 120, 300, 600], help="Thời gian ngủ (giây)")
    p_params.add_argument("--motion-sync", type=_parse_bool_flag, help="on/off")
    p_params.add_argument("--angle-snap", type=_parse_bool_flag, help="Straight-Line Correction (on/off)")
    p_params.add_argument("--ripple", type=_parse_bool_flag, help="Wave Control (on/off)")
    p_params.add_argument("--latency", choices=["stable", "extreme"], help="Chế độ độ trễ")
    p_params.add_argument("--fps", choices=["basic", "20k"], help="Tốc độ quét cảm biến")

    p_bkp = sub.add_parser("backup", parents=[common], help="Sao lưu cấu hình chuột ra file JSON")
    p_bkp.add_argument("file")

    p_rst = sub.add_parser("restore", parents=[common], help="Khôi phục cấu hình chuột từ file JSON")
    p_rst.add_argument("file")

    p_gui = sub.add_parser("gui", help="Mở giao diện đồ họa VGN Hub Linux")
    p_gui.add_argument("--demo", action="store_true", help="Chạy với dữ liệu mô phỏng Dragonfly 3 Ultra")

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    if not raw_args:
        from .gui import main as gui_main

        return gui_main([])

    parser = build_parser()
    args = parser.parse_args(raw_args)
    device_path = getattr(args, "device", None) or getattr(args, "device_top", None)

    if args.command == "gui":
        from .gui import main as gui_main

        return gui_main(["--demo"] if args.demo else [])

    handlers = {
        "status": _cmd_status,
        "battery": _cmd_battery,
        "profile": _cmd_profile,
        "dpi": _cmd_dpi,
        "polling": _cmd_polling,
        "angle": _cmd_angle,
        "params": _cmd_params,
        "backup": _cmd_backup,
        "restore": _cmd_restore,
    }
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args, device_path)
    except (TransportError, ProtocolError, ValueError, OSError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1
