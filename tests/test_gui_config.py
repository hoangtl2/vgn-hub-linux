"""Unit tests for GUI configuration, wallpaper storage, and device serialization."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from vgn_hub import config
from vgn_hub.registry import find_device_spec
from vgn_hub.transport import HidDeviceInfo

try:
    import gi

    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    _HAS_GDKPIXBUF = True
except (ImportError, ValueError):
    _HAS_GDKPIXBUF = False


class TestGuiConfigAndWallpaper(unittest.TestCase):
    def test_default_config_contains_wallpaper_and_finish(self) -> None:
        cfg = config._default_config()
        self.assertEqual(cfg["mouse_finish"], "obsidian")
        self.assertIn("wallpaper", cfg)
        wp = cfg["wallpaper"]
        self.assertEqual(wp["mode"], "preset")
        self.assertEqual(wp["preset"], "vgn-crimson")
        self.assertEqual(wp["blur"], 0)
        self.assertEqual(wp["dim"], 28)
        self.assertEqual(wp["opacity"], 88)
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

            with patch.object(config, "CONFIG_DIR", cfg_dir), patch.object(
                config, "CONFIG_FILE", cfg_file
            ), patch.object(config, "WALLPAPER_DIR", wp_dir):
                loaded = config._load_config()

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

            norm = config._normalize_wallpaper(
                {
                    "mode": "custom",
                    "preset": "nonexistent-theme",
                    "custom_path": str(img),
                    "blur": 999,
                    "dim": -10,
                    "opacity": 5,
                }
            )
            self.assertEqual(norm["mode"], "custom")
            self.assertEqual(norm["preset"], "vgn-crimson")
            self.assertEqual(norm["blur"], 24)
            self.assertEqual(norm["dim"], 0)
            self.assertEqual(norm["opacity"], 25)
            self.assertTrue(norm["custom_url"].startswith("file://"))
            self.assertIn("?v=", norm["custom_url"])

            missing = config._normalize_wallpaper(
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

            installed1 = config._install_custom_wallpaper(src1, wallpaper_dir=wp_dir)
            self.assertTrue(installed1.is_file())
            self.assertEqual(installed1.parent, wp_dir)
            self.assertEqual(installed1.suffix, ".png")

            time.sleep(0.005)
            installed2 = config._install_custom_wallpaper(src2, wallpaper_dir=wp_dir)
            self.assertTrue(installed2.is_file())
            self.assertFalse(installed1.exists())
            self.assertEqual(installed2.suffix, ".webp")

            with self.assertRaises(ValueError):
                config._install_custom_wallpaper(bad_ext, wallpaper_dir=wp_dir)

            with patch.object(config, "MAX_WALLPAPER_BYTES", 16):
                with self.assertRaises(ValueError):
                    config._install_custom_wallpaper(big_img, wallpaper_dir=wp_dir)

            config._clear_custom_wallpaper_files(wallpaper_dir=wp_dir)
            self.assertFalse(installed2.exists())

    def test_install_copies_original_when_downscale_not_needed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "photo.jpg"
            src.write_bytes(b"jpeg-bytes")
            with patch.object(config, "_downscale_wallpaper", return_value=None) as ds:
                dest = config._install_custom_wallpaper(src, wallpaper_dir=root / "wp", max_edge=1234)
            ds.assert_called_once()
            self.assertEqual(ds.call_args.kwargs["max_edge"], 1234)
            self.assertEqual(dest.suffix, ".jpg")
            self.assertEqual(dest.read_bytes(), b"jpeg-bytes")

    def test_install_prefers_downscaled_output_and_cleans_old_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wp_dir = root / "wp"
            wp_dir.mkdir()
            stale = wp_dir / "custom_1.webp"
            stale.write_bytes(b"old")
            src = root / "huge.webp"
            src.write_bytes(b"webp-bytes")

            def fake_downscale(_src: Path, dest_stem: Path, max_edge: int) -> Path:
                out = dest_stem.with_suffix(".jpg")
                out.write_bytes(b"small")
                return out

            with patch.object(config, "_downscale_wallpaper", side_effect=fake_downscale):
                dest = config._install_custom_wallpaper(src, wallpaper_dir=wp_dir)

            self.assertEqual(dest.suffix, ".jpg")
            self.assertEqual(dest.read_bytes(), b"small")
            self.assertFalse(stale.exists())
            self.assertEqual(sorted(p.name for p in wp_dir.iterdir()), [dest.name])

    def test_downscale_skips_gif_without_touching_gdkpixbuf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "anim.gif"
            src.write_bytes(b"GIF89a")
            self.assertIsNone(config._downscale_wallpaper(src, Path(tmp) / "out", max_edge=10))

    @unittest.skipUnless(_HAS_GDKPIXBUF, "GdkPixbuf (PyGObject) not available")
    def test_downscale_real_images_with_gdkpixbuf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wp_dir = root / "wp"

            def make(name: str, w: int, h: int, alpha: bool, fmt: str) -> Path:
                pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, alpha, 8, w, h)
                pb.fill(0x3366CC80 if alpha else 0x3366CCFF)
                path = root / name
                pb.savev(str(path), fmt, [], [])
                return path

            # Opaque oversized image -> JPEG, aspect ratio preserved
            wide = make("wide.png", 4000, 1000, False, "png")
            out = config._install_custom_wallpaper(wide, wallpaper_dir=wp_dir, max_edge=2560)
            _fmt, w, h = GdkPixbuf.Pixbuf.get_file_info(str(out))
            self.assertEqual(out.suffix, ".jpg")
            self.assertEqual((w, h), (2560, 640))

            # Transparent oversized image -> PNG keeps alpha
            time.sleep(0.005)
            tall = make("tall.png", 1500, 3000, True, "png")
            out = config._install_custom_wallpaper(tall, wallpaper_dir=wp_dir, max_edge=2560)
            self.assertEqual(out.suffix, ".png")
            reloaded = GdkPixbuf.Pixbuf.new_from_file(str(out))
            self.assertTrue(reloaded.get_has_alpha())
            self.assertEqual((reloaded.get_width(), reloaded.get_height()), (1280, 2560))

            # Already small -> byte-identical copy, original format kept
            time.sleep(0.005)
            small = make("small.png", 800, 600, False, "png")
            out = config._install_custom_wallpaper(small, wallpaper_dir=wp_dir, max_edge=2560)
            self.assertEqual(out.suffix, ".png")
            self.assertEqual(out.read_bytes(), small.read_bytes())
            self.assertEqual(len(list(wp_dir.iterdir())), 1)

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
        out = config._serialize_device(dev)
        self.assertEqual(out["path"], "/dev/hidraw3")
        self.assertEqual(out["vid_pid"], "391d:1a25")
        self.assertTrue(out["is_wireless"])
        self.assertEqual(out["model_name"], "Dragonfly 3 Ultra")
        self.assertEqual(out["sensor"], "PAW3950")
        self.assertEqual(out["dpi_max"], 42000)


if __name__ == "__main__":
    unittest.main()
