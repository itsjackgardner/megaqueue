## Context

MegaQueue handles complete TV seasons and movies well, but has no support for currently airing shows where a mega.nz folder link accumulates new episodes over time. Today, re-submitting the same folder link creates a duplicate Download entry, re-downloads all files, and the organiser may clash with already-placed files. The user's current workaround is keeping a text note with the link and manually selecting new episodes in megabasterd's native UI — MegaQueue should absorb this workflow.

The system already has folder expansion (sync.py creates child DownloadFile records when megabasterd splits a folder), three-tier URL matching, and a post-processing pipeline that routes TV episodes to Plex folders by season/episode number. The new feature builds on these foundations.

## Goals / Non-Goals

**Goals:**
- Allow re-checking a completed folder download for new files, downloading only what's new
- Keep ongoing shows easily accessible via a ongoing section on the dashboard
- Prevent accidental duplicate downloads of the same folder
- Handle re-organised downloads gracefully (skip files already in Plex)

**Non-Goals:**
- Automatic periodic re-checking (polling folders on a schedule) — manual trigger only
- Notifications when new episodes are detected — the user initiates the check
- Multi-season tracking across different folder links — each link is its own Download
- Megabasterd UI integration for selective file picking — we download all new files automatically

## Decisions

### 1. Megabasterd gets a `/folder-list` endpoint

**Decision**: Add a new `GET /folder-list?url=<encoded-folder-url>` endpoint to megabasterd that returns the folder's file listing without starting a download.

**Rationale**: megabasterd already has the mega.nz SDK wired up and handles authentication/decryption. Adding a listing endpoint keeps all mega.nz protocol interaction in one place. The alternative — having megaqueue call the mega.nz API directly — would duplicate crypto logic and add a new Python dependency (mega.py or similar).

**Response format**:
```json
[
  {"name": "Show.S01E01.mkv", "url": "https://mega.nz/file/xxx#yyy", "size": 1234567890},
  {"name": "Show.S01E02.mkv", "url": "https://mega.nz/file/xxx#zzz", "size": 1234567890}
]
```

### 2. Diff by filename, not URL

**Decision**: When comparing folder contents against existing DownloadFile records, match by `name` (filename), not by URL.

**Rationale**: megabasterd may generate different per-file URLs each time it lists a folder (the URLs contain session-specific components). Filenames are stable identifiers for episode files within a folder. This is consistent with how the organiser already identifies episodes (guessit parses the filename).

### 3. Re-check reuses the existing Download entry

**Decision**: New files from a re-check are added as new child DownloadFile records under the existing folder parent, and the Download transitions back to `downloading`.

**Alternatives considered**:
- **New Download per re-check**: Simpler but fragments the history. The user would have multiple entries for the same show/season, making the dashboard noisy.
- **Separate "subscription" model**: Over-engineered for the use case. The user wants a simple "check again" button, not a subscription system.

**Rationale**: Reusing the entry keeps all episodes for a season grouped together, matches the user's mental model ("this is one season"), and the existing status derivation already handles mixed file states (some finished, some downloading).

### 4. Organiser skips already-placed files

**Decision**: When computing a destination path, if the file already exists on disk, skip the move and just set `file_path` on the DownloadFile record.

**Rationale**: After a re-check, post-processing runs for the entire Download (all leaf files). Files from previous runs are already in their Plex destination. The organiser must not fail or overwrite them. Checking `file_path is not None` on the DownloadFile is the primary guard (skip files that were already organised), with the destination-exists check as a safety net.

### 5. Ongoing status is manual, not automatic

**Decision**: The user manually marks downloads as ongoing or finished. There's no auto-marking on re-check or auto-clearing on season completion.

**Rationale**: The user explicitly requested manual control. Auto-clearing would require knowing when a season is "done", which MegaQueue can't determine (it doesn't know how many episodes a season has).

### 6. Submission of only new files to megabasterd

**Decision**: When re-check finds new files, only those files' URLs are passed to `client.start()`. Already-finished files are not re-submitted.

**Rationale**: Re-submitting finished files to megabasterd would cause it to either re-download them or error. The sync layer already handles selective submission — this extends it to the re-check path.

## Risks / Trade-offs

**[Megabasterd change required]** → The `/folder-list` endpoint must be implemented in the Java codebase. This is the only cross-repo dependency. The endpoint is simple (list folder, return JSON), but it needs to be done before the megaqueue side can be fully tested end-to-end. The megaqueue client can be built and tested with mocks in the meantime.

**[Filename collisions across different shows]** → If two different folder downloads happen to have files with the same name, the filename-based diff could theoretically produce false matches. This is extremely unlikely for episode files (which include show name and S/E numbers) and is mitigated by the diff being scoped to children of a single parent DownloadFile, not across all downloads.

**[Organiser runs on all leaf files]** → Post-processing processes all leaf files, not just new ones. The `file_path is not None` skip and destination-exists safety net handle this, but it means the organiser does O(all files) work on each re-check completion instead of O(new files). For TV seasons with ~10-20 episodes, this is negligible.

**[Race condition: re-check during worker tick]** → If the user triggers a re-check at the exact moment the worker is polling, there could be a brief inconsistency. The re-check route should acquire a session-scoped lock or use the existing DB session to ensure atomicity. In practice, the 5-second poll interval makes collisions rare, and SQLite's write serialization prevents corruption.
