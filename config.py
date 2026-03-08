import os
import sys

def _env(key, default=None):
    """Get config from environment variable (MEGAQUEUE_ prefix) or return default."""
    return os.environ.get(f"MEGAQUEUE_{key}", default)

# Megabasterd REST API
MEGABASTERD_API_URL = _env("MEGABASTERD_API_URL", "http://localhost:8217")
MEGABASTERD_POLL_INTERVAL = int(_env("MEGABASTERD_POLL_INTERVAL", "5"))

# Plex library paths
PLEX_MOVIES_DIR = _env("PLEX_MOVIES_DIR")
PLEX_TV_DIR = _env("PLEX_TV_DIR")

# Notifications
NTFY_TOPIC = _env("NTFY_TOPIC")
NTFY_SERVER = _env("NTFY_SERVER", "https://ntfy.sh")

# Authentication
PASSWORD_HASH = _env("PASSWORD_HASH")
SECRET_KEY = _env("SECRET_KEY")

# Server
HOST = _env("HOST", "0.0.0.0")
PORT = int(_env("PORT", "5000"))

# Database
DATABASE_URL = _env("DATABASE_URL", "sqlite:///megaqueue.db")

_REQUIRED = {
    "PLEX_MOVIES_DIR": PLEX_MOVIES_DIR,
    "PLEX_TV_DIR": PLEX_TV_DIR,
    "NTFY_TOPIC": NTFY_TOPIC,
    "PASSWORD_HASH": PASSWORD_HASH,
    "SECRET_KEY": SECRET_KEY,
}

def validate():
    """Check that all required configuration values are set. Exit if any are missing."""
    missing = [k for k, v in _REQUIRED.items() if not v]
    if missing:
        for key in missing:
            print(f"ERROR: Required config MEGAQUEUE_{key} is not set.", file=sys.stderr)
        sys.exit(1)
