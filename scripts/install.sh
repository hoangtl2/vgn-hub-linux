#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
UDEV_RULE_DST="/etc/udev/rules.d/99-vgn-hub.rules"
LEGACY_HIDRAW_RULE="/etc/udev/rules.d/99-vgn-dragonfly-hidraw.rules"

mkdir -p "$BIN_DIR" "$APP_DIR"

ln -sf "$REPO_DIR/vgn-hub" "$BIN_DIR/vgn-hub"
ln -sf "$REPO_DIR/vgn-hub-gui" "$BIN_DIR/vgn-hub-gui"
cp "$REPO_DIR/packaging/vgn-hub-linux.desktop" "$APP_DIR/vgn-hub-linux.desktop"

echo "Đã cài đặt symlink vào $BIN_DIR và launcher vào $APP_DIR."
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Lưu ý: Hãy thêm $BIN_DIR vào PATH để gọi lệnh trực tiếp." ;;
esac

if [ ! -f "$UDEV_RULE_DST" ] && [ ! -f "$LEGACY_HIDRAW_RULE" ]; then
  echo ""
  echo "Chưa phát hiện udev rule cho thiết bị VGN (391d)."
  echo "Để chạy không cần root, hãy chạy:"
  echo "  sudo cp \"$REPO_DIR/packaging/99-vgn-hub.rules\" \"$UDEV_RULE_DST\""
  echo "  sudo udevadm control --reload-rules && sudo udevadm trigger"
else
  echo "Đã phát hiện udev rule cho VGN (391d)."
fi
