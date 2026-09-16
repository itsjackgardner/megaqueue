## Context

The current file organizer (`organizer.py`) implements archive extraction (patoolib + 7z fallback), season-regex routing, and source cleanup in ~200 lines of Python. All downloaded files land flat in `MEGABASTERD_DOWNLOAD_DIR` with no subfolders, so post-processing always works on a known list of individual file paths drawn from `DownloadFile` records.

Separately, when a user submits a folder URL, the worker creates one `DownloadFile` record and aggregates all megabasterd per-file entries into that single record. The UI therefore shows one opaque entry for what may be tens of files.

## Goals / Non-Goals

**Goals:**
- Replace `organizer.py` with FileBot subprocess calls for archive extraction, metadata-matched renaming, and Plex-structured moves
- When a folder URL is split into individual files by megabasterd, expose each file as a separate row in the UI (both dashboard and detail view)
- Keep the post-processing integration point in `worker.py` unchanged (a single function call after all files finish)

**Non-Goals:**
- Automatic subtitle downloading via FileBot (can be added later with a config flag)
- Changing how downloads are submitted to megabasterd (folder URLs still submitted as-is)
- Supporting FileBot's online metadata lookup as a rename strategy (we use `--action move` with Plex-format output, not `--db` lookup, to avoid network dependency and misidentification risk)

## Decisions

### 1. FileBot invocation: two-step, file-list mode

FileBot treats extraction and renaming as separate commands. Since all files land flat in `MEGABASTERD_DOWNLOAD_DIR`, we pass the explicit file paths (from `DownloadFile` records) rather than a directory:

```
filebot -extract file.part1.rar file.part2.rar --output <temp_dir>
filebot -rename <temp_dir> <non_archive_files...> \
  --output <plex_dir> --format "<format>" --action move -non-strict
```

Non-archive files are passed directly to `-rename` alongside the extraction temp dir. This keeps the two-step structure while eliminating all Python-side routing logic.

**Alternative considered**: Point FileBot at the whole `MEGABASTERD_DOWNLOAD_DIR`. Rejected because all downloads share that flat directory, so running FileBot on it when one download finishes would process in-flight files from other downloads.

### 2. FileBot format strings, not online DB lookup

We pass `--format "{plex}"` (FileBot's built-in Plex-compatible naming) with `--action move` and `-non-strict`, using `--q <title>` to hint the match. We do NOT rely on `--db TheTVDB`/`TheMovieDB` as the primary source of truth — the user-provided title and media type are the authority.

**Why**: Network lookups add latency and failure modes on the post-processing critical path. A failed lookup would leave files in the download dir. The user already provides correct title/year/type at queue time; FileBot's value here is structural (Plex-correct folder layout, archive handling) not metadata enrichment.

**Alternative considered**: Full online lookup with `--db`. Deferred — can be added as an opt-in config flag later.

### 3. Folder download expansion: create child DownloadFile records lazily

When the worker first sees megabasterd split a folder URL into N per-file entries, it creates N child `DownloadFile` records linked to the parent folder `DownloadFile` via a new nullable `parent_id` FK. The parent record transitions to a container role (its status is derived from children, not directly from megabasterd).

After expansion, each child tracks its own `progress_bytes`, `total_bytes`, `speed`, `name`, `status`, and eventual `file_path`. The original folder URL DownloadFile keeps its `url` as the submitted folder link and becomes the aggregation parent.

**Why**: The cleanest approach for persistent per-file visibility. The alternative (JSON blob on the parent record) would complicate the organizer's file path lookup and lose type safety. The alternative (return raw megabasterd data from the API without persisting it) loses history after completion.

**Timing**: Expansion happens on the worker's first tick where it sees folder-split entries for a given DownloadFile. Expansion is idempotent — if children already exist, no new records are created.

### 4. FileBot output parsing for final paths

FileBot logs each rename to stdout in the format: `[rename] From [/path/orig] to [/path/dest]`. We parse this to collect final paths and update `DownloadFile.file_path`. If stdout parsing yields no paths (unexpected output format), we fall back to scanning the output directory for files newer than the pre-invocation timestamp.

### 5. `MEGAQUEUE_FILEBOT_BIN` config var, startup validation

A new optional config var `FILEBOT_BIN` (default: `filebot`) points to the FileBot executable. On startup, `app.py` verifies the binary is callable (`filebot --version`). Failure is logged as a warning (not fatal) since FileBot is only needed at post-processing time, not at startup.

## Risks / Trade-offs

- **FileBot two-step for archives** → Mitigation: temp dir always cleaned up in `finally`; if extraction fails, post-processing marks download as failed with the FileBot stderr as the error message
- **FileBot stdout parsing brittleness** → Mitigation: filesystem scan fallback; log full stdout on parse failure
- **Lazy folder expansion races** → If the worker ticks twice before expansion commits, idempotency check (existing children query) prevents duplicate records
- **DB migration required** for `parent_id` column → Simple nullable FK addition; existing records unaffected (all null)
- **FileBot binary not installed** → Startup warning; post-processing will fail with a clear error message ("FileBot binary not found at: filebot")

## Migration Plan

1. Add `parent_id` column to `DownloadFile` table via Alembic migration
2. Deploy updated `worker.py` (folder expansion), `organizer.py` deletion, new `filebot_organizer.py`
3. Update `config.py` to add `FILEBOT_BIN`
4. Update `app.py` startup validation to check FileBot binary
5. Install FileBot on the Windows NUC
6. In-flight downloads at deploy time: will complete with the new worker but use the old organizer if already in `processing` state — acceptable since the worker atomically swaps the post-processing call

## Open Questions

- Should FileBot's `--db` online lookup be opt-in via a config flag from the start, or added in a later change?
- Does the Windows NUC FileBot install use `filebot` or `filebot.exe` as the binary name? (May need `MEGAQUEUE_FILEBOT_BIN` to be set explicitly on Windows)
