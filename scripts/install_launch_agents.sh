#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$ROOT/data/logs"
mkdir -p "$PLIST_DIR" "$LOG_DIR"

if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi

if ! "$ROOT/.venv/bin/python" -c "import fastapi, httpx" >/dev/null 2>&1; then
  "$ROOT/.venv/bin/pip" install -r "$ROOT/backend/requirements.txt"
fi

if [ ! -d "$ROOT/node_modules" ]; then
  (cd "$ROOT" && npm install)
fi

cat > "$PLIST_DIR/com.justalim.obsidianai.backend.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.justalim.obsidianai.backend</string>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT/.venv/bin/uvicorn</string>
    <string>backend.main:app</string>
    <string>--host</string><string>0.0.0.0</string>
    <string>--port</string><string>8765</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG_DIR/launch-backend.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/launch-backend.err.log</string>
</dict>
</plist>
PLIST

cat > "$PLIST_DIR/com.justalim.obsidianai.frontend.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.justalim.obsidianai.frontend</string>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>npm</string>
    <string>run</string>
    <string>dev</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG_DIR/launch-frontend.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/launch-frontend.err.log</string>
</dict>
</plist>
PLIST

cat > "$PLIST_DIR/com.justalim.obsidianai.bridge.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.justalim.obsidianai.bridge</string>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT/.venv/bin/python</string>
    <string>$ROOT/scripts/obsidian_local_agent.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG_DIR/launch-bridge.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/launch-bridge.err.log</string>
</dict>
</plist>
PLIST

for service in backend frontend bridge; do
  launchctl unload "$PLIST_DIR/com.justalim.obsidianai.$service.plist" >/dev/null 2>&1 || true
  launchctl load "$PLIST_DIR/com.justalim.obsidianai.$service.plist"
done

echo "Installed and started ObsidianAI launch agents."
echo "Backend:  http://localhost:8765"
echo "Frontend: http://localhost:5173"
