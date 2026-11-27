# Changelog

## v0.1.0 (2026-11-27)

### Tính năng ban đầu / Initial Release
- Giao diện desktop **GTK4 + WebKitGTK6** (`vgn-hub-gui`) và công cụ dòng lệnh **CLI** (`vgn-hub`) chạy thuần Python stdlib + Linux `/dev/hidraw*` + `PyGObject` / `WebKitGTK6` hệ thống, không cần thư viện `pip` hay `npm` ngoài.
- Hỗ trợ **VGN Dragonfly 3 Ultra** (`391d:1028` có dây USB & `391d:1a25` dongle 2.4GHz), kèm registry mở rộng cho các mẫu `vgn-ry-mouse` cùng họ (`Dragonfly 3 Pro Max`, `Dragonfly Y2 V2 Pro Max`, `Dragonfly F1 V2 Pro Max`, `Dragonfly F1 V5 Ultra`, `Dragonfly F2 V2 Ultra`).
- Đầy đủ chức năng cấu hình:
  - **Key Binding (6 nút)**: Chuột, DPI/Scroll, tổ hợp phím bàn phím, Multimedia/System, Macro và Disable.
  - **DPI Settings (1–6 nấc)**: `50–42,000 DPI` (step 50), hỗ trợ X/Y độc lập, đổi màu LED từng nấc và chuyển nấc DPI trực tiếp (đồng bộ realtime khi nhấn nút DPI vật lý).
  - **Performance**: Polling Rate `125Hz–8000Hz` và Sensor Sampling Rate (`Basic` / `Supreme Competitive ≥20K FPS`).
  - **Macros (16 slot)**: Ghi phím/chuột, chỉnh sửa bước & delay, ghi vào bộ nhớ chuột.
  - **Sensor Rotation**: Xoay góc cảm biến `-90°..+90°` với núm xoay trực quan.
  - **Parameters**: `LOD (0.7 / 1 / 2mm)`, `Latency Mode (Stable / Extreme)`, `Motion Sync`, `Button Debounce (1..20ms)`, `Straight-Line Correction`, `Wave Control`, `Sleep Timer (10s..10m)`.
  - **Profile 1–4**, **Backup / Restore JSON**, **Factory Reset**, giao diện **3 cột Dark Glass**, chuyển đổi **Tiếng Việt / English**, và theo dõi **% pin** hỗ trợ xuất JSON cho **Waybar**.
