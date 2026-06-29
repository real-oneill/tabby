#!/bin/bash
# Configure the Adafruit Speaker Bonnet (MAX98357A I2S amp, product 3346) as the
# Pi's DEFAULT audio output, while leaving onboard HDMI audio available.
#
# Current Raspberry Pi OS uses PipeWire: once the device-tree overlay is enabled,
# PipeWire auto-detects the bonnet and exposes it as a sink. This script enables
# the overlay, then makes that sink the default and sets a sane volume. Tabby needs
# no change — it opens the ALSA/PipeWire default (output_device = None).
#
# Idempotent and two-phase: run it, reboot when told, then run it again.
#   Phase 1 (card not loaded): adds the overlay to config.txt (needs sudo) -> reboot.
#   Phase 2 (card present):    sets the bonnet as the PipeWire default sink (runs as you).
set -euo pipefail

OVERLAY="dtoverlay=max98357a"
VOLUME="0.90"

find_config() {
    for f in /boot/firmware/config.txt /boot/config.txt; do
        [ -f "$f" ] && { echo "$f"; return; }
    done
    echo "ERROR: no config.txt found (/boot/firmware/config.txt or /boot/config.txt)" >&2
    exit 1
}

# Echo the PipeWire sink id whose ALSA card is the MAX98357A, or nothing.
find_sink() {
    local ids id
    ids=$(wpctl status | awk '
        /Sinks:/  {f=1; next}
        /Sources:/{f=0}
        f { for (i=1; i<=NF; i++) if ($i ~ /^[0-9]+\.$/) { sub(/\./,"",$i); print $i } }')
    for id in $ids; do
        if wpctl inspect "$id" 2>/dev/null | grep -q 'alsa.card_name = "MAX98357A"'; then
            echo "$id"; return 0
        fi
    done
}

CONFIG="$(find_config)"
echo "Boot config: $CONFIG"

# --- Phase 1: ensure the I2S overlay is enabled (idempotent) ---------------
if grep -qE "^[[:space:]]*${OVERLAY}([[:space:],]|$)" "$CONFIG"; then
    echo "Overlay already enabled: $OVERLAY"
else
    echo "Adding overlay to $CONFIG: $OVERLAY"
    echo "$OVERLAY" | sudo tee -a "$CONFIG" >/dev/null
    echo
    echo ">>> Overlay added. REBOOT, then re-run this script:"
    echo ">>>   sudo reboot"
    exit 0
fi

# A previous version of this script wrote an ALSA override; on a PipeWire system
# that fights PipeWire for the raw card ("device busy"), so remove it.
if [ -f /etc/asound.conf ] && grep -q speakerbonnet /etc/asound.conf; then
    echo "Removing stale /etc/asound.conf (PipeWire handles routing)"
    sudo rm -f /etc/asound.conf
fi

# Tabby uses sounddevice/PortAudio (raw ALSA), which reaches PipeWire only through
# the ALSA bridge. Without it, PipeWire owns the cards exclusively and PortAudio sees
# no usable output device. Install the bridge so the ALSA "default" routes to PipeWire.
if ! aplay -L 2>/dev/null | grep -qx pipewire; then
    echo "Installing pipewire-alsa (ALSA -> PipeWire bridge)"
    sudo apt-get update -qq && sudo apt-get install -y pipewire-alsa
fi

# --- Phase 2: make the bonnet the PipeWire default sink --------------------
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if ! command -v wpctl >/dev/null 2>&1; then
    echo "ERROR: wpctl not found — is PipeWire/WirePlumber installed and running?" >&2
    exit 1
fi

SINK="$(find_sink || true)"
if [ -z "${SINK:-}" ]; then
    echo
    echo ">>> Overlay is set but no MAX98357A PipeWire sink yet."
    echo ">>> REBOOT and re-run this script:  sudo reboot"
    exit 0
fi

echo "MAX98357A is PipeWire sink id $SINK — setting it as the default output."
wpctl set-default "$SINK"
wpctl set-volume "$SINK" "$VOLUME"
wpctl set-mute   "$SINK" 0
echo "Default sink set, volume ${VOLUME}, unmuted. WirePlumber remembers this across reboots."
echo
echo "Test it:"
echo "  pw-play /usr/share/sounds/alsa/Front_Center.wav"
echo "  wpctl set-volume $SINK 5%+      # nudge volume"
echo
echo "Tabby needs no config change (Settings -> AUDIO OUTPUT = DEFAULT)."
echo "Relaunch it with: ./scripts/launch.sh"
