#!/usr/bin/env bash
# Public launcher (WITH admin login). Reads credentials from a .env file next to
# this script, then starts the server. Use this together with a Cloudflare Tunnel
# so it is reachable at your subdomain. See README section "Publish to your domain".
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

if [ ! -f ".env" ]; then
  echo "No .env file found. Copy .env.example to .env and set your admin login first."
  exit 1
fi
# load .env
set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "$ADMIN_USERNAME" ] || [ -z "$ADMIN_PASSWORD" ]; then
  echo "ADMIN_USERNAME and ADMIN_PASSWORD must be set in .env to run publicly."
  exit 1
fi

if [ ! -d ".venv" ]; then
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
if [ ! -f ".venv/.deps_installed" ]; then
  pip install --upgrade pip
  pip install -r requirements.txt
  touch .venv/.deps_installed
fi

export HOST="${HOST:-127.0.0.1}"   # keep on localhost; Cloudflare Tunnel reaches it
export PORT="${PORT:-5005}"
echo ""
echo "  Admin login ENABLED. Serving on http://$HOST:$PORT (expose via Cloudflare Tunnel)."
echo ""
python app.py
