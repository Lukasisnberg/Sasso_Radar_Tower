#!/usr/bin/env bash
set -euo pipefail

# Sasso Radar Tower — Raspberry Pi install script
# Run as root:  sudo bash install.sh

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

info()  { echo -e "\033[0;32m[SRT]\033[0m $*"; }
warn()  { echo -e "\033[0;33m[SRT]\033[0m $*"; }
error() { echo -e "\033[0;31m[SRT]\033[0m $*" >&2; }

# --- Pre-flight checks ---
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (sudo bash install.sh)"
    exit 1
fi

# Determine the real user who invoked sudo
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    SRT_USER="${SUDO_USER}"
else
    error "Cannot determine target user. Run this script with: sudo bash install.sh"
    error "(Do not run as root directly — sudo is required to identify the user.)"
    exit 1
fi

SRT_HOME="$(eval echo "~${SRT_USER}")"
INSTALL_DIR="${SRT_HOME}/sasso-radar-tower"
VENV_DIR="${INSTALL_DIR}/.venv"
ENV_FILE="${SRT_HOME}/.env"

info "Installing Sasso Radar Tower for user '${SRT_USER}' (${SRT_HOME})..."

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

# UI typeface (Ausbaustufe 2, Schritt 3 -- docs/prompt-ausbaustufe-2.md):
# Inter / IBM Plex Sans, both OFL-licensed. Shipped via apt package rather
# than vendored binaries. Older Raspbian releases may not carry these
# packages -- not fatal, flugradar/display/fonts.py falls back through
# DejaVu/Noto/system sans (installed above) if neither is present.
if ! apt-get install -y -qq fonts-inter fonts-ibm-plex; then
    warn "fonts-inter/fonts-ibm-plex not available in this repo -- falling back to DejaVu"
fi

# --- Copy project ---
info "Setting up project in ${INSTALL_DIR}..."
if [[ "${REPO_DIR}" == "${INSTALL_DIR}" ]]; then
    info "Running in-place from ${INSTALL_DIR}, nothing to copy."
elif [[ -d "${INSTALL_DIR}/.git" ]]; then
    info "Existing git checkout found in ${INSTALL_DIR} -- leaving it as-is (use the in-app Update button for code updates, not a re-run of install.sh)."
elif git -C "${REPO_DIR}" remote get-url origin &>/dev/null; then
    # A real git clone (not just a copy) is what makes the in-app Update
    # button work later (flugradar/system/update.py does `git fetch` +
    # `git reset --hard origin/main` in place).
    ORIGIN_URL="$(git -C "${REPO_DIR}" remote get-url origin)"
    info "Cloning ${ORIGIN_URL} into ${INSTALL_DIR}..."
    mkdir -p "$(dirname "${INSTALL_DIR}")"
    sudo -u "${SRT_USER}" git clone "${ORIGIN_URL}" "${INSTALL_DIR}"
else
    warn "No git remote found in ${REPO_DIR} -- falling back to a plain copy. The in-app Update button won't work until ${INSTALL_DIR} is turned into a git clone manually."
    mkdir -p "${INSTALL_DIR}"
    rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
        --exclude='*.egg-info' --exclude='.pytest_cache' \
        "${REPO_DIR}/" "${INSTALL_DIR}/"
fi
chown -R "${SRT_USER}:${SRT_USER}" "${INSTALL_DIR}"

# --- Python venv + dependencies ---
info "Creating virtual environment..."
sudo -u "${SRT_USER}" python3 -m venv "${VENV_DIR}"
sudo -u "${SRT_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip
sudo -u "${SRT_USER}" "${VENV_DIR}/bin/pip" install -e "${INSTALL_DIR}[display,web]"

# --- Environment file ---
if [[ ! -f "${ENV_FILE}" ]]; then
    info "Creating default .env from template..."
    cp "${INSTALL_DIR}/.env.example" "${ENV_FILE}"
    chown "${SRT_USER}:${SRT_USER}" "${ENV_FILE}"
    warn "Edit ${ENV_FILE} to set your location and API keys."
fi

# --- Generate systemd service files with correct paths ---
info "Installing systemd services..."

cat > /etc/systemd/system/flugradar-display.service <<UNIT
[Unit]
Description=Sasso Radar Tower — Display
After=multi-user.target
Wants=multi-user.target

[Service]
Type=simple
User=${SRT_USER}
EnvironmentFile=-${ENV_FILE}
ExecStart=${INSTALL_DIR}/system/flugradar-display-start.sh
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/flugradar-web.service <<UNIT
[Unit]
Description=Sasso Radar Tower — Web Portal
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SRT_USER}
EnvironmentFile=-${ENV_FILE}
ExecStart=${INSTALL_DIR}/.venv/bin/flugradar-web --host 0.0.0.0 --port 5000
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

# --- Display start wrapper script ---
cat > "${INSTALL_DIR}/system/flugradar-display-start.sh" <<'WRAPPER'
#!/usr/bin/env bash
# Sasso Radar Tower — display start wrapper
# Selects desktop (X11/Xwayland) or kiosk (KMS/DRM) mode based on DISPLAY_BACKEND.

DISPLAY_BACKEND="${DISPLAY_BACKEND:-desktop}"

case "${DISPLAY_BACKEND}" in
    desktop)
        export SDL_VIDEODRIVER=x11
        export DISPLAY="${DISPLAY:-:0}"
        # Find XAUTHORITY — Xwayland/labwc often places it outside the default path
        if [[ -z "${XAUTHORITY:-}" ]]; then
            for candidate in \
                "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/.Xauthority" \
                "${HOME}/.Xauthority" \
                "/run/user/$(id -u)/Xauthority"; do
                if [[ -f "${candidate}" ]]; then
                    export XAUTHORITY="${candidate}"
                    break
                fi
            done
        fi
        ;;
    kiosk)
        export SDL_VIDEODRIVER=kmsdrm
        unset DISPLAY
        unset XAUTHORITY
        # pygame's bundled SDL2 (pygame.libs/) ships without KMSDRM support —
        # force the system SDL2 (has it compiled in) via LD_PRELOAD instead.
        if [[ -e /usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0 ]]; then
            export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0
        fi
        ;;
    *)
        echo "[SRT] Unknown DISPLAY_BACKEND='${DISPLAY_BACKEND}' — use 'desktop' or 'kiosk'" >&2
        exit 1
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "${SCRIPT_DIR}/.venv/bin/flugradar-display" --size 720
WRAPPER

chmod +x "${INSTALL_DIR}/system/flugradar-display-start.sh"
chown "${SRT_USER}:${SRT_USER}" "${INSTALL_DIR}/system/flugradar-display-start.sh"

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
echo "  User:      ${SRT_USER}"
echo "  Services:  flugradar-display, flugradar-web"
echo "  Config:    ${ENV_FILE}"
echo "  Portal:    http://$(hostname).local:5000"
echo "  Logs:      journalctl -u flugradar-display -f"
echo ""
echo "  Display mode: DISPLAY_BACKEND=desktop (default)"
echo "  Switch to kiosk: set DISPLAY_BACKEND=kiosk in ${ENV_FILE}, then also:"
echo "    sudo systemctl disable lightdm"
echo "    sudo systemctl set-default multi-user.target"
echo "  (kiosk mode needs exclusive DRM access — the desktop compositor must not"
echo "   auto-start, or SDL's kmsdrm driver will fail to grab the display)"
echo ""
echo "  Start now: sudo systemctl start flugradar-display flugradar-web"
echo "  Reboot to launch automatically."
echo ""
