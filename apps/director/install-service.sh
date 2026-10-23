#!/usr/bin/env bash
# Run XPSR Director as a systemd user service, so it survives logouts of the
# terminal and starts with the machine. Undo with:
#   systemctl --user disable --now xpsr-director && rm ~/.config/systemd/user/xpsr-director.service
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
port="${1:-8790}"
unit="$HOME/.config/systemd/user/xpsr-director.service"
mkdir -p "$(dirname "$unit")"
cat > "$unit" <<UNIT
[Unit]
Description=XPSR Director (workshop phone app, local GPU and Google Flow bridge)
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 $here/server.py --host 127.0.0.1 --port $port
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now xpsr-director
systemctl --user --no-pager status xpsr-director | head -5
echo "Access code: grep XPSR_ACCESS_CODE ~/.config/xpsr-director/env"
