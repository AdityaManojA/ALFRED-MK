#!/bin/bash
# Build ALFRED.app for macOS and install it as a login agent.
#
#   ALFRED.app/Contents/MacOS/ALFRED  = alfredd, the native "Hey Alfred" listener
#                                       (mac/alfredd/*.swift). It starts the
#                                       Python agent (main.py) when needed.
#
# Usage:  mac/build.sh              build + install to ~/Applications + start at login
#         ALFRED_PYTHON=/path/to/python mac/build.sh
#         mac/build.sh --uninstall  stop and remove the login agent (keeps the app)
#
# Note: the app is ad-hoc signed, so macOS treats every rebuild as a new app and
# asks for Microphone / Speech Recognition (and other) permissions again.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
APP="${ALFRED_APP:-$HOME/Applications/ALFRED.app}"
LABEL="local.alfred.assistant"
AGENT_PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SUPPORT="$HOME/Library/Application Support/ALFRED"
DOMAIN="gui/$(id -u)"

if [[ "${1:-}" == "--uninstall" ]]; then
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$AGENT_PLIST"
  echo "Login agent removed. Delete $APP yourself if you no longer want it."
  exit 0
fi

PY="${ALFRED_PYTHON:-}"
if [[ -z "$PY" ]]; then
  for c in "$(conda info --base 2>/dev/null)/envs/alfred/bin/python" \
           /opt/homebrew/Caskroom/miniconda/base/envs/alfred/bin/python \
           "$HOME/miniconda3/envs/alfred/bin/python" "$HOME/anaconda3/envs/alfred/bin/python"; do
    [[ -x "$c" ]] && PY="$c" && break
  done
fi
[[ -x "$PY" ]] || { echo "Python for the agent not found; set ALFRED_PYTHON=/path/to/python"; exit 1; }

echo "▶ Compiling alfredd"
mkdir -p "$REPO/build"
swiftc -O -swift-version 5 -target "$(uname -m)-apple-macos14.0" "$REPO"/mac/alfredd/*.swift -o "$REPO/build/ALFRED"

echo "▶ Assembling $APP"
STAGE="$REPO/build/ALFRED.app"
rm -rf "$STAGE"
mkdir -p "$STAGE/Contents/MacOS" "$STAGE/Contents/Resources"
cp "$REPO/build/ALFRED" "$STAGE/Contents/MacOS/ALFRED"
cp "$REPO/mac/Info.plist" "$STAGE/Contents/Info.plist"
ICONSET="$REPO/build/alfred.iconset"
rm -rf "$ICONSET" && mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$REPO/config/alfred.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2)); [[ $d -le 512 ]] && sips -z $d $d "$REPO/config/alfred.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$STAGE/Contents/Resources/alfred.icns"
codesign --force --sign - --identifier "$LABEL" "$STAGE"

echo "▶ Stopping any running ALFRED"
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
pkill -f "$APP/Contents/MacOS/ALFRED" 2>/dev/null || true
pkill -f "python -u main.py" 2>/dev/null || true
for _ in 1 2 3 4 5 6; do pgrep -f "python -u main.py" >/dev/null || break; sleep 0.5; done
pkill -9 -f "python -u main.py" 2>/dev/null || true   # the dashboard's uvicorn can swallow SIGTERM
sleep 1

rm -rf "$APP"
mkdir -p "$(dirname "$APP")"
cp -R "$STAGE" "$APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"

echo "▶ Writing $SUPPORT/daemon.json"
mkdir -p "$SUPPORT"
"$PY" - "$SUPPORT/daemon.json" "$REPO" "$PY" <<'EOF'
import json, sys, os
path, repo, py = sys.argv[1:4]
cfg = {}
if os.path.exists(path):
    try:
        cfg = json.load(open(path))
    except Exception:
        cfg = {}
cfg.update({"repo": repo, "python": py})
cfg.setdefault("listening", True)
json.dump(cfg, open(path, "w"), indent=2, sort_keys=True)
EOF

echo "▶ Installing login agent $AGENT_PLIST"
mkdir -p "$(dirname "$AGENT_PLIST")"
cat > "$AGENT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$APP/Contents/MacOS/ALFRED</string><string>--daemon</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <key>StandardOutPath</key><string>/dev/null</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/ALFRED-daemon.log</string>
</dict>
</plist>
EOF
launchctl bootstrap "$DOMAIN" "$AGENT_PLIST"

echo
echo "✅ ALFRED is installed and listening for “Hey Alfred”."
echo "   • macOS will ask ALFRED for Microphone and Speech Recognition — allow both."
echo "   • Open ALFRED from Spotlight/Launchpad to show the full window."
echo "   • Logs: ~/Library/Logs/ALFRED-daemon.log (listener), ~/Library/Logs/ALFRED.log (agent)"
echo "   • Control: $REPO/mac/alfredctl status | say \"what's the time\" | pause | resume"
