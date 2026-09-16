## REMOVED Requirements

### Requirement: FileBot organizer moves completed downloads to Plex directories
**Reason**: FileBot is paid software whose auto-detection misclassified a real movie download as a TV episode. Replaced by a hand-rolled organiser that uses `guessit` for filename parsing and writes Plex-canonical paths directly.
**Migration**: See `file-organizer` spec for the new movie/extras/TV routing rules.

### Requirement: FileBot organizer extracts archives before renaming
**Reason**: Archive extraction moves to the new organiser using `rarfile`, `zipfile`, and `py7zr`.
**Migration**: See `file-organizer` spec for the new extraction requirement.

### Requirement: FileBot organizer cleans up temp directory after organizing
**Reason**: Same cleanup contract still applies but is now provided by the new organiser.
**Migration**: See the `Organizer cleans up temp directory after organizing` requirement in `file-organizer`.

### Requirement: FileBot organizer returns final destination paths
**Reason**: Same return contract still applies but is now provided by the new organiser.
**Migration**: See the `Organizer returns organized file paths for all placed files` requirement in `file-organizer`.

### Requirement: FileBot organizer reports failure on non-zero exit
**Reason**: There is no longer a subprocess to exit non-zero; the new organiser raises Python exceptions on failure and the worker converts them to `Download.status="failed"` with `error_message` set.
**Migration**: See the `Organizer updates download status on completion` requirement in `file-organizer`.

### Requirement: FileBot binary path is configurable
**Reason**: FileBot is no longer invoked.
**Migration**: See `configuration` spec.

### Requirement: Startup validates FileBot binary is accessible
**Reason**: FileBot is no longer invoked.
**Migration**: See `configuration` spec.
