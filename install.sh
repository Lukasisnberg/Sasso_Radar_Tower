#!/usr/bin/env bash
set -euo pipefail

# Sasso Radar Tower — Raspberry Pi install script
# Run as root:  sudo bash install.sh

INSTALL_DIR="/home/pi/sasso-radar-tower"
VENV_DIR="${INSTALL_DIR}/.venv"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

info()  { echo -e "\033[0;32m[SRT]\033[0m $*"; }
warn()  { echo -e "\033[0;33m[SRT]\033[0m $*"; }
error() { echo -e "\033[0;31m[SRT]\033[0m $*" >&2; }

# --- Pre-flight checks ---
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (sudo bash install.sh)"
    exit 1
fi

info "Installing Sasso Radar Tower..."

# --- System packages ---
info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip python3-dev \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libfreetype6-dev libjpeg-dev libpng-dev \
    fonts-dejavu-core \
    plymouth \
    python3-pil \
    git

# --- Copy project ---
info "Setting up project in ${INSTALL_DIR}..."
if [[ "${REPO_DIR}" != "${INSTALL_DIR}" ]]; then
    mkdir -p "${INSTALL_DIR}"
    rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
        --exclude='*.egg-info' --exclude='.pytest_cache' \
        "${REPO_DIR}/" "${INSTALL_DIR}/"
fi
chown -R pi:pi "${INSTALL_DIR}"

# --- Python venv + dependencies ---
info "Creating virtual environment..."
sudo -u pi python3 -m venv "${VENV_DIR}"
sudo -u pi "${VENV_DIR}/bin/pip" install --upgrade pip
sudo -u pi "${VENV_DIR}/bin/pip" install -e "${INSTALL_DIR}[display,web]"

# --- Environment file ---
if [[ ! -f /home/pi/.env ]]; then
    info "Creating default .env from template..."
    cp "${INSTALL_DIR}/.env.example" /home/pi/.env
    chown pi:pi /home/pi/.env
    warn "Edit /home/pi/.env to set your location and API keys."
fi

# --- systemd services ---
info "Installing systemd services..."
cp "${INSTALL_DIR}/system/systemd/flugradar-display.service" /etc/systemd/system/
cp "${INSTALL_DIR}/system/systemd/flugradar-web.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable flugradar-display.service
systemctl enable flugradar-web.service

# --- Plymouth boot splash ---
info "Installing boot splash theme..."
THEME_DIR="/usr/share/plymouth/themes/sasso-radar"
mkdir -p "${THEME_DIR}"
cp "${INSTALL_DIR}/system/plymouth/sasso-radar.plymouth" "${THEME_DIR}/"
cp "${INSTALL_DIR}/system/plymouth/sasso-radar.script" "${THEME_DIR}/"

if command -v python3 &>/dev/null && python3 -c "from PIL import Image" 2>/dev/null; then
    python3 "${INSTALL_DIR}/system/plymouth/generate_logo.py" "${THEME_DIR}/logo.png"
else
    warn "Pillow not available — skipping logo generation."
fi

plymouth-set-default-theme sasso-radar 2>/dev/null || warn "Could not set Plymouth theme."
update-initramfs -u 2>/dev/null || warn "Could not update initramfs."

# --- DSI display config ---
CONFIG_TXT="/boot/firmware/config.txt"
if [[ ! -f "${CONFIG_TXT}" ]]; then
    CONFIG_TXT="/boot/config.txt"
fi

if [[ -f "${CONFIG_TXT}" ]]; then
    if ! grep -q "dtoverlay=vc4-kms-v3d" "${CONFIG_TXT}"; then
        info "Adding KMS overlay to ${CONFIG_TXT}..."
        echo "" >> "${CONFIG_TXT}"
        echo "# Sasso Radar Tower — display config" >> "${CONFIG_TXT}"
        echo "dtoverlay=vc4-kms-v3d" >> "${CONFIG_TXT}"
    fi
    if ! grep -q "disable_splash" "${CONFIG_TXT}"; then
        echo "disable_splash=1" >> "${CONFIG_TXT}"
    fi
fi

# --- Summary ---
echo ""
info "Installation complete!"
echo ""
echo "  Services:  flugradar-display, flugradar-web"
echo "  Config:    /home/pi/.env"
echo "  Portal:    http://$(hostname).local:5000"
echo "  Logs:      journalctl -u flugradar-display -f"
echo ""
echo "  Start now: sudo systemctl start flugradar-display flugradar-web"
echo "  Reboot to launch automatically."
echo ""
