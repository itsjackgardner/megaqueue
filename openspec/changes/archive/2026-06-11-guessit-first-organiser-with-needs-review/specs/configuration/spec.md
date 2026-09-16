## REMOVED Requirements

### Requirement: FileBot binary path is configurable
**Reason**: FileBot is no longer used; replaced by a hand-rolled Python organiser driven by `guessit`.
**Migration**: Remove `MEGAQUEUE_FILEBOT_BIN` from any `.env` files and deployment scripts. No replacement variable is needed — the new organiser has no external CLI configuration.

### Requirement: Startup validates FileBot binary is accessible
**Reason**: FileBot is no longer invoked at runtime, so the startup probe has nothing to validate.
**Migration**: The startup log line about FileBot availability will be removed; if `.rar` extraction needs `unrar` on PATH, the organiser SHALL surface a clear error at the time it first encounters a rar archive, not at startup.
