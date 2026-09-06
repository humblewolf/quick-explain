#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Quick Explain Shortcut Setup ==="
echo "Project directory: $SCRIPT_DIR"

# 1. Make launch.sh executable
chmod +x "$SCRIPT_DIR/launch.sh"

# 2. Copy desktop entry file to user applications directory
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat <<EOF > "$DESKTOP_DIR/com.quickexplain.app.desktop"
[Desktop Entry]
Name=Quick Explain
Comment=Global text explanation utility using LLM
Exec=$SCRIPT_DIR/launch.sh
Icon=$SCRIPT_DIR/assets/logo.png
Terminal=false
Type=Application
Categories=Utility;Development;
StartupWMClass=com.quickexplain.app
EOF

echo "✓ Installed desktop file to $DESKTOP_DIR/com.quickexplain.app.desktop"

# 3. Configure GNOME shortcut via gsettings
KEY_PATH="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/quick-explain/"

CURRENT=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)

if [[ "$CURRENT" == "@as []" ]] || [[ "$CURRENT" == "[]" ]]; then
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/quick-explain/']"
elif [[ "$CURRENT" != *"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/quick-explain/"* ]]; then
    NEW_BINDINGS=$(echo "$CURRENT" | sed "s|\]|, '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/quick-explain/']|")
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$NEW_BINDINGS"
fi

gsettings set $KEY_PATH name 'Quick Explain'
gsettings set $KEY_PATH command "$SCRIPT_DIR/launch.sh"
gsettings set $KEY_PATH binding '<Control><Shift>e'

echo "✓ Registered global shortcut Ctrl+Shift+E in GNOME Shell"
echo "=== Quick Explain setup complete! ==="
