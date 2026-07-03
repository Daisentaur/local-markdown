#!/usr/bin/env bash
# One-command setup for MarkItDown Web (native / non-Docker install).
#
#   ./setup.sh
#
# Installs the OCR system tools, builds the virtualenv, generates a .env with
# fresh secrets, and (optionally) installs the systemd service for 24/7 running
# with your username and path filled in automatically.
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(pwd)"
WHO="$(whoami)"

echo "==> MarkItDown Web setup  (repo: $REPO)"

# 1. OCR system tools ---------------------------------------------------------
if command -v apt-get >/dev/null 2>&1; then
  if ! command -v tesseract >/dev/null 2>&1 || ! command -v ocrmypdf >/dev/null 2>&1; then
    echo "==> Installing OCR tools (ocrmypdf, tesseract-ocr) — needs sudo"
    sudo apt-get update
    sudo apt-get install -y ocrmypdf tesseract-ocr
  else
    echo "==> OCR tools already present"
  fi
else
  echo "==> Non-apt system: install 'ocrmypdf' and 'tesseract' via your package"
  echo "    manager to enable OCR (the app still runs without them)."
fi

# 2. Python virtualenv + deps -------------------------------------------------
echo "==> Building virtualenv and installing Python deps"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# 3. Secrets (.env) -----------------------------------------------------------
if [ ! -f .env ]; then
  echo "==> Generating .env with fresh secrets"
  read -rp "    Admin username [admin]: " ADMIN_IN
  ADMIN_IN="${ADMIN_IN:-admin}"
  PASS="$(.venv/bin/python -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))')"
  SECRET="$(.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')"
  APIKEY="$(.venv/bin/python -c 'import secrets; print("mid_"+secrets.token_urlsafe(32))')"
  cat > .env <<EOF
ADMIN_USERNAME=$ADMIN_IN
ADMIN_PASSWORD=$PASS
SECRET_KEY=$SECRET
API_KEY=$APIKEY
HOST=127.0.0.1
PORT=5005
OCR_ENABLED=1
OCR_LANGUAGE=eng
EOF
  chmod 600 .env
else
  echo "==> .env already exists — leaving it untouched"
fi

# 4. systemd service (optional) ----------------------------------------------
read -rp "==> Install & start the systemd service for 24/7 running? [y/N]: " YN
if [[ "${YN,,}" == y* ]]; then
  echo "==> Writing /etc/systemd/system/markitdown.service (needs sudo)"
  sudo tee /etc/systemd/system/markitdown.service >/dev/null <<EOF
[Unit]
Description=MarkItDown Web (file -> Markdown converter)
After=network-online.target
Wants=network-online.target

[Service]
User=$WHO
WorkingDirectory=$REPO
EnvironmentFile=$REPO/.env
ExecStart=$REPO/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5005 --timeout 300 app:app
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now markitdown
  echo "==> Service installed and running."
fi

# Summary ---------------------------------------------------------------------
echo
echo "==> Done. Your credentials (also in .env):"
grep -E 'ADMIN_USERNAME|ADMIN_PASSWORD|API_KEY' .env | sed 's/^/      /'
echo
echo "    Not using systemd? Start it directly with:"
echo "      .venv/bin/gunicorn --bind 127.0.0.1:5005 app:app"
echo "    Then open http://127.0.0.1:5005"
