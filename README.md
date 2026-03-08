# MegaQueue

Self-hosted web app for queueing mega.nz downloads via megabasterd, organizing files into Plex library folders, and getting push notifications when they're ready.

## Prerequisites

- **Python 3.10+** on the Windows NUC
- **Megabasterd fork** (with REST API) — see below
- **Cloudflare account** with a domain for remote access
- **ntfy.sh app** on your phone (subscribe to your chosen topic)

## Setup

### 1. Install megabasterd fork

Clone and build the megabasterd fork that includes the REST API:

```bash
git clone https://github.com/<your-username>/megabasterd.git
cd megabasterd
mvn package
```

Run the JAR, then in megabasterd's settings:
- **Downloads tab**: Enable "Remote API", set port to `8217`
- **Downloads tab**: Configure smart proxy with your proxy list
- **Advanced tab**: Set your MEGA API key

### 2. Install MegaQueue

```bash
cd megaqueue
pip install -r requirements.txt
```

### 3. Generate a password hash

```bash
python hashpw.py
```

Copy the output hash.

### 4. Configure

Set environment variables (or create a `.env` file and source it):

```bash
export MEGAQUEUE_SECRET_KEY="<random-string-at-least-32-chars>"
export MEGAQUEUE_PASSWORD_HASH="<bcrypt-hash-from-step-3>"
export MEGAQUEUE_PLEX_MOVIES_DIR="D:/Plex/Movies"
export MEGAQUEUE_PLEX_TV_DIR="D:/Plex/TV Shows"
export MEGAQUEUE_NTFY_TOPIC="megaqueue-<random-suffix>"
```

Optional (defaults shown):

```bash
export MEGAQUEUE_MEGABASTERD_API_URL="http://localhost:8217"
export MEGAQUEUE_MEGABASTERD_POLL_INTERVAL="5"
export MEGAQUEUE_NTFY_SERVER="https://ntfy.sh"
export MEGAQUEUE_HOST="0.0.0.0"
export MEGAQUEUE_PORT="5000"
```

### 5. Run

```bash
python app.py
```

MegaQueue starts on `http://0.0.0.0:5000` via Waitress.

### 6. Set up Cloudflare Tunnel (for remote access)

1. Register a domain and point its DNS to Cloudflare
2. Install `cloudflared` on the NUC: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
3. Authenticate: `cloudflared tunnel login`
4. Create a tunnel: `cloudflared tunnel create megaqueue`
5. Configure the tunnel to point to `http://localhost:5000`
6. Add a DNS record: `cloudflared tunnel route dns megaqueue megaqueue.yourdomain.com`
7. Install as a Windows service: `cloudflared service install`

Now access MegaQueue at `https://megaqueue.yourdomain.com` from anywhere.

### 7. (Optional) Set up Cloudflare Access

For an extra authentication layer in front of MegaQueue:

1. Go to Cloudflare Zero Trust dashboard
2. Create an Access application for `megaqueue.yourdomain.com`
3. Add an email-based policy (your email gets an OTP to log in)

## Usage

1. Open MegaQueue on your phone (LAN IP or Cloudflare domain)
2. Log in with your password
3. Tap "+ Add", enter the title, year, type, and paste mega.nz links
4. MegaQueue submits to megabasterd, tracks progress, organizes into Plex folders
5. Get a push notification on your phone when it's ready

## Architecture

```
Phone browser
    │
    ├── LAN: http://192.168.x.x:5000
    └── Remote: https://megaqueue.yourdomain.com
              │
              └── Cloudflare Tunnel (cloudflared)
                        │
    ┌───────────────────┘
    │
    ▼
MegaQueue (Flask/Waitress)
    │
    ├── SQLite DB (download queue)
    ├── Worker thread
    │     │
    │     ├── POST /start → megabasterd API
    │     ├── GET /status  → poll progress
    │     └── POST /stop   → cancel
    │
    ├── File organizer (Plex folder structure)
    └── ntfy.sh notifications
              │
              ▼
        megabasterd (Java, smart proxy)
              │
              ▼
          mega.nz
```
