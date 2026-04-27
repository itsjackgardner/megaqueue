# MegaQueue

Self-hosted web app for queueing mega.nz downloads via megabasterd, organizing files into Plex library folders, and getting push notifications when they're ready.

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
MegaQueue (Flask/Waitress)
    |
    |-- SQLite DB (download queue)
    |-- Worker thread
    |     |
    |     |-- POST /start -> megabasterd API
    |     |-- GET /status  -> poll progress
    |     +-- POST /stop   -> cancel
    |
    |-- File organizer (Plex folder structure)
    +-- ntfy.sh notifications
              |
              v
        megabasterd (Java, smart proxy)
              |
              v
          mega.nz
```

## Prerequisites

Install on the Windows NUC (all available via Chocolatey: `choco install git python maven adoptopenjdk 7zip nssm -y`):

- **Git for Windows**
- **Python 3.10+** (check "Add to PATH" during install)
- **Java 21+** (needed to build and run megabasterd)
- **Maven** (needed to build megabasterd)
- **7-Zip** (needed by patool for extracting archives)
- **NSSM** (for running as Windows services)
- **ntfy app** on your phone — https://ntfy.sh

## Setup

### 1. Clone the project

```powershell
git clone --recurse-submodules git@github.com:itsjackgardner/megaqueue-dev.git
cd megaqueue-dev
```

If you already cloned without `--recurse-submodules`:

```powershell
git submodule update --init
```

### 2. Build megabasterd

```powershell
cd megabasterd
mvn package -DskipTests
```

The executable JAR will be at `target/MegaBasterd-8.23-jar-with-dependencies.jar`.

### 3. Configure megabasterd

Run it once to set up the GUI settings:

```powershell
java -jar target/MegaBasterd-8.23-jar-with-dependencies.jar
```

In the megabasterd settings:

1. **Advanced tab** — Enable "Remote API", set port to `8127`
2. **Downloads tab** — Configure smart proxy with your proxy list
3. **Advanced tab** — Set your MEGA API key if you have one

Leave megabasterd running — MegaQueue talks to it via the REST API on port 8127.

### 4. Set up MegaQueue

```powershell
cd ..\megaqueue
pip install -r requirements.txt
```

#### Create a `.env` file

Create `megaqueue/.env` with your configuration:

```
MEGAQUEUE_SECRET_KEY=change-me-to-a-random-string-at-least-32-chars
MEGAQUEUE_PLEX_MOVIES_DIR=D:/Plex/Movies
MEGAQUEUE_PLEX_TV_DIR=D:/Plex/TV Shows
MEGAQUEUE_NTFY_TOPIC=megaqueue-change-me-to-something-random
```

Optional (defaults shown):

```
MEGAQUEUE_MEGABASTERD_API_URL=http://localhost:8127
MEGAQUEUE_MEGABASTERD_POLL_INTERVAL=5
MEGAQUEUE_NTFY_SERVER=https://ntfy.sh
MEGAQUEUE_HOST=0.0.0.0
MEGAQUEUE_PORT=5000
```

Load environment variables before running:

```powershell
foreach ($line in Get-Content .env) {
    if ($line -match "^([^#=]+)=(.*)$") {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}
```

### 5. Run MegaQueue

Make sure megabasterd is already running, then:

```powershell
python run.py
```

MegaQueue starts on `http://0.0.0.0:5000`. Open it from your phone at `http://<NUC-local-IP>:5000`.

### 6. Run as Windows services (optional)

Use NSSM to run both as Windows services that start automatically and restart on crash.

#### Install megabasterd as a service

```powershell
nssm install megabasterd java -jar "C:\path\to\megaqueue-dev\megabasterd\target\MegaBasterd-8.23-jar-with-dependencies.jar"
nssm set megabasterd AppDirectory "C:\path\to\megaqueue-dev\megabasterd"
nssm set megabasterd DisplayName "MegaBasterd"
nssm set megabasterd Start SERVICE_AUTO_START
```

#### Install MegaQueue as a service

```powershell
nssm install megaqueue python run.py
nssm set megaqueue AppDirectory "C:\path\to\megaqueue-dev\megaqueue"
nssm set megaqueue DisplayName "MegaQueue"
nssm set megaqueue DependOnService megabasterd
nssm set megaqueue Start SERVICE_AUTO_START
```

Set environment variables from your `.env` file:

```powershell
$envVars = (Get-Content megaqueue\.env | Where-Object { $_ -match "^[^#=]+=.+" }) -join " "
nssm set megaqueue AppEnvironmentExtra $envVars
```

#### Manage the services

```powershell
nssm start megaqueue         # start
nssm status megaqueue        # check status
nssm restart megaqueue       # restart
nssm stop megaqueue          # stop
nssm edit megaqueue          # open GUI to edit settings
nssm remove megaqueue        # uninstall the service
```

You can also manage them from the Windows Services panel (`services.msc`).

### 7. Remote access via Cloudflare Tunnel + Zero Trust

#### Create the tunnel

1. Sign up for Cloudflare and add a domain
2. Download cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
3. Run the setup:

```powershell
cloudflared tunnel login
cloudflared tunnel create megaqueue
cloudflared tunnel route dns megaqueue queue.yourdomain.com
```

4. Create `C:\Users\<you>\.cloudflared\config.yml`:

```yaml
tunnel: <tunnel-id>
credentials-file: C:\Users\<you>\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: queue.yourdomain.com
    service: http://localhost:5000
  - service: http_status:404
```

5. Install as a Windows service:

```powershell
cloudflared service install
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
   - Optionally also require specific emails for extra control
4. **Install WARP on your devices**:
   - iPhone: Install "1.1.1.1: Faster Internet" from the App Store
   - Open the app, go to Settings > Account > Login to Cloudflare Zero Trust
   - Enter your team name and authenticate with your email
5. Visit `https://queue.yourdomain.com` — no login page, just works

#### Granting access to a friend

1. In Zero Trust dashboard, go to **Settings > WARP Client > Device enrollment**
2. Add their email to the enrollment policy (e.g., **Emails** > `friend@email.com`)
3. Have them install the WARP app and enroll with their email
4. They can now access `https://queue.yourdomain.com` seamlessly

To revoke access, remove their email from the enrollment policy. All free-tier (up to 50 users).

## Usage

1. Open MegaQueue on your phone (LAN IP or Cloudflare domain)
2. Tap "+ Add", enter the title, year, type, and paste mega.nz links
4. MegaQueue submits to megabasterd, tracks progress, organizes into Plex folders
5. Get a push notification on your phone when it's ready
