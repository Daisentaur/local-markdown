# MarkItDown Web

A self-hosted web interface around Microsoft's
[markitdown](https://github.com/microsoft/markitdown) library. Drag in files
(PDF, Word, PowerPoint, Excel, HTML, images, **audio (mp3/wav)**, CSV, JSON,
zip, and more), convert them to Markdown, preview the result, and download
individual `.md` files or all of them as a zip.

Files are converted in memory on the machine running this app. Nothing is stored.

```
local-markdown/
├── app.py            # Flask backend (upload, convert, zip, optional login)
├── index.html        # UI: drag/drop, live preview, downloads
├── login.html        # Sign-in page (only used when login is enabled)
├── static/
│   └── marked.min.js # Markdown preview renderer (bundled, works offline)
├── requirements.txt
├── run.sh            # Local launcher — no login
├── run-public.sh     # Public launcher — reads .env, enables admin login
├── deploy/
│   └── markitdown.service  # systemd unit for 24/7 hosting
├── DEPLOY.md         # Full homelab + Cloudflare Tunnel walkthrough
├── .env.example      # Copy to .env for the public launcher
└── .gitignore
```

Running it 24/7 on a server? See **[DEPLOY.md](DEPLOY.md)** for the full
homelab + Cloudflare Tunnel setup.

---

## 1. Run it locally (no login)

Requires **Python 3.10+**.

```bash
cd ~/dev/local-markdown
./run.sh
```

First launch builds a virtualenv and installs dependencies (needs internet
once). Then open **http://127.0.0.1:5005**, drop in files, hit **Convert**, and
download the Markdown. `Ctrl+C` stops it.

**Audio just works** — a static `ffmpeg` is installed via pip (`imageio-ffmpeg`),
so `.mp3` and `.wav` convert with no separate install. If you already have a
system `ffmpeg`, it's used instead. (Note: speech *transcription* inside
markitdown uses an online recognizer, so that specific step needs internet;
audio metadata and format handling work regardless.)

---

## 2. Publish it to your domain: `markdown.example.com`

Your app runs on your own machine, which has no fixed public IP — so you can't
just point a DNS record at it. The clean fix is a **Cloudflare Tunnel**: a small
program (`cloudflared`) on your machine makes an outbound connection to
Cloudflare, and Cloudflare serves your subdomain and forwards traffic down that
tunnel. No port forwarding, no public IP, and you get HTTPS automatically.

> A "subdomain" is just a DNS record like `markdown` under `example.com`.
> The tunnel setup below **creates that record for you** — you don't add it by
> hand.

### Step A — Start the app WITH the admin login

```bash
cd ~/dev/local-markdown
cp .env.example .env
```

Edit `.env` and set your own username, a strong password, and a random
`SECRET_KEY` (the file shows the command to generate one). Then:

```bash
./run-public.sh
```

Leave it running. It listens on `127.0.0.1:5005` and now requires your login.

### Step B — Create the tunnel in the Cloudflare dashboard

Do this in the browser (the dashboard you have open):

1. Go to **one.dash.cloudflare.com** (Cloudflare Zero Trust). It's part of your
   same account — pick a team name if it's your first time (free).
2. Left sidebar → **Networks → Tunnels** → **Create a tunnel**.
3. Choose **Cloudflared** as the connector → **Next**. Name it something like
   `markdown` → **Save tunnel**.
4. Cloudflare shows an **install command with a long token**. Pick your OS,
   copy that command, and run it in a terminal on this machine. It installs and
   starts `cloudflared` and connects it to this tunnel. Leave it running.
   (On macOS this is typically `brew install cloudflared` followed by the
   `cloudflared service install <TOKEN>` line they give you.)
5. Back in the dashboard, once the connector shows **Connected**, click **Next**.

### Step C — Route your subdomain to the local app

On the tunnel's **Public Hostname** (or **Routes → Add route → Published
application**) page:

- **Subdomain:** `markdown`
- **Domain:** `example.com`  (select from the dropdown)
- **Path:** leave blank
- **Type:** `HTTP`
- **URL:** `localhost:5005`

Save. Cloudflare **automatically creates the DNS record** for
`markdown.example.com` pointing at the tunnel.

### Step D — Done

Open **https://markdown.example.com**. You'll get your sign-in page; log in
with the credentials from `.env`, and the converter is live with HTTPS.

**Keep in mind:** the site is only up while **both** `run-public.sh` (the app)
and `cloudflared` (the tunnel) are running on your machine. Close your laptop /
stop either one and the subdomain goes offline until you start them again. If
you want it up 24/7, run it on an always-on machine or a small VPS instead.

### Optional extra lock: Cloudflare Access

Even with the app's own login, you can add a second gate in Zero Trust →
**Access → Applications** that only lets *your* email reach the site at all
(email one-time-pin or Google login). Nice belt-and-suspenders if it's public.

---

## Reference

**Endpoints**

- `POST /api/convert` — accepts one or more files, converts each in memory,
  returns `{results: [{name, source, markdown, error}]}`. A file that can't be
  parsed comes back with an `error` string instead of failing the whole batch.
- `POST /api/zip` — bundles the converted `{name, markdown}` entries into
  `markdown.zip` (duplicate names de-collided as `name_1.md`).
- `GET /login`, `POST /login`, `GET /logout` — only active when login is enabled.

**Agent / script access (API key).** The browser login uses a session cookie,
which a script or AI agent can't carry. Set `API_KEY` in `.env` and have the
agent send it as a header — no login needed:

```bash
curl -H "X-API-Key: $API_KEY" \
     -F "files=@report.pdf" \
     https://markdown.example.com/api/convert
```

`Authorization: Bearer <key>` works too. The `.md` text comes back in
`results[].markdown`. Point any of your projects' agents at this endpoint to get
token-optimized Markdown before they do their real work.

**Login on/off.** Login is enabled automatically when both `ADMIN_USERNAME` and
`ADMIN_PASSWORD` are set (that's what `run-public.sh` does via `.env`). With
them unset (plain `./run.sh`), the app runs open — right for local use.

**Config knobs**

| Variable | Meaning | Default |
|---|---|---|
| `HOST` | Bind address | `127.0.0.1` |
| `PORT` | Port | `5005` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Enable + set the login | unset (login off) |
| `API_KEY` | Lets agents/scripts call `/api/` via `X-API-Key` header | unset (API-key path off) |
| `SECRET_KEY` | Signs login cookies (set a fixed random value in production) | random per start |

Upload size is capped at 100 MB/request (`MAX_CONTENT_LENGTH` in `app.py`).

---

Built on [microsoft/markitdown](https://github.com/microsoft/markitdown) ·
preview via [marked](https://github.com/markedjs/marked) · bundled ffmpeg via
[imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg).
