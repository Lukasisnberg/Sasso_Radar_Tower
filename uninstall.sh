#!/usr/bin/env bash
set -euo pipefail

# Sasso Radar Tower — uninstall script
# Run as root:  sudo bash uninstall.sh

info()  { echo -e "\033[0;32m[SRT]\033[0m $*"; }
warn()  { echo -e "\033[0;33m[SRT]\033[0m $*"; }

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (sudo bash uninstall.sh)" >&2
    exit 1
fi

info "Stopping services..."
systemctl stop flugradar-display.service 2>/dev/null || true
systemctl stop flugradar-web.service 2>/dev/null || true

info "Disabling services..."
systemctl disable flugradar-display.service 2>/dev/null || true
systemctl disable flugradar-web.service 2>/dev/null || true

info "Removing service files..."
rm -f /etc/systemd/system/flugradar-display.service
rm -f /etc/systemd/system/flugradar-web.service
systemctl daemon-reload

info "Removing Plymouth theme..."
rm -rf /usr/share/plymouth/themes/sasso-radar
update-initramfs -u 2>/dev/null || true

echo ""
info "Services and theme removed."
info "Project files in /home/pi/sasso-radar-tower and /home/pi/.env were kept."
info "Remove manually if no longer needed:"
echo "  rm -rf /home/pi/sasso-radar-tower"
echo "  rm /home/pi/.env"
echo ""
