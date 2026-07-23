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
        ;;
    *)
        echo "[SRT] Unknown DISPLAY_BACKEND='${DISPLAY_BACKEND}' — use 'desktop' or 'kiosk'" >&2
        exit 1
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "${SCRIPT_DIR}/.venv/bin/flugradar-display" --size 720
