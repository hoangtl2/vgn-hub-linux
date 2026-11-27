# VGN Hub Linux (`vgn-hub-linux`)

Ứng dụng giao diện desktop (**GTK4 + WebKitGTK6 Dark Glass**) và công cụ dòng lệnh (**CLI**) chạy thuần trên Linux (Wayland / X11) cho chuột gaming **VGN Dragonfly 3 Ultra** (`391d:1028` có dây USB & `391d:1a25` dongle 2.4GHz), được thiết kế theo kiến trúc mở rộng để dễ dàng bổ sung thêm chuột/bàn phím VGN khác — **không cần cài đặt thư viện `pip` hay `npm` ngoài**.

## Tính năng chính
- **Gán nút (Key Binding — 6 nút):** Chuột trái/phải/giữa, Tiến/Lùi bên hông, nút DPI, cuộn/nghiêng, tổ hợp phím bàn phím (`Ctrl + Shift + ...`), phím Multimedia/System, Macro hoặc Disable.
- **DPI Settings (1–6 nấc, `50–42,000 DPI`):** Chỉnh từng nấc (step 50), hỗ trợ tách riêng trục X/Y, đổi màu LED từng nấc DPI và đồng bộ realtime khi bấm nút DPI vật lý dưới đáy chuột.
- **Performance:** Chọn Polling Rate `125Hz → 8000Hz` (hình thanh bậc thang) và Sensor Sampling Rate (`Basic Mode` / `Supreme Competitive ≥20K FPS`).
- **Macros (16 slot):** Ghi trực tiếp phím/chuột kèm độ trễ thực tế hoặc chỉnh từng bước và nạp thẳng vào bộ nhớ chuột.
- **Sensor Rotation (`-90° .. +90°`):** Núm xoay cảm biến trực quan kèm mô phỏng góc chuột theo thời gian thực.
- **Parameters:** `LOD (0.7 / 1 / 2mm)`, `Latency Mode (Stable / Extreme)`, `Motion Sync`, `Button Debounce (1..20ms)`, `Straight-Line Correction`, `Wave Control`, `Sleep Timer (10s..10m)`.
- **Profile 1–4 & Sao lưu JSON:** Chuyển đổi nhanh 4 profile trên chuột, xuất/nhập file JSON, hỗ trợ **Tiếng Việt / English** và chế độ **Dark Glass / Solid**.
- **Theo dõi Pin & Waybar:** Đọc % pin qua cả cáp USB lẫn receiver 2.4GHz (`vgn-hub battery --waybar`).

## Thiết bị hỗ trợ (`vgn-ry-mouse`)

| Thiết bị | Sensor | DPI tối đa | Polling tối đa | USB Wired | Dongle 2.4GHz |
|---|---|---|---|---|---|
| **VGN Dragonfly 3 Ultra** *(đã kiểm chứng phần cứng thật)* | PAW3950 | 42,000 | 8000Hz | `391d:1028` | `391d:1a25` |
| VGN Dragonfly F1 V5 Ultra | PAW3950 | 42,000 | 8000Hz | `391d:102f` | `391d:1a2b` |
| VGN Dragonfly F2 V2 Ultra | PAW3950 | 42,000 | 8000Hz | `391d:1048` | `391d:1a41` |
| VGN Dragonfly 3 Pro Max | PAW3395 | 36,000 | 8000Hz | `391d:1004` | `391d:1a04` |
| VGN Dragonfly Y2 V2 Pro Max | PAW3395 | 36,000 | 8000Hz | `391d:1008` | `391d:1a08` |
| VGN Dragonfly F1 V2 Pro Max | PAW3395 | 36,000 | 8000Hz | `391d:1015` | `391d:1a13` |

## Yêu cầu hệ thống
- Linux với `/dev/hidraw*` và Python `>= 3.11`
- Gói hệ thống **GTK4 + Libadwaita + WebKitGTK6 (`PyGObject`)**:
  - **Fedora:** `sudo dnf install python3-gobject gtk4 libadwaita webkitgtk6.0`
  - **Arch:** `sudo pacman -S python-gobject gtk4 libadwaita webkitgtk-6.0`
  - **Ubuntu / Debian:** `sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0`

## Cài đặt

```bash
git clone https://github.com/hoangtl2/vgn-hub-linux.git
cd vgn-hub-linux
./scripts/install.sh
```

Cấp quyền `hidraw` để chạy không cần `sudo` (áp dụng cho toàn bộ thiết bị VGN VID `391d`):
```bash
sudo cp packaging/99-vgn-hub.rules /etc/udev/rules.d/99-vgn-hub.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
# Sau đó rút chuột/dongle ra cắm lại 1 lần
```

## Sử dụng

Mở giao diện đồ họa:
```bash
vgn-hub-gui
# hoặc chạy không tham số
vgn-hub
# hoặc xem thử giao diện không cần cắm chuột
vgn-hub-gui --demo
```

Hoặc dùng CLI:
```bash
vgn-hub status
vgn-hub battery --waybar
vgn-hub profile 1
vgn-hub dpi list
vgn-hub dpi active 2
vgn-hub dpi set 2 1600 --color "#00ff88"
vgn-hub polling 1000
vgn-hub angle -5
vgn-hub params --lod 1 --debounce 4 --motion-sync on --latency extreme
vgn-hub backup dragonfly-backup.json
vgn-hub restore dragonfly-backup.json
```

Tích hợp Waybar (`~/.config/waybar/config.jsonc`):
```jsonc
"custom/vgn-mouse": {
  "exec": "vgn-hub battery --waybar",
  "return-type": "json",
  "interval": 30
}
```

## Kiến trúc mở rộng
- `vgn_hub/registry.py`: Khai báo `DeviceSpec` theo từng cặp `VID:PID`.
- `vgn_hub/transport.py`: Giao tiếp Linux `/dev/hidraw*` qua `HIDIOCSFEATURE` / `HIDIOCGFEATURE` (kèm thread lắng nghe nút DPI phần cứng).
- `vgn_hub/protocols/`: Tách riêng module giao thức theo dòng sản phẩm (`ry_mouse.py` cho `vgn-ry-mouse`, dễ thêm dòng `vgn-king` / `vgn-byMs` / bàn phím về sau).
- `vgn_hub/web/`: Giao diện HTML/CSS/SVG chạy trong WebKitGTK6 giao tiếp trực tiếp qua `user_content_manager` IPC (không mở cổng HTTP).

## Kiểm thử

```bash
python3 -m unittest discover -s tests -v
./vgn-hub-gui --smoke-test
```

## License
[MIT](LICENSE)
