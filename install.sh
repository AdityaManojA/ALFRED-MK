#!/usr/bin/env bash
# ==============================================================================
# ALFRED-MK-V / MARK-IX: Linux One-Step Installation Script
# Installs system dependencies (PortAudio, PulseAudio, X11 utilities) and runs setup.py
# ==============================================================================

set -e

echo "⚙ Starting ALFRED Linux installation..."

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "▶ Detected Linux environment."

    # Check for Debian / Ubuntu apt
    if command -v apt-get &> /dev/null; then
        echo "▶ Updating APT and installing PortAudio & audio utilities..."
        sudo apt-get update
        sudo apt-get install -y \
            portaudio19-dev \
            python3-pyaudio \
            pulseaudio-utils \
            libasound2-dev \
            xdotool \
            brightnessctl
        echo "✅ System audio libraries installed successfully."
    elif command -v dnf &> /dev/null; then
        echo "▶ Detected Fedora/RHEL. Installing portaudio-devel..."
        sudo dnf install -y portaudio-devel alsa-lib-devel pulseaudio-utils xdotool
    elif command -v pacman &> /dev/null; then
        echo "▶ Detected Arch Linux. Installing portaudio..."
        sudo pacman -S --noconfirm portaudio pulseaudio xdotool
    else
        echo "⚠️  Unknown package manager. Please ensure 'portaudio19-dev' or equivalent is installed."
    fi
fi

# Run setup.py
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "▶ Executing setup.py with $PYTHON_CMD..."
$PYTHON_CMD setup.py

echo "✅ ALFRED Linux installation script finished."
