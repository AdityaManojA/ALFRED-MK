# Cross-Platform Installation & Setup Guide (macOS & Linux)

This guide documents the native environment prerequisites and installation commands to run ALFRED Mark-V on macOS and Linux with feature parity.

---

## 🍎 macOS Setup

### 1. Prerequisites (via Homebrew)
```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Core multimedia and audio libraries
brew install yt-dlp ffmpeg portaudio python-tk@3.12
```

### 2. Permissions (macOS TCC)
Grant permissions in **System Settings > Privacy & Security**:
- **Accessibility:** Required for simulated clicks and global shortcut interaction.
- **Screen Recording:** Required for Sentry Mode, visual screen recon, and screenshot capture.
- **Microphone:** Required for audio input.

### 3. Execution
```bash
pip install -r requirements.txt
python main.py
```

---

## 🐧 Linux Setup (Ubuntu / Debian / Arch / Fedora)

### 1. Prerequisites

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install -y python3-pyqt6 python3-tk yt-dlp ffmpeg \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav \
    xdotool wmctrl playerctl libportaudio2 maim
```

**Arch Linux:**
```bash
sudo pacman -S python-pyqt6 yt-dlp ffmpeg gst-plugins-good gst-plugins-bad gst-libav \
    xdotool wmctrl playerctl portaudio maim
```

**Fedora:**
```bash
sudo dnf install -y python3-qt6 yt-dlp ffmpeg \
    gstreamer1-plugins-good gstreamer1-plugins-bad-free gstreamer1-plugin-libav \
    xdotool wmctrl playerctl portaudio maim
```

### 2. Tiling Window Managers (i3 / sway / bspwm)
To enable floating and stay-on-top behavior for the Minimised HUD:
```text
# ~/.config/i3/config or ~/.config/sway/config
for_window [class="alfred" instance="minimizedHudOverlay"] floating enable, sticky enable
```

### 3. Execution
```bash
pip install -r requirements.txt
python main.py
```
