#!/data/data/com.termux/files/usr/bin/bash
# install.sh — installs termux-sms as a standalone package.
#
# Standalone means: no openclaw dependency at all. Any CLI (openclaw's
# termux-sms-channel plugin, pi-agent, a plain cron job, you by hand) can
# use these bins and the one shared poller. Multiple consumers subscribe
# via ~/.config/termux-sms/handlers.d/ instead of each polling the SIM
# independently -- see bin/termux-sms-poll's own docstring for why that
# matters.
#
# What this does:
#   1. Symlinks bin/* into ~/.local/bin/ (or wherever USER_BIN resolves).
#   2. Writes and enables termux-sms-poll's own sv service (via
#      svbase-health, if present on this device -- falls back to a plain
#      runit service definition otherwise, see below).
#   3. Does NOT write a config file for you -- copy config.example to
#      ~/.config/termux-sms/config and fill in your real number.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
HOME="${HOME:-/data/data/com.termux/files/home}"
export SVDIR="${SVDIR:-$PREFIX/var/service}"

CONFIG_DIR="$HOME/.config/termux-sms"   # user-edited: config, handlers.d
DATA_DIR="$HOME/.termux-sms"            # package-generated: state, messages, media
mkdir -p "$CONFIG_DIR/handlers.d" "$DATA_DIR"

# 1. Symlink bins.
USER_BIN="$HOME/.local/bin"
mkdir -p "$USER_BIN"
for f in "$SCRIPT_DIR"/bin/*; do
    name="$(basename "$f")"
    chmod +x "$f"
    ln -sf "$f" "$USER_BIN/$name"
    echo "[termux-sms] linked $name -> $USER_BIN/$name"
done

if ! echo "$PATH" | tr ':' '\n' | grep -qx "$USER_BIN"; then
    echo "[termux-sms] WARN: $USER_BIN is not on PATH in this shell"
fi

# 2. Write the poller's sv service. Prefer svbase-health's safe-write +
#    registration if it's installed on this device; otherwise fall back
#    to a plain, unprotected write (same risk tclaw's own run scripts had
#    before svbase-health existed -- acceptable degradation, not silent).
SVBASE_LIB=""
if [[ -f "$HOME/.svbase/svbase.sh" ]]; then
    SVBASE_LIB="$HOME/.svbase/svbase.sh"
fi

POLL_INTERVAL_SEC="${TERMUX_SMS_POLL_INTERVAL_SEC:-10}"
RUN_SCRIPT_CONTENT="#!/data/data/com.termux/files/usr/bin/bash
export HOME=\"$HOME\"
while true; do
    \"$USER_BIN/termux-sms-poll\" >&2
    sleep $POLL_INTERVAL_SEC
done
"

if [[ -n "$SVBASE_LIB" ]]; then
    # shellcheck disable=SC1090
    source "$SVBASE_LIB"
    svbase_init_log
    echo -n "$RUN_SCRIPT_CONTENT" | svbase_write_run_script "$SVDIR/termux-sms-poll/run"
else
    echo "[termux-sms] WARN: svbase-health not found -- writing run script directly, no overwrite protection"
    mkdir -p "$SVDIR/termux-sms-poll"
    echo -n "$RUN_SCRIPT_CONTENT" > "$SVDIR/termux-sms-poll/run"
    chmod +x "$SVDIR/termux-sms-poll/run"
fi

for _ in 1 2 3 4 5 6 7 8 9 10; do
    [[ -e "$SVDIR/termux-sms-poll/supervise/ok" ]] && break
    sleep 1
done

if command -v sv-enable >/dev/null 2>&1; then
    sv-enable termux-sms-poll
else
    sv up termux-sms-poll
fi

sleep 2
STATUS="$(sv status termux-sms-poll 2>&1 || true)"
echo "[termux-sms] termux-sms-poll: $STATUS"

if [[ -n "$SVBASE_LIB" ]]; then
    # No enabled_if here on purpose -- receiving (sms-receive/mms-receive)
    # doesn't need FROM_NUMBER configured at all, only sending does. The
    # poller is useful with zero config beyond this install.
    svbase_register "termux-sms-poll" "$USER_BIN/termux-sms-poll (looped)" \
        "always" "" "" "termux-sms" "5"
    echo "[termux-sms] registered with svbase-health"
fi

if [[ ! -f "$CONFIG_DIR/config" ]]; then
    echo "[termux-sms] No config yet -- copy config.example to $CONFIG_DIR/config and set FROM_NUMBER."
    echo "[termux-sms] The poller will keep running but every send will fail until that's set."
fi

echo "[termux-sms] install complete."
