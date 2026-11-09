#!/bin/bash
set -e

# Export display port for X11
export DISPLAY=:99

# Clean up any stale lock files
rm -f /tmp/.X99-lock
rm -f /tmp/.X11-unix/X99

# Clean up stale Chromium SingletonLock files from persistent profiles.
# These are symlinks referencing old container hostnames that prevent Chromium
# from starting after a container is recreated (new hostname).
echo "Cleaning stale Chromium profile locks..."
for profile_dir in /app/playwright_data/portal_profile /app/playwright_data/profiles/*; do
    rm -f "$profile_dir/SingletonLock" "$profile_dir/SingletonCookie" "$profile_dir/SingletonSocket" 2>/dev/null
done

# Start Virtual Framebuffer with access control disabled
echo "Starting Xvfb on DISPLAY=:99..."
Xvfb :99 -screen 0 1920x1080x24 -ac &

# Wait for the X server to be ready
echo "Waiting for X server to start..."
timeout 10 bash -c 'while ! xdpyinfo -display :99 >/dev/null 2>&1; do sleep 0.5; done' || { echo "Xvfb failed to start!"; exit 1; }

# Start Window Manager (prevents browser from acting like a kiosk and failing to handle popups)
echo "Starting Fluxbox..."
fluxbox &
sleep 1

# Start VNC Server. Bound to localhost: the only way in is the authenticated websockify below.
echo "Starting x11vnc..."
x11vnc -display :99 -forever -nopw -bg -quiet -xkb -localhost

# Start the websockify bridge for noVNC, gated by HTTP auth with the MCP API key (static files and WebSocket).
# Without a key the portal VNC stays off rather than open.
# "Empty" means the same as in vnc_auth.py and the app: nothing but whitespace.
if [ -n "$(tr -d '[:space:]' < /run/secrets/PLAYWRIGHT_MCP_API_KEY 2>/dev/null)" ]; then
    echo "Starting websockify for noVNC on port 6080 (authenticated)..."
    PYTHONPATH=/app websockify --web /usr/share/novnc --web-auth \
        --auth-plugin playwright_mcp.vnc_auth.ApiKeyBasicAuth \
        --auth-source /run/secrets/PLAYWRIGHT_MCP_API_KEY 6080 localhost:5900 &
    WEBSOCKIFY_PID=$!
    # A websockify that dies at startup (bad plugin path, no --web-auth support) must be visible in the logs.
    up=""
    for _ in $(seq 1 20); do
        if (exec 3<>/dev/tcp/127.0.0.1/6080) 2>/dev/null; then up=1; break; fi
        kill -0 "$WEBSOCKIFY_PID" 2>/dev/null || break
        sleep 0.5
    done
    [ -n "$up" ] || echo "ERROR: websockify for the portal VNC did not start; the portal is unavailable"
else
    echo "portal VNC disabled: PLAYWRIGHT_MCP_API_KEY not set"
fi

# Start the MCP Python Server
echo "Starting Playwright MCP Server..."
exec python3 -m playwright_mcp.server