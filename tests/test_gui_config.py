"""Unit tests for GUI configuration, wallpaper storage, and device serialization."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from vgn_hub import gui
from vgn_hub.registry import find_device_spec
from vgn_hub.transport import HidDeviceInfo


class TestGuiConfigAndWallpaper(unittest.TestCase):
    def test_default_config_contains_wallpaper_and_finish(self) -> None:
        cfg = gui._default_config()
        self.assertEqual(cfg["mouse_finish"], "obsidian")
        self.assertIn("wallpaper", cfg)
        wp = cfg["wallpaper"]
        self.assertEqual(wp["mode"], "preset")
        self.assertEqual(wp["preset"], "vgn-crimson")
        self.assertEqual(wp["blur"], 0)
        self.assertEqual(wp["dim"], 28)
        self.assertEqual(wp["opacity"], 88)
        self.assertTrue(wp["watermark"])
        self.assertEqual(wp["custom_path"], "")
        self.assertEqual(wp["custom_url"], "")

    def test_load_config_backward_compatibility_with_legacy_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp)
            cfg_file = cfg_dir / "config.json"
            wp_dir = cfg_dir / "wallpapers"
            legacy_payload = {
                "lang": "en",
                "theme": "solid",
                "macros": [{"slot": 0, "name": "Burst", "repeat": 3, "events": []}],
            }
            cfg_file.write_text(json.dumps(legacy_payload), encoding="utf-8")

            with patch.object(gui, "CONFIG_DIR", cfg_dir), patch.object(
                gui, "CONFIG_FILE", cfg_file
            ), patch.object(gui, "WALLPAPER_DIR", wp_dir):
                loaded = gui._load_config()

            self.assertEqual(loaded["lang"], "en")
            self.assertEqual(loaded["theme"], "solid")
            self.assertEqual(loaded["mouse_finish"], "obsidian")
            self.assertEqual(loaded["wallpaper"]["preset"], "vgn-crimson")
            self.assertEqual(loaded["wallpaper"]["mode"], "preset")
            self.assertEqual(loaded["macros"][0]["name"], "Burst")
            self.assertEqual(loaded["macros"][0]["repeat"], 3)
            self.assertEqual(len(loaded["macros"]), 16)

    def test_normalize_wallpaper_clamps_and_resolves_custom_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp) / "bg.png"
            img.write_bytes(b"\x89PNG\r\n\x1a\nfake")

            norm = gui._normalize_wallpaper(
                {
                    "mode": "custom",
                    "preset": "nonexistent-theme",
                    "custom_path": str(img),
                    "blur": 999,
                    "dim": -10,
                    "opacity": 5,
                    "watermark": False,
                }
            )
            self.assertEqual(norm["mode"], "custom")
            self.assertEqual(norm["preset"], "vgn-crimson")
            self.assertEqual(norm["blur"], 24)
            self.assertEqual(norm["dim"], 0)
            self.assertEqual(norm["opacity"], 25)
            self.assertFalse(norm["watermark"])
            self.assertTrue(norm["custom_url"].startswith("file://"))
            self.assertIn("?v=", norm["custom_url"])

            missing = gui._normalize_wallpaper(
                {
                    "mode": "custom",
                    "preset": "cyber-indigo",
                    "custom_path": str(Path(tmp) / "missing.png"),
                }
            )
            self.assertEqual(missing["mode"], "preset")
            self.assertEqual(missing["preset"], "cyber-indigo")
            self.assertEqual(missing["custom_path"], "")
            self.assertEqual(missing["custom_url"], "")

    def test_install_and_clear_custom_wallpaper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wp_dir = root / "wallpapers"
            src1 = root / "first.png"
            src2 = root / "second.webp"
            bad_ext = root / "notes.txt"
            big_img = root / "huge.jpg"
            src1.write_bytes(b"png-bytes-1")
            src2.write_bytes(b"webp-bytes-2")
            bad_ext.write_text("not an image", encoding="utf-8")
            big_img.write_bytes(b"0" * 64)

            installed1 = gui._install_custom_wallpaper(src1, wallpaper_dir=wp_dir)
            self.assertTrue(installed1.is_file())
            self.assertEqual(installed1.parent, wp_dir)
            self.assertEqual(installed1.suffix, ".png")

            time.sleep(0.005)
            installed2 = gui._install_custom_wallpaper(src2, wallpaper_dir=wp_dir)
            self.assertTrue(installed2.is_file())
            self.assertFalse(installed1.exists())
            self.assertEqual(installed2.suffix, ".webp")

            with self.assertRaises(ValueError):
                gui._install_custom_wallpaper(bad_ext, wallpaper_dir=wp_dir)

            with patch.object(gui, "MAX_WALLPAPER_BYTES", 16):
                with self.assertRaises(ValueError):
                    gui._install_custom_wallpaper(big_img, wallpaper_dir=wp_dir)

            gui._clear_custom_wallpaper_files(wallpaper_dir=wp_dir)
            self.assertFalse(installed2.exists())

    def test_serialize_device(self) -> None:
        spec = find_device_spec(0x391D, 0x1A25)
        self.assertIsNotNone(spec)
        dev = HidDeviceInfo(
            path="/dev/hidraw3",
            vid=0x391D,
            pid=0x1A25,
            name="VGN Receiver",
            bcd_device="0512",
            phys="usb-0000:00:14.0-1/input1",
            usage_page=0xFFFF,
            usage=0x0002,
            accessible=True,
            spec=spec,
        )
        out = gui._serialize_device(dev)
        self.assertEqual(out["path"], "/dev/hidraw3")
        self.assertEqual(out["vid_pid"], "391d:1a25")
        self.assertTrue(out["is_wireless"])
        self.assertEqual(out["model_name"], "Dragonfly 3 Ultra")
        self.assertEqual(out["sensor"], "PAW3950")
        self.assertEqual(out["dpi_max"], 42000)


if __name__ == "__main__":
    unittest.main()
