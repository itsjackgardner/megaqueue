## Context

Today's flow: user fills a form (title, year, media_type, links) → worker submits to megabasterd → on completion, FileBot moves files into Plex folders using `--db TheMovieDB`/`--db TheTVDB` + `--q <title>`. FileBot is paid, its auto-detector misclassifies movie-with-extras as TV (the `Birth (2004)` case we just patched), and the form duplicates information that almost always exists in the filename.

`guessit` (https://github.com/guessit-io/guessit) parses scene/p2p filenames into structured metadata with no API calls. On `Birth.2004.Criterion.1080p.BluRay.x265.HEVC.FLAC-SARTRE.mkv` it returns `{title: "Birth", year: 2004, screen_size: "1080p", source: "BluRay"}`. On `Gen.V.S02E06.1080p.10bit.WEBRip.mkv` it returns `{title: "Gen V", season: 2, episode: 6, type: "episode"}`. On bare `Trailer.mkv` it returns `{title: "Trailer", type: "movie"}` — no year, no quality tags, which is the signal we need to tag it as an extra.

Existing megabasterd integration already gives us per-file names within a few poll ticks of submission via the async `/start` queue and the `DownloadFile.name` field populated in `_update_file_from_megabasterd`. That's the hook point for guessit.

## Goals / Non-Goals

**Goals:**

- Submit UX collapses to "paste links" — no title/year/media_type fields required.
- Metadata is resolved as soon as megabasterd reports file names (typically seconds after submit), not at completion time.
- Movies named `<Title> (<Year>).<ext>`, TV episodes named `<Title> - S<NN>E<NN>.<ext>` — both Plex-canonical.
- Movie extras (featurettes/trailers/interviews) are detected automatically and placed in a `Featurettes/` subfolder.
- When confidence is low, the system blocks post-processing in a `needs_review` state and notifies the user instead of guessing.
- The hand-rolled organiser has no paid dependencies and no external CLI beyond `unrar` for rar archives.

**Non-Goals:**

- No TMDB/TVDB API lookup. Filename-derived title is good enough; if the user wants a "canonical" title (e.g. "Gen V" → "Gen V" already, no remapping needed) they can override via the review form. Plex itself does authoritative metadata matching against the folder name.
- No per-episode title lookup (e.g. "S01E01 - Pilot.mkv"). Plex resolves episode titles on its side.
- No automatic re-run of organiser on already-organised downloads.
- No backfill of `metadata_confidence` on existing rows in the DB. New column defaults to `high` for legacy rows so they don't surprise the user with a review request.
- No keeping FileBot around as a fallback. Clean break.

## Decisions

### 1. When guessit runs

In `_update_file_from_megabasterd`, after `df.name` is set from megabasterd, call `metadata.refresh(df.download)` to re-aggregate. This means guessit runs on every poll tick where a name is updated — cheap (microseconds per filename), idempotent, and accumulates as folder children land one by one.

Rejected: running guessit once at completion. Defeats the "UI fills in as it resolves" goal.

Rejected: running guessit at submit time on URLs. Mega URLs carry no filename information.

### 2. Aggregation strategy

`metadata.refresh(download)` reads every `DownloadFile` with a populated `name`, runs guessit on each, and aggregates:

- **Type vote**: count guessit `type` values across files. If >50% return `type=episode`, the download is TV. If >50% return `type=movie`, it's a movie. Mixed → low confidence, needs review.
- **TV title**: most common `title` field across episode-typed files. Season number = mode of `season` values (in a season pack, all files agree).
- **Movie main feature**: the file whose guessit result includes both `year` and at least one of `screen_size`/`source`/`video_codec`. Tiebreak by largest `total_bytes`. All other movie-typed files in the same Download become `is_extra=True`.
- **Confidence**: `high` if (TV: ≥1 file has S/E and title matches across files) OR (movie: a main feature was selected with a year). `low` otherwise.

### 3. New `needs_review` status

Inserted between `downloading` and `processing`. The worker's `_derive_download_status` returns `needs_review` instead of `processing` when all files finished but `metadata_confidence == "low"`. The detail view exposes a form to set/correct `title`, `year`, `media_type` on the Download, and toggle `is_extra` per file. Submitting the form sets `metadata_source="user"`, `metadata_confidence="high"`, status `processing`, which the worker picks up on the next tick.

Rejected: blocking submission until guessit can resolve (would couple submit to the megabasterd resolve delay, breaks the async submit flow we just landed).

Rejected: a `paused` status that the user manually resumes — `needs_review` carries the *reason* in the name, which is better UX.

### 4. Hand-rolled organiser

`megaqueue/organiser.py`, modelled on the pre-FileBot version at commit `469eeca`. Routing:

- **Movie main feature** (`is_extra=False`): `<PLEX_MOVIES_DIR>/<Title> (<Year>)/<Title> (<Year>).<ext>`.
- **Movie extra** (`is_extra=True`): `<PLEX_MOVIES_DIR>/<Title> (<Year>)/Featurettes/<original-name>.<ext>`. The `Featurettes/` folder is the Plex-recognised convention for local extras.
- **TV episode**: `<PLEX_TV_DIR>/<Title>/Season <NN>/<Title> - S<NN>E<NN>.<ext>`. NN zero-padded to 2 digits.

Archive extraction uses `rarfile` (needs `unrar` system binary), `zipfile` (stdlib), `py7zr` (pure Python). Dispatch on extension; multi-part rar handled by `rarfile` natively.

Rejected: `patoolib`. Heavyweight, wraps multiple system binaries, mostly the same surface as our 3 targeted libs.

### 5. Submit form

Single textarea, one mega.nz link per line. Submit creates one Download with `title=NULL`, `year=NULL`, `media_type=NULL`, `metadata_confidence="low"`, `metadata_source=NULL`, plus one DownloadFile per link. Pre-existing CSRF, link validation, and worker hand-off are unchanged.

Open question: should multiple links in one submission group as one Download (current behaviour) or split into one Download per link? Keeping current behaviour (one Download per submission) — that matches the mental model of "this is my Gen V S02 download" even if 8 mega URLs.

### 6. Dashboard rendering before metadata resolves

The dashboard polls every 5s. Between submit and the first megabasterd name population, `Download.title` is NULL. Render as "Resolving…" with the link's mega ID as a placeholder. Once any DownloadFile gets a name, guessit runs and `title` populates; the next 5s tick swaps the placeholder for the real title.

### 7. ntfy on needs_review

New `notify_needs_review(download)` in `notifications.py` sends a push with title "Review needed: \<placeholder or partial title\>" and body listing the gaps ("no year detected", "mixed types — please confirm"). Same ntfy topic as the other notifications.

### 8. Restructure done in the same change, ahead of behavioural work

Three internal restructures land *first* on the branch, so the guessit/needs_review work lands on a cleaner base. Each is mechanically reversible if it doesn't pull its weight, but the post-restructure code is what gets reviewed.

**8a. Split `worker.py` by responsibility.** Current `worker.py` is 446 lines covering polling, URL helpers, megabasterd matching, folder expansion, file updates, status derivation, source-path resolution, post-processing, and submission. Adding guessit aggregation + needs_review transitions to this file is the wrong direction. The split:

| Module | Responsibility | Why a separate module |
|---|---|---|
| `mega_urls.py` | `normalize_url`, `extract_folder_id`, `is_folder_url` | Pure functions, no DB, no IO — easy to test exhaustively. Currently `_`-prefixed helpers in `worker.py`. |
| `sync.py` | Match megabasterd entries to `DownloadFile` records, expand folders, update per-file progress, trigger `metadata.refresh`. | The "megabasterd → DB" boundary. Test with a fixture of mb status dicts + a DB session. |
| `lifecycle.py` | Derive Download status, drive `needs_review` ↔ `processing` transitions, call into the organiser and notifications. | The state-machine layer. Easy to assert "given these file states + confidence, the Download status is X". |
| `worker.py` | The 5-second poll loop and thread bootstrap. Calls `sync` then `lifecycle`. | Stays tiny (~50 lines). Threading is the only thing that's hard to test, and now it's isolated. |

Rejected: leave it all in one file. Adding ~150 lines of guessit + lifecycle changes would push it past 600 lines with no organising principle.

Rejected: split further (e.g. `submission.py`, `integrity_sweep.py`). Diminishing returns for ~30-line concerns.

**8b. `enum.StrEnum` for statuses.** Today `Download.status` and `DownloadFile.status` are `Enum(...)` columns at the SQLAlchemy level with string literals (`"queued"`, `"downloading"`, …) sprinkled through `worker.py`, `app.py`, and tests. With seven Download statuses now and two new enums (`MetadataConfidence`, `MetadataSource`), typos in comparisons become silent bugs. Introduce in `megaqueue/enums.py`:

```python
class DownloadStatus(StrEnum):
    QUEUED = "queued"; DOWNLOADING = "downloading"; NEEDS_REVIEW = "needs_review"
    PROCESSING = "processing"; COMPLETE = "complete"; FAILED = "failed"; CANCELLED = "cancelled"
```

`StrEnum` keeps the string-comparison ergonomics (`download.status == DownloadStatus.QUEUED` still works against the DB-stored string). SQLAlchemy column type becomes `Enum(DownloadStatus, ...)`. Replace string literals incrementally; ruff/pyright would catch any missed sites.

Rejected: plain `Enum` (breaks string comparison against existing serialised data without an adapter). Rejected: keep strings (the whole point of this restructure is to eliminate magic-string drift).

**8c. `migrations.py` with named, ordered migrations.** Current `init_db()` has one inline `try/except` for the `parent_id` column. With three more columns (`metadata_confidence`, `metadata_source`, `is_extra`) and the `needs_review` enum value, the pattern doesn't scale. New module:

```python
# megaqueue/migrations.py
MIGRATIONS = [
    ("add_parent_id_column", _add_parent_id),
    ("add_metadata_columns", _add_metadata_columns),
    ("add_is_extra_column", _add_is_extra),
    ("widen_status_enum", _widen_status_enum),
]

def run_all(conn):
    for name, fn in MIGRATIONS:
        try: fn(conn); log.info("Migration %s applied", name)
        except Exception as e: log.debug("Migration %s skipped: %s", name, e)
```

Each migration function is one `ALTER TABLE` (or the SQLite table-rebuild pattern for enum widening). The try/except remains because SQLite gives no native "is this migration applied" check, but the names are now visible and the order is explicit. Alembic was considered and rejected — overkill for a single-user app on SQLite with <10 migrations expected lifetime.

Rejected: a `schema_migrations` tracking table. Worth doing if we ever hit a migration that can't be made idempotent, but every migration we have today is idempotent under `IF NOT EXISTS`-style guards.

## Risks / Trade-offs

- **guessit false positives on the title field.** It pulls `title="Trailer"` from `Trailer.mkv`. Mitigation: the extras heuristic discards titles that lack year/quality so the main feature wins.
- **Movies released without a year in the filename.** A small minority — guessit returns no year, the main-feature heuristic falls back to largest file. If there are extras and the largest file *is* the main feature, this works. If there's only one file, we use it but flag `low` confidence → review.
- **TV with mixed-quality files.** Should still aggregate correctly because the title field is the dominant signal, not quality.
- **`unrar` dependency on the NUC.** Need to verify it's already installed (it should be — megabasterd downloads `.rar` archives that megaqueue currently hands to FileBot for extraction, and the NUC has megabasterd working). If not, document the install step.
- **No metadata for existing in-flight downloads.** Migration sets `metadata_confidence="high"` on existing rows so they bypass review and use whatever title/year/media_type are already set. New submissions go through the new path.
- **One-shot, no rollback.** This change removes FileBot wholesale. Rollback means reverting the submodule pointer. Acceptable risk because the new path has tests and the FileBot path has caused failures.

## Migration Plan

Land in the following order on the `megaqueue` branch; each step keeps the tree green:

1. **Restructure** (Decision 8): extract `mega_urls.py`, `sync.py`, `lifecycle.py`, `enums.py`, `migrations.py`. Mechanical refactor; existing tests should pass with import path updates only.
2. **Schema migration**: add `metadata_confidence`, `metadata_source`, `is_extra`; widen status enum to include `needs_review`. Runs via `migrations.py` on first startup.
3. **Metadata + organiser**: introduce `metadata.py` and replace `filebot_organizer.py` with `organiser.py`.
4. **Lifecycle changes**: wire `needs_review` transition + ntfy push into `lifecycle.py`.
5. **Routes + templates**: collapse submit form, add `/resolve`, add resolve form to detail view.
6. **Cleanup**: drop `MEGAQUEUE_FILEBOT_BIN`, the FileBot startup probe, FileBot install steps in `scripts/`.
7. **Bump submodule pointer** in parent repo and deploy to NUC.

Existing failed downloads can be retried after deployment; they'll go through the new path, get fresh metadata from guessit, and proceed.

Rollback: revert the parent-repo submodule pointer. The new columns are additive and don't break the old code path.

## Open Questions

- Should we keep `Download.media_type` as a strict enum (`movie | tv`) or relax to nullable string until guessit resolves it? Leaning nullable enum — set after resolution, not at row creation.
- Should the resolve form require the user to also confirm `media_type` even when guessit was confident enough to set it? Leaning no — only ask for fields that are actually unresolved.
- Multi-language audio / forced subtitles — out of scope; rely on Plex to surface them.
