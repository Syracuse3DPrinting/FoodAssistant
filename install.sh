#!/usr/bin/env bash
# FoodAssistant on-device installer (Phase 1 — minimal bootstrap)
# ===============================================================
# Run this ON the device (a freshly imaged Raspberry Pi, or any Debian/Ubuntu
# box) over SSH.  It completes in under a minute and then hands off to a
# web UI for the rest of the configuration.
#
#   curl -fsSL https://raw.githubusercontent.com/Syracuse3DPrinting/FoodAssistant/main/install.sh | bash
#
# What it does:
#   1. Installs git + avahi-daemon (mDNS) if absent.
#   2. Clones / updates the repo to REPO_DIR.
#   3. Installs and starts the FoodAssistant bootstrap web server on port 80.
#   4. Prints "Open http://<hostname>.local in your browser" and exits.
#
# The web installer (bootstrap_server.py) then walks the user through mode
# selection and runs the full provisioner (scripts/image-build/firstboot.sh)
# with live log streaming.
#
# Non-interactive / CI use:
#   Set NONINTERACTIVE=1 along with the same env vars accepted by firstboot.sh:
#     DEPLOYMENT_MODE, REMOTE_SERVER_URL, ENABLE_KIOSK, ENABLE_STREAMDECK,
#     ENABLE_MEALIE, ENABLE_OLLAMA, DISPLAY_ROTATION
#   When NONINTERACTIVE=1 the bootstrap web server is NOT started; the
#   provisioner is called directly, matching the old behaviour.
#
# Branch override (e.g. for testing):
#   REPO_BRANCH=ANGTEST2 bash <(curl -fsSL .../install.sh)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Syracuse3DPrinting/FoodAssistant.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
REPO_DIR="${REPO_DIR:-/opt/foodassistant-src}"
NONINTERACTIVE="${NONINTERACTIVE:-0}"
BOOTSTRAP_PORT="${BOOTSTRAP_PORT:-8080}"

# ── pretty output ─────────────────────────────────────────────────────────────
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_CYAN=$'\033[1;36m'; C_GREEN=$'\033[1;32m'; C_YELLOW=$'\033[1;33m'
  C_RED=$'\033[1;31m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_CYAN=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_DIM=""; C_OFF=""
fi
say()  { printf '%s==>%s %s\n' "$C_CYAN" "$C_OFF" "$*"; }
ok()   { printf '%s[ok]%s %s\n' "$C_GREEN" "$C_OFF" "$*"; }
warn() { printf '%s[!]%s %s\n' "$C_YELLOW" "$C_OFF" "$*" >&2; }
die()  { printf '%sError:%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; exit 1; }
hr()   { printf '%s----------------------------------------%s\n' "$C_DIM" "$C_OFF"; }

# ── root check ────────────────────────────────────────────────────────────────
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || die "Please run as root or install sudo first."
  SUDO="sudo"
fi

# ── hostname ──────────────────────────────────────────────────────────────────
THIS_HOST="$(hostname 2>/dev/null || echo foodassistant)"

hr
printf '%s  FoodAssistant — Web Installer%s\n' "$C_GREEN" "$C_OFF"
hr
say "This script installs the web installer on this device."
say "It will be done in about 30 seconds."
hr

# ── Step 1: base dependencies ─────────────────────────────────────────────────
say "Installing base dependencies (git, avahi-daemon)…"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq git avahi-daemon
ok "Base dependencies ready"

# ── Step 2: clone / update the repo ──────────────────────────────────────────
say "Fetching FoodAssistant repository to $REPO_DIR…"
if [ -d "$REPO_DIR/.git" ]; then
  $SUDO git -C "$REPO_DIR" fetch --depth 1 origin "$REPO_BRANCH" 2>/dev/null \
    && $SUDO git -C "$REPO_DIR" reset --hard "origin/$REPO_BRANCH" \
    || warn "Could not update existing checkout; using what is on disk."
else
  $SUDO git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR" \
    || die "Could not clone $REPO_URL — check internet access and try again."
fi
ok "Repo ready at $REPO_DIR"

# ── Non-interactive shortcut: skip the web server, run firstboot directly ─────
if [ "$NONINTERACTIVE" = "1" ]; then
  say "NONINTERACTIVE mode — running provisioner directly…"
  FIRSTBOOT="$REPO_DIR/scripts/image-build/firstboot.sh"
  [ -f "$FIRSTBOOT" ] || die "Provisioner not found at $FIRSTBOOT"
  $SUDO env \
    DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-}" \
    REMOTE_SERVER_URL="${REMOTE_SERVER_URL:-}" \
    ENABLE_MEALIE="${ENABLE_MEALIE:-false}" \
    ENABLE_OLLAMA="${ENABLE_OLLAMA:-false}" \
    ENABLE_KIOSK="${ENABLE_KIOSK:-auto}" \
    ENABLE_STREAMDECK="${ENABLE_STREAMDECK:-auto}" \
    DISPLAY_ROTATION="${DISPLAY_ROTATION:-0}" \
    REPO_DIR="$REPO_DIR" \
    bash "$FIRSTBOOT"
  hr
  ok "FoodAssistant installed."
  say "Open http://${THIS_HOST}.local:9284/setup to finish configuration."
  hr
  exit 0
fi

# ── Step 3: install the bootstrap web server as a systemd service ─────────────
BOOTSTRAP_SVC="$REPO_DIR/scripts/bootstrap-server/foodassistant-bootstrap.service"
BOOTSTRAP_PY="$REPO_DIR/scripts/bootstrap-server/bootstrap_server.py"

[ -f "$BOOTSTRAP_SVC" ] || die "Bootstrap service file not found: $BOOTSTRAP_SVC"
[ -f "$BOOTSTRAP_PY"  ] || die "Bootstrap server not found: $BOOTSTRAP_PY"

say "Installing bootstrap web server on port $BOOTSTRAP_PORT…"

# Write the unit with the correct REPO_DIR and port substituted in
$SUDO sed \
  -e "s|/opt/foodassistant-src|$REPO_DIR|g" \
  -e "s|BOOTSTRAP_PORT=80|BOOTSTRAP_PORT=$BOOTSTRAP_PORT|g" \
  "$BOOTSTRAP_SVC" \
  | $SUDO tee /etc/systemd/system/foodassistant-bootstrap.service >/dev/null

$SUDO systemctl daemon-reload
$SUDO systemctl enable --now foodassistant-bootstrap.service \
  || die "Failed to start the bootstrap web server — check 'journalctl -u foodassistant-bootstrap.service'"

ok "Bootstrap web server is running on port $BOOTSTRAP_PORT"

# ── Done ───────────────────────────────────────────────────────────────────────
hr
printf '%s  Open this URL in your browser on any device on the same network:%s\n' "$C_GREEN" "$C_OFF"
printf '\n'
if [ "$BOOTSTRAP_PORT" = "80" ]; then
  printf '    %shttp://%s.local%s\n' "$C_CYAN" "$THIS_HOST" "$C_OFF"
else
  printf '    %shttp://%s.local:%s%s\n' "$C_CYAN" "$THIS_HOST" "$BOOTSTRAP_PORT" "$C_OFF"
fi
printf '\n'
say "(If .local doesn't resolve, use the device's IP address instead, e.g. http://<ip>:$BOOTSTRAP_PORT)"
hr

