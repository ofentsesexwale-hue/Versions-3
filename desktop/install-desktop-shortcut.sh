#!/usr/bin/env bash
# Put an OVC CaseFile shortcut (Sebueng Itumeleng icon) on this user's desktop.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ICON="$ROOT/desktop/icons/icon-256.png"
LAUNCHER="$ROOT/start-desktop.sh"
DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

mkdir -p "$DESKTOP_DIR" "$APPS_DIR" "$ICON_DIR"
chmod +x "$LAUNCHER" || true
cp -f "$ICON" "$ICON_DIR/ovc-casefile.png"

write_entry() {
  local dest="$1"
  cat > "$dest" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=OVC CaseFile
Comment=Office case files for orphans and vulnerable children
Exec=$LAUNCHER
Icon=$ICON
Path=$ROOT
Terminal=false
StartupNotify=true
Categories=Office;Education;
StartupWMClass=ovc-casefile
EOF
  chmod +x "$dest"
}

write_entry "$DESKTOP_DIR/OVC-CaseFile.desktop"
write_entry "$APPS_DIR/ovc-casefile.desktop"

# Mark the launcher trusted so the desktop shows the icon instead of a .desktop file.
if command -v gio >/dev/null 2>&1; then
  gio set "$DESKTOP_DIR/OVC-CaseFile.desktop" metadata::trusted true 2>/dev/null || true
fi
# XFCE: turn desktop icons on if they were hidden.
if command -v xfconf-query >/dev/null 2>&1; then
  xfconf-query -c xfce4-desktop -p /desktop-icons/style -n -t int -s 2 2>/dev/null || true
  xfconf-query -c xfce4-desktop -p /desktop-icons/file-icons/show -n -t bool -s true 2>/dev/null || true
fi
gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "Shortcut on $DESKTOP_DIR/OVC-CaseFile.desktop"
echo "Uses icon $ICON"
