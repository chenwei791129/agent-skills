#!/bin/bash
# Launch Chrome with remote debugging enabled for chrome-devtools MCP

set -euo pipefail

PORT=9222
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DATA_DIR="$HOME/ChromeDebugProfile"

# Check if port is already listening
if curl -s "http://localhost:$PORT/json/version" > /dev/null 2>&1; then
  echo "Chrome debug mode already running on port $PORT"
  curl -s "http://localhost:$PORT/json/version"
  exit 0
fi

# Quit any running Chrome instances
if pgrep -f "Google Chrome" > /dev/null 2>&1; then
  echo "Quitting existing Chrome instances..."
  pkill -f "Google Chrome" 2>/dev/null || true
  sleep 2
fi

# Launch Chrome with remote debugging
echo "Launching Chrome with remote debugging on port $PORT..."
"$CHROME" --remote-debugging-port="$PORT" --user-data-dir="$DATA_DIR" &>/dev/null &

# Wait and verify
for i in $(seq 1 10); do
  if curl -s "http://localhost:$PORT/json/version" > /dev/null 2>&1; then
    echo "Chrome debug mode ready on port $PORT"
    curl -s "http://localhost:$PORT/json/version"
    exit 0
  fi
  sleep 1
done

echo "ERROR: Chrome failed to start with remote debugging after 10 seconds" >&2
exit 1
