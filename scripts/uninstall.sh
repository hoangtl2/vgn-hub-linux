#!/usr/bin/env bash
set -euo pipefail

rm -f "${HOME}/.local/bin/vgn-hub"
rm -f "${HOME}/.local/bin/vgn-hub-gui"
rm -f "${HOME}/.local/share/applications/vgn-hub-linux.desktop"

echo "Đã gỡ symlink khỏi ~/.local/bin và desktop entry khỏi ~/.local/share/applications."
