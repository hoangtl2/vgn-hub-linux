"""Comprehensive unit tests for VGN ry_mouse HID protocol (wired & 2.4GHz wireless)."""

from __future__ import annotations

import struct
import unittest

from vgn_hub.keycodes import decode_binding_bytes, encode_binding, parse_key_combo
from vgn_hub.protocols.base import DpiStage, MacroEvent, MacroSlot
from vgn_hub.protocols.ry_mouse import (
    CMD_DONGLE_CMD_246,
    CMD_DONGLE_FETCH,
    CMD_DONGLE_STATUS,
    CMD_GET_ALL_KEY_INFO,
    CMD_GET_ANGLE_VALUE,
    CMD_GET_CONFIG,
    CMD_GET_DEVICE_INFO,
    CMD_GET_DONGLE_INFO,
    CMD_GET_DPI_INFO,
    CMD_GET_FPS,
    CMD_GET_MACRO,
    CMD_GET_POWER_SUPPLY,
    CMD_RESTORE_FACTORY,
    CMD_SET_ANGLE,
    CMD_SET_ANGLE_VALUE,
    CMD_SET_BLU_SLEEP_TIME,
    CMD_SET_DEBOUNCE_TIME,
    CMD_SET_DELAY_MODE,
    CMD_SET_DPI_INFO,
    CMD_SET_FPS,
    CMD_SET_KEY_INDEX,
    CMD_SET_LOD,
    CMD_SET_MACRO,
    CMD_SET_MOTION_SYNC,
    CMD_SET_PROFILE,
    CMD_SET_REPORT_RATE,
    CMD_SET_RIPPLE,
    CMD_SET_SLEEP_TIME,
    ProtocolError,
    RyMouseClient,
    build_packet,
    compute_crc,
    encode_macro_payload,
)
from vgn_hub.registry import find_device_spec
from vgn_hub.transport import HidDeviceInfo


class MockFeatureTransport:
    """In-memory simulator for Dragonfly 3 Ultra wired (391d:1028) & 2.4GHz dongle (391d:1a25)."""

    def __init__(self, wireless: bool = False) -> None:
        self.wireless = wireless
        pid = 0x1A25 if wireless else 0x1028
        spec = find_device_spec(0x391D, pid)
        self._info = HidDeviceInfo(
            path="/dev/hidraw2",
            vid=0x391D,
            pid=pid,
            name="Dragonfly 3 Ultra",
            bcd_device="0807",
            phys="usb-mock",
            usage_page=0xFFFF,
            usage=0x0002,
            accessible=True,
            spec=spec,
            event_path="/dev/hidraw1",
        )
        self.sent: list[bytes] = []
        self.last_response = b"\x00" * 64
        self.pending_dongle_resp = b"\x00" * 64
        self.dongle_sleep = False
        self.dongle_ready_after = 0
        self._f7_polls = 0

        self.battery = 88
        self.profile = 0
        self.debounce = 4
        self.sleep_sec = 300
        self.blu_sleep_sec = 300
        self.polling_code = 2  # 500Hz
        self.lod_code = 2      # 2mm
        self.angle_snap = 0
        self.ripple = 0
        self.motion_sync = 1
        self.latency_mode = 0
        self.fps_mode = 0
        self.sensor_rotation = 0  # signed int8 encoded as uint8
        self.macros: dict[int, bytearray] = {}
        self.macro_chunks: list[tuple[int, int, int, int, bytes]] = []

        # Default DPI buffer with distinctive tail bytes [58..64]
        self.dpi_buf = bytearray(64)
        self.dpi_buf[0] = CMD_GET_DPI_INFO
        self.dpi_buf[2] = 3
        self.dpi_buf[3] = 6
        defaults = [400, 800, 1600, 2000, 6400, 42000]
        colors = [(255, 0, 0), (0, 0, 255), (0, 255, 0), (255, 255, 0), (0, 255, 255), (125, 0, 255)]
        for i, (d, (r, g, b)) in enumerate(zip(defaults, colors)):
            struct.pack_into("<H", self.dpi_buf, 8 + 2 * i, d)
            struct.pack_into("<H", self.dpi_buf, 24 + 2 * i, d)
            self.dpi_buf[40 + 3 * i : 43 + 3 * i] = bytes([r, g, b])
        self.dpi_buf[58:64] = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])

        self.keys = [
            bytearray([1, 0, 240, 0]),
            bytearray([1, 0, 241, 0]),
            bytearray([1, 0, 242, 0]),
            bytearray([1, 0, 244, 0]),
            bytearray([1, 0, 243, 0]),
            bytearray([20, 0, 0, 0]),
        ]

    @property
    def info(self) -> HidDeviceInfo:
        return self._info

    def open(self) -> HidDeviceInfo:
        return self._info

    def close(self) -> None:
        pass

    def _verify_crc(self, pkt: bytes, header_len: int) -> None:
        expected = compute_crc(pkt[:header_len])
        assert pkt[header_len] == expected, (
            f"Bad CRC for cmd 0x{pkt[0]:02x}: got {pkt[header_len]:02x}, expected {expected:02x}"
        )

    def _handle_mouse_cmd(self, pkt: bytes) -> bytes:
        cmd = pkt[0]
        resp = bytearray(64)
        if cmd == CMD_GET_CONFIG:
            self._verify_crc(pkt, 4)
            resp[0] = cmd
            resp[4] = pkt[4]
            resp[8] = self.profile
            resp[9] = self.debounce
            struct.pack_into("<H", resp, 11, self.sleep_sec)
            struct.pack_into("<H", resp, 13, self.sleep_sec)
            resp[15] = self.polling_code
            resp[16] = self.lod_code
            resp[17] = self.angle_snap
            resp[18] = self.ripple
            resp[19] = self.motion_sync
            resp[40] = self.latency_mode
            return bytes(resp)

        self._verify_crc(pkt, 7)

        if cmd == CMD_GET_DEVICE_INFO:
            resp[0] = cmd
            resp[5], resp[6] = 0x07, 0x08  # fw 0807
        elif cmd == CMD_GET_POWER_SUPPLY:
            resp[0] = cmd
            resp[1] = self.battery
        elif cmd == CMD_GET_ALL_KEY_INFO:
            for i, k in enumerate(self.keys):
                resp[4 * i : 4 * i + 4] = k
        elif cmd == CMD_GET_DPI_INFO:
            resp[:] = self.dpi_buf
        elif cmd == CMD_GET_FPS:
            resp[0] = cmd
            resp[1] = self.fps_mode
        elif cmd == CMD_GET_ANGLE_VALUE:
            resp[0] = cmd
            resp[1] = self.sensor_rotation & 0xFF
        elif cmd == CMD_GET_MACRO:
            slot = pkt[1]
            data = self.macros.get(slot, b"")
            resp[: min(len(data), 64)] = data[:64]
        elif cmd == CMD_SET_PROFILE:
            self.profile = pkt[1]
        elif cmd == CMD_SET_REPORT_RATE:
            self.polling_code = pkt[1]
        elif cmd == CMD_SET_LOD:
            self.lod_code = pkt[1]
        elif cmd == CMD_SET_DEBOUNCE_TIME:
            self.debounce = pkt[1]
        elif cmd == CMD_SET_SLEEP_TIME:
            self.sleep_sec = struct.unpack_from("<H", pkt, 1)[0]
        elif cmd == CMD_SET_BLU_SLEEP_TIME:
            self.blu_sleep_sec = struct.unpack_from("<H", pkt, 1)[0]
        elif cmd == CMD_SET_MOTION_SYNC:
            self.motion_sync = pkt[1]
        elif cmd == CMD_SET_ANGLE:
            self.angle_snap = pkt[1]
        elif cmd == CMD_SET_RIPPLE:
            self.ripple = pkt[1]
        elif cmd == CMD_SET_DELAY_MODE:
            self.latency_mode = pkt[1]
        elif cmd == CMD_SET_FPS:
            self.fps_mode = pkt[1]
        elif cmd == CMD_SET_ANGLE_VALUE:
            self.sensor_rotation = pkt[1]
        elif cmd == CMD_SET_DPI_INFO:
            self.dpi_buf = bytearray(pkt)
            self.dpi_buf[0] = CMD_GET_DPI_INFO
        elif cmd == CMD_SET_KEY_INDEX:
            slot = pkt[1]
            self.keys[slot] = bytearray(pkt[8:12])
        elif cmd == CMD_SET_MACRO:
            slot, chunk_idx, total_len, is_last = pkt[1], pkt[2], pkt[3], pkt[4]
            chunk = pkt[8:64]
            self.macro_chunks.append((slot, chunk_idx, total_len, is_last, chunk))
            buf = self.macros.setdefault(slot, bytearray(total_len))
            end = min(total_len, chunk_idx * 56 + 56)
            buf[chunk_idx * 56 : end] = chunk[: end - chunk_idx * 56]
        elif cmd == CMD_RESTORE_FACTORY:
            self.polling_code = 1
            self.debounce = 8
            self.sensor_rotation = 0
        else:
            raise AssertionError(f"Unhandled mouse opcode 0x{cmd:02x}")
        return bytes(resp)

    def xfer_feature(self, payload: bytes, read: bool = True, delay: float = 0.02) -> bytes:
        assert len(payload) == 64
        self.sent.append(payload)
        cmd = payload[0]

        if self.wireless:
            if cmd == CMD_DONGLE_STATUS:
                self._verify_crc(payload, 7)
                resp = bytearray(64)
                if self.dongle_sleep:
                    resp[4] = 1
                    resp[2] = 0
                else:
                    self._f7_polls += 1
                    resp[0] = 0 if self._f7_polls <= self.dongle_ready_after else 1
                    resp[2] = self.battery
                    resp[4] = 0
                    resp[5] = 1
                self.last_response = bytes(resp)
            elif cmd == CMD_DONGLE_CMD_246:
                self._verify_crc(payload, 7)
                self.last_response = bytes(payload)
            elif cmd == CMD_GET_DONGLE_INFO:
                self._verify_crc(payload, 7)
                resp = bytearray(64)
                resp[0], resp[1] = 0x12, 0x05  # dongle v0512
                self.last_response = bytes(resp)
            elif cmd == CMD_DONGLE_FETCH:
                self._verify_crc(payload, 7)
                self.last_response = self.pending_dongle_resp
            else:
                self.pending_dongle_resp = self._handle_mouse_cmd(payload)
                self.last_response = b"\x00" * 64
        else:
            self.last_response = self._handle_mouse_cmd(payload)

        return self.last_response if read else b""


class TestRyMouseProtocol(unittest.TestCase):
    def _make_client(self, wireless: bool = False) -> tuple[MockFeatureTransport, RyMouseClient]:
        tr = MockFeatureTransport(wireless=wireless)
        client = RyMouseClient(tr, tr.info)
        client._sleep_fn = lambda _sec: None  # speed up tests
        return tr, client

    def test_crc_and_packet_framing(self) -> None:
        self.assertEqual(compute_crc(bytes([159, 0, 0, 0])), 0x60)
        self.assertEqual(compute_crc(bytes([138, 0, 0, 0, 0, 0, 0])), 0x75)
        pkt = build_packet(bytes([159, 0, 0, 0]))
        self.assertEqual(len(pkt), 64)
        self.assertEqual(pkt[4], 0x60)

    def test_wired_read_all_state(self) -> None:
        _, client = self._make_client(wireless=False)
        st = client.read_all_state()
        self.assertEqual(st.device_name, "Dragonfly 3 Ultra")
        self.assertEqual(st.firmware, "0807")
        self.assertEqual(st.battery, 88)
        self.assertEqual(st.polling_hz, 500)
        self.assertEqual(st.lod_mm, "2mm")
        self.assertEqual(st.debounce_ms, 4)
        self.assertEqual(st.sleep_seconds, 300)
        self.assertTrue(st.motion_sync)
        self.assertFalse(st.angle_snap)
        self.assertEqual(st.active_dpi, 3)
        self.assertEqual(len(st.dpi_stages), 6)
        self.assertEqual(st.dpi_stages[5].x, 42000)
        self.assertEqual(st.dpi_stages[5].color, "#7d00ff")
        self.assertEqual([b.action_id for b in st.buttons], [
            "mouse_left", "mouse_right", "mouse_middle", "mouse_forward", "mouse_back", "dpi_cycle"
        ])

    def test_wireless_dongle_handshake_and_sleep(self) -> None:
        tr, client = self._make_client(wireless=True)
        tr.dongle_ready_after = 1
        st = client.read_all_state()
        self.assertTrue(st.is_wireless)
        self.assertEqual(st.dongle_firmware, "0512")
        self.assertEqual(st.battery, 88)
        self.assertEqual(st.firmware, "0807")

        tr.dongle_sleep = True
        with self.assertRaises(ProtocolError):
            client.read_all_state()

    def test_dpi_preserves_tail_and_supports_xy_split(self) -> None:
        tr, client = self._make_client()
        client.read_all_state()
        client.set_dpi_stage(1, 1200, y=1400, color="#123456")
        self.assertEqual(bytes(tr.dpi_buf[58:64]), bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]))
        st = client.read_all_state()
        self.assertEqual(st.dpi_stages[1].x, 1200)
        self.assertEqual(st.dpi_stages[1].y, 1400)
        self.assertEqual(st.dpi_stages[1].color, "#123456")

        client.set_dpi_count(3)
        st2 = client.read_all_state()
        self.assertEqual(len(st2.dpi_stages), 3)
        self.assertEqual(st2.active_dpi, 2)  # clamped from 3 -> 2
        self.assertEqual(bytes(tr.dpi_buf[58:64]), bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]))

    def test_signed_sensor_rotation_and_dual_sleep_write(self) -> None:
        tr, client = self._make_client()
        for deg in (-90, -1, 0, 45, 90):
            client.set_sensor_rotation(deg)
            st = client.read_all_state()
            self.assertEqual(st.sensor_rotation, deg)

        with self.assertRaises(ValueError):
            client.set_sensor_rotation(91)

        client.set_sleep_time(600)
        self.assertEqual(tr.sleep_sec, 600)
        self.assertEqual(tr.blu_sleep_sec, 600)

    def test_all_button_bindings_roundtrip(self) -> None:
        _, client = self._make_client()
        client.set_button_binding(3, action_id="disable")
        client.set_button_binding(4, action_id="media_vol_up")
        client.set_button_binding(5, keys=parse_key_combo("Ctrl + Shift + C"))
        client.set_button_binding(2, macro_id=3, macro_loop=1)

        st = client.read_all_state()
        self.assertEqual(st.buttons[3].action_id, "disable")
        self.assertEqual(st.buttons[4].action_id, "media_vol_up")
        self.assertEqual(st.buttons[5].action_label_en, "Ctrl + Shift + C")
        self.assertEqual(st.buttons[2].kind, "macro")
        self.assertEqual(st.buttons[2].macro_id, 3)
        self.assertEqual(st.buttons[2].macro_loop, 1)

        # Verify raw encode/decode direct consistency
        raw = encode_binding(action_id="scroll_down")
        self.assertEqual(raw, (1, 0, 245, 255))
        self.assertEqual(decode_binding_bytes(raw)["action_id"], "scroll_down")

    def test_macro_chunking_and_256_delay_quirk(self) -> None:
        tr, client = self._make_client()
        events = [MacroEvent("keyboard", 0x04 + (i % 10), i % 2 == 0, 256 if i == 0 else 25) for i in range(16)]
        macro = MacroSlot(slot=2, name="Burst", repeat=3, events=events)
        payload = encode_macro_payload(macro)
        # 2 + 16*4 + 2 = 68 bytes -> 2 chunks (56 + 12)
        self.assertEqual(len(payload), 68)
        self.assertEqual(struct.unpack_from("<H", payload, 4)[0], 255)  # 256 -> 255 quirk

        client.set_macro(macro)
        self.assertEqual(len(tr.macro_chunks), 2)
        self.assertEqual(tr.macro_chunks[0][0:4], (2, 0, 68, 0))
        self.assertEqual(tr.macro_chunks[1][0:4], (2, 1, 68, 1))

        read_back = client.get_macro(2, name="Burst")
        self.assertEqual(read_back.repeat, 3)
        self.assertEqual(len(read_back.events), 15)  # 64-byte GetMacro read holds up to 15 events
        self.assertEqual(read_back.events[0].delay_ms, 255)

    def test_backup_and_restore_roundtrip(self) -> None:
        _, client = self._make_client()
        client.set_polling_rate(4000)
        client.set_lod("0.7mm")
        client.set_debounce(2)
        client.set_motion_sync(False)
        client.set_angle_snap(True)
        client.set_ripple_control(True)
        client.set_latency_mode("extreme")
        client.set_fps_mode("20k")
        client.set_sensor_rotation(-12)
        client.set_dpi_stages([DpiStage(800, 800, "#112233"), DpiStage(1600, 1600, "#445566")], active_index=1)
        backup = client.export_backup()

        client.restore_factory()
        client.import_backup(backup)
        restored = client.read_all_state()
        self.assertEqual(restored.polling_hz, 4000)
        self.assertEqual(restored.lod_mm, "0.7mm")
        self.assertEqual(restored.debounce_ms, 2)
        self.assertFalse(restored.motion_sync)
        self.assertTrue(restored.angle_snap)
        self.assertTrue(restored.ripple_control)
        self.assertEqual(restored.latency_mode, 1)
        self.assertEqual(restored.fps_mode, 1)
        self.assertEqual(restored.sensor_rotation, -12)
        self.assertEqual(len(restored.dpi_stages), 2)
        self.assertEqual(restored.dpi_stages[1].color, "#445566")


if __name__ == "__main__":
    unittest.main()
