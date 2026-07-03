# Deploying MarkItDown Web on your homelab (24/7)

This runs the converter permanently on your server laptop and exposes it at
`https://markdown.example.com` through a Cloudflare Tunnel. Once done, it
survives reboots and crashes, and you don't need a terminal open.

All commands below run **on the server laptop** (Linux). Replace `YOUR_USER`
with your actual Linux username (`whoami` tells you).

---

## 1. Get the code and build it

```bash
cd ~
git clone https://github.com/Daisentaur/local-markdown.git
cd local-markdown

# Build the virtualenv + install deps (needs internet this once)
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# OCR for scanned PDFs & images (system tools, not pip packages)
sudo apt install -y ocrmypdf tesseract-ocr
```

## 2. Create your secrets file

`.env` is **not** in git (it holds passwords), so you create it on the server.
Copy the template and fill it in:

```bash
cp .env.example .env
```

Generate strong values and paste them in:

```bash
# password
python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))"
# SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
# API_KEY (for agents)
python3 -c "import secrets; print('mid_'+secrets.token_urlsafe(32))"
```

Edit `.env`, set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`, `API_KEY`,
then lock it down:

```bash
chmod 600 .env
```

> You can reuse the exact secrets already generated on your dev machine if you
> prefer one set of credentials everywhere — just copy them into this `.env`.

## 3. Run it as a service (auto-start, auto-restart)

Edit `deploy/markitdown.service` and replace both `YOUR_USER` placeholders, then:

```bash
sudo cp deploy/markitdown.service /etc/systemd/system/markitdown.service
sudo systemctl daemon-reload
sudo systemctl enable --now markitdown

# check it came up
systemctl status markitdown --no-pager
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5005/   # expect 302 (redirect to login)
```

The app is now live on `127.0.0.1:5005` and will restart on boot or crash.
Logs: `journalctl -u markitdown -f`.

---

## 4. Cloudflare Tunnel — expose it at your subdomain

The app only listens on localhost. A Cloudflare Tunnel connects it to the
internet with automatic HTTPS, no port-forwarding, no public IP.

### 4a. Install cloudflared on the server

```bash
# Debian/Ubuntu
curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared
```

### 4b. Create the tunnel in the Cloudflare dashboard

Do this in a browser (any machine):

1. **one.dash.cloudflare.com** → Zero Trust. Pick a team name if it's your
   first time (free).
2. **Networks → Tunnels → Create a tunnel** → connector **Cloudflared** → Next.
3. Name it `markdown` → Save.
4. It shows an **install command containing a long token**. Ignore the install
   part (you already installed cloudflared); you just need the token. The clean
   way to register it as a boot service on the server:

   ```bash
   sudo cloudflared service install <THE_LONG_TOKEN>
   ```

   This starts cloudflared as a systemd service tied to your tunnel.
5. Back in the dashboard, wait until the connector shows **Connected** → Next.

### 4c. Route the subdomain to the app

On the tunnel's **Public Hostname** page → **Add a public hostname**:

- **Subdomain:** `markdown`
- **Domain:** `example.com`
- **Path:** (blank)
- **Type:** `HTTP`
- **URL:** `localhost:5005`

Save. Cloudflare **auto-creates the DNS record** for `markdown.example.com`.

### 4d. Done

Open **https://markdown.example.com** — you get the login page. Sign in with
your `.env` credentials and use the UI. Agents use the API key (see README).

---

## Updating later

```bash
cd ~/local-markdown
git pull
.venv/bin/pip install -r requirements.txt   # only if deps changed
sudo systemctl restart markitdown
```

## Optional extra lock: Cloudflare Access

In Zero Trust → **Access → Applications** you can add a rule so only *your*
email can reach the site at all (email one-time-pin or Google login) — a second
gate in front of the app's own login. Note: if you add Access, agents hitting
the API need a **service token** from Access, or you scope the Access policy to
the UI paths only and leave `/api/` to the API key.
