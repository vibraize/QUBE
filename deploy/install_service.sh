#!/bin/bash
# deploy/install_service.sh - start QUBE automatically at boot (systemd service).
#
#   sudo bash deploy/install_service.sh          # LED panels: what the finished QUBE uses
#   sudo bash deploy/install_service.sh web      # browser preview instead (for testing)
#
# After this QUBE starts by itself whenever it's plugged in, with the panels dark
# until you press the clicker's square button (START_WITH_LEDS_OFF in config.py).
#
# Watch its output:      journalctl -u qube -f
# Stop / start:          sudo systemctl stop qube    /    sudo systemctl start qube
# Turn auto-start off:   sudo systemctl disable --now qube
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run with sudo:  sudo bash $0 ${1:-}"
    exit 1
fi

DISPLAY_MODE="${1:-matrix}"
PYTHON="${PYTHON:-/usr/bin/python3}"     # a virtual environment? run: sudo PYTHON=/path/to/python3 bash ...
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"

case "$DISPLAY_MODE" in
    web|matrix|none) ;;
    *) echo "Unknown display '$DISPLAY_MODE' (use web, matrix or none)"; exit 1 ;;
esac

sed -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__PROJECT__|$PROJECT|g" \
    -e "s|__DISPLAY__|$DISPLAY_MODE|g" \
    "$PROJECT/deploy/qube.service" > /etc/systemd/system/qube.service

systemctl daemon-reload
systemctl enable qube.service
systemctl restart qube.service
echo "Installed and started (display: $DISPLAY_MODE). Recent output:"
sleep 5
journalctl -u qube -n 20 --no-pager || true
