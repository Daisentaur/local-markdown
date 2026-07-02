#!/usr/bin/env bash
# Local launcher (no login). Creates a venv, installs deps once, starts the server.
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv) ..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f ".venv/.deps_installed" ]; then
  echo "Installing dependencies (first run only, needs internet this once) ..."
  pip install --upgrade pip
  pip install -r requirements.txt
  touch .venv/.deps_installed
fi

export HOST="${HOST:-127.0.0.1}"
export PORT="${PORT:-5005}"
echo ""
echo "  Open http://$HOST:$PORT in your browser."
echo "  Press Ctrl+C to stop."
echo ""
python app.py
