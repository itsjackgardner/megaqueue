# MegaQueue

Self-hosted web app for queueing mega.nz downloads, organizing files into Plex library folders, and getting push notifications when they're ready. Runs in Docker on Linux.

## Architecture

```
Phone browser
    |
    |-- LAN: http://192.168.x.x:5000
    +-- Remote: https://queue.yourdomain.com
              |
              +-- Cloudflare Tunnel (cloudflared)
                        |
    +-------------------+
    |
    v
MegaQueue (Flask/Waitress, Docker)
    |
    |-- SQLite DB (download queue)
    |-- Worker thread
    |     |
    |     +-- MegaDownloadManager (in-process, async)
    |           |-- megapull (vendored, httpx + asyncio)
    |           +-- ProxyPool (optional)
    |
    |-- File organizer (Plex folder structure)
    +-- ntfy.sh notifications
```

## Prerequisites

- **Docker** and **Docker Compose**
- **ntfy app** on your phone — https://ntfy.sh

## Setup

### 1. Clone the project

```bash
git clone git@github.com:itsjackgardner/megaqueue.git
cd megaqueue
```

### 2. Configure

Copy the example env file and edit it:

```bash
cp .env.example .env
```

Required variables:

```
MEGAQUEUE_SECRET_KEY=change-me-to-a-random-string-at-least-32-chars
MEGAQUEUE_PLEX_MOVIES_DIR=/media/movies
MEGAQUEUE_PLEX_TV_DIR=/media/tv
MEGAQUEUE_DOWNLOAD_DIR=/data/downloads
MEGAQUEUE_NTFY_TOPIC=megaqueue-change-me-to-something-random
```

Optional (defaults shown):

```
MEGAQUEUE_POLL_INTERVAL=5
MEGAQUEUE_GRACE_PERIOD=30
MEGAQUEUE_DOWNLOAD_WORKERS=8
MEGAQUEUE_PROXY_FILE=
MEGAQUEUE_NTFY_SERVER=https://ntfy.sh
MEGAQUEUE_HOST=0.0.0.0
MEGAQUEUE_PORT=5000
```

### 3. Run with Docker

```bash
docker compose up -d
```

MegaQueue starts on `http://0.0.0.0:5000`. Open it from your phone at `http://<host-IP>:5000`.

### 4. Remote access via Cloudflare Tunnel + Zero Trust

#### Create the tunnel

1. Sign up for Cloudflare and add a domain
2. Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
3. Run the setup:

```bash
cloudflared tunnel login
cloudflared tunnel create megaqueue
cloudflared tunnel route dns megaqueue queue.yourdomain.com
```

4. Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <tunnel-id>
credentials-file: ~/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: queue.yourdomain.com
    service: http://localhost:5000
  - service: http_status:404
```

5. Run cloudflared (or install as a systemd service):

```bash
cloudflared tunnel run megaqueue
```

#### Secure with Cloudflare Zero Trust + WARP

Instead of a password, MegaQueue uses Cloudflare Zero Trust to authenticate devices. Only devices running Cloudflare WARP and enrolled in your Zero Trust org can access the app.

1. Go to the **Cloudflare Zero Trust dashboard** (https://one.dash.cloudflare.com)
2. **Settings > WARP Client > Device enrollment**:
   - Add an enrollment policy: **Allow** > **Emails** > your email address
3. **Access > Applications > Add an application**:
   - Type: Self-hosted
   - Application domain: `queue.yourdomain.com`
   - Policy: **Allow** > **Require** > **WARP** (ensures device must be running WARP)
4. **Install WARP on your devices**:
   - iPhone: Install "1.1.1.1: Faster Internet" from the App Store
   - Open the app, go to Settings > Account > Login to Cloudflare Zero Trust
   - Enter your team name and authenticate with your email
5. Visit `https://queue.yourdomain.com` — no login page, just works

#### Granting access to a friend

1. In Zero Trust dashboard, go to **Settings > WARP Client > Device enrollment**
2. Add their email to the enrollment policy
3. Have them install the WARP app and enroll with their email
4. They can now access `https://queue.yourdomain.com` seamlessly

To revoke access, remove their email from the enrollment policy. All free-tier (up to 50 users).

## Usage

1. Open MegaQueue on your phone (LAN IP or Cloudflare domain)
2. Tap "+ Add" and paste mega.nz links
3. MegaQueue downloads via megapull, tracks progress, organizes into Plex folders
4. Get a push notification on your phone when it's ready

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py
```

Run tests:

```bash
pytest
pytest --cov=megaqueue --cov-report=term-missing
```
