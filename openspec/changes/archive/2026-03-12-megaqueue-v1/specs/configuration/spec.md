## ADDED Requirements

### Requirement: Application provides centralized configuration
The system SHALL expose configuration via a `config.py` module with the following settings: MEGABASTERD_API_URL (megabasterd REST API base URL, default "http://localhost:8127"), MEGABASTERD_POLL_INTERVAL (seconds between progress polls, default 5), MEGABASTERD_GRACE_PERIOD (seconds before treating a missing download as failed, default 30), PLEX_MOVIES_DIR (Plex movies library path), PLEX_TV_DIR (Plex TV library path), NTFY_TOPIC (ntfy.sh topic name), NTFY_SERVER (ntfy.sh server URL, default "https://ntfy.sh"), SECRET_KEY (Flask session/CSRF secret key), HOST (listen address, default "0.0.0.0"), and PORT (listen port, default 5000).

#### Scenario: Configuration values are accessible throughout the app
- **WHEN** any module imports config
- **THEN** all configuration values are available as module-level constants

### Requirement: Configuration uses sensible defaults
The system SHALL provide default values for MEGABASTERD_API_URL ("http://localhost:8127"), MEGABASTERD_POLL_INTERVAL (5), MEGABASTERD_GRACE_PERIOD (30), and NTFY_SERVER ("https://ntfy.sh"). PLEX_MOVIES_DIR, PLEX_TV_DIR, NTFY_TOPIC, and SECRET_KEY SHALL require explicit configuration.

#### Scenario: App starts with required config set
- **WHEN** all required configuration values are provided
- **THEN** the application starts normally

#### Scenario: App fails on missing required config
- **WHEN** a required configuration value (e.g., SECRET_KEY) is not set
- **THEN** the application logs an error at startup identifying the missing configuration and exits

### Requirement: Configuration supports environment variables
The system SHALL allow all configuration values to be overridden via environment variables with MEGAQUEUE_ prefix (e.g., `MEGAQUEUE_PLEX_MOVIES_DIR`).

#### Scenario: Environment variable overrides default
- **WHEN** `MEGAQUEUE_MEGABASTERD_GRACE_PERIOD` is set to "60"
- **THEN** the grace period is 60 seconds instead of the default 30
