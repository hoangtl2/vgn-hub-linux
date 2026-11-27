"""Unit tests for device registry, Waybar telemetry, key parser, and CLI."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from vgn_hub import cli
from vgn_hub.keycodes import parse_key_combo
from vgn_hub.protocols.base import BatteryInfo
from vgn_hub.registry import find_device_spec, list_supported_models
from tests.test_ry_protocol import MockFeatureTransport


class TestRegistryAndWaybar(unittest.TestCase):
    def test_registry_lookup(self) -> None:
        wired = find_device_spec(0x391D, 0x1028)
        wireless = find_device_spec(0x391D, 0x1A25)
        self.assertIsNotNone(wired)
        self.assertIsNotNone(wireless)
        assert wired is not None and wireless is not None
        self.assertEqual(wired.name, "Dragonfly 3 Ultra")
        self.assertFalse(wired.is_wireless_receiver)
        self.assertTrue(wireless.is_wireless_receiver)
        self.assertEqual(wired.dpi_max, 42000)

        models = list_supported_models()
        self.assertGreaterEqual(len(models), 6)

    def test_waybar_battery_states(self) -> None:
        ok = BatteryInfo(85, True, False, True, "Dragonfly 3 Ultra", "391d:1a25", "0512").to_waybar_json()
        self.assertEqual(ok["class"], "ok")
        self.assertIn("85%", ok["text"])

        low = BatteryInfo(15, True, False, True, "Dragonfly 3 Ultra", "391d:1a25", "0512").to_waybar_json()
        self.assertEqual(low["class"], "low")

        slp = BatteryInfo(0, True, True, True, "Dragonfly 3 Ultra", "391d:1a25", "0512").to_waybar_json()
        self.assertEqual(slp["class"], "sleep")

        off = BatteryInfo(None, False, False, False, "VGN Mouse", "").to_waybar_json()
        self.assertEqual(off["class"], "disconnected")

    def test_parse_key_combo_orders_modifiers_first(self) -> None:
        self.assertEqual(parse_key_combo("C + Ctrl + Shift"), [224, 225, 0x06])
        self.assertEqual(parse_key_combo("F5"), [0x3E])

    def test_cli_status_and_battery_json(self) -> None:
        tr = MockFeatureTransport(wireless=False)

        with patch("vgn_hub.cli.discover_devices", return_value=[tr.info]), patch(
            "vgn_hub.cli.FeatureHidTransport", return_value=tr
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["status", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["device_name"], "Dragonfly 3 Ultra")
            self.assertEqual(payload["polling_hz"], 500)

            buf2 = io.StringIO()
            with redirect_stdout(buf2):
                rc2 = cli.main(["battery", "--waybar"])
            self.assertEqual(rc2, 0)
            wb = json.loads(buf2.getvalue())
            self.assertEqual(wb["class"], "ok")
            self.assertIn("88%", wb["text"])


if __name__ == "__main__":
    unittest.main()
