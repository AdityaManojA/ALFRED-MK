# Cross-Platform Live Verification Matrix

## Feature × OS Verification Checklist

| Feature | Windows 10/11 | macOS 11+ (Intel/Apple Silicon) | Linux (X11 / Wayland) | Verification Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Boot & Initialisation** | ✅ Verified | ✅ Verified (Defaults to Gemini Live) | ✅ Verified (Defaults to Gemini Live) | Boots cleanly without requiring Ollama daemon |
| **Visual HUD Playback** | ✅ Verified | ✅ Verified (AVFoundation backend) | ✅ Verified (GStreamer backend) | VP9 / H.264 / Opus streams render smoothly |
| **Settings Overlay Layering** | ✅ Verified | ✅ Verified (DWM/Quartz elevated) | ✅ Verified (Compositor independent) | Modal dialogs raise above video canvas |
| **Minimised HUD** | ✅ Verified | ✅ Verified (Frameless floating window) | ✅ Verified (Floating WM rule supported) | Clamps within available screen bounds |
| **TTS Synthesis** | ✅ Verified | ✅ Verified (Edge/Kokoro/say) | ✅ Verified (Edge/Kokoro/espeak) | Voice synthesizes with automatic ducking |
| **STT Voice Input** | ✅ Verified | ✅ Verified (PortAudio stream) | ✅ Verified (PortAudio stream) | Microphone captures voice packets cleanly |
| **Sentry FOCUS & Drift** | ✅ Verified | ✅ Verified (`lsappinfo` + AppleScript) | ✅ Verified (`xdotool` + Wayland IPC) | Realtime frontmost surface inspection |
| **Volume & Media Control** | ✅ Verified | ✅ Verified (AppleScript / Music.app) | ✅ Verified (`pactl` / `playerctl`) | Volume and pause/resume dispatch smoothly |
| **Screenshot Capture** | ✅ Verified | ✅ Verified (`screencapture -x`) | ✅ Verified (`maim` / `grim` / `mss`) | Encodes and delivers to uplink / vision |
| **Idle CPU Footprint** | ✅ ~0% | ✅ ~0% | ✅ ~0% | No hot spin loops, timers bounded to >= 1 Hz |
