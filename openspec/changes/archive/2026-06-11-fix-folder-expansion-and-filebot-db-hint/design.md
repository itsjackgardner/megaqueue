## Context

Three failures in `fail_screenshots/`:

- `For All Mankind` (id=31, TV, 1 file) — folder URL `https://mega.nz/#F!th9WHKwR!m5RYPC6ytdaI4UEZTwjvxw`. Error: `File organization failed: Could not determine download file path: DownloadFile name not set for id=31`.
- `Gen V` (TV, 8 files) — error mentions `-q` (single-dash). Stale: commit `a701f627` already changed the code to `--q`.
- `Birth (2004)` (movie, 5 files) — `FileBot rename failed: Rename episodes using [TheMovieDB] with [Airdate Order]…`. FileBot's auto-classifier picked the episode renamer because extras files ("Making Birth.mkv", "Trailer.mkv", interview clips) confused it.

Relevant code:

- `worker.py:53–104` `_match_megabasterd_files` — three-tier matching. Tier 3 (folder-ID via `###n=…`) only populates `file_by_folder_id` when `"mega.nz/folder/" in df.url` (line 76).
- `worker.py:107–144` `_maybe_expand_folder_files` — only expands when `"mega.nz/folder/" in df.url` (line 124).
- `worker.py:187–189` `_update_file_from_megabasterd` — only sets `df.name` when `len(mb_entries) == 1`. So unsplit folder records never get a name.
- `worker.py:204–223` `_resolve_source_paths` — raises `ValueError("DownloadFile name not set …")` when `df.name` is falsy.
- `filebot_organizer.py:84–95` — rename invocation: `--output`, `--format {plex}`, `--action move`, `--q <title>`, `-non-strict`. No `--db`.

Why the old `#F!` URL pattern still shows up: it's accepted by `models.DownloadFile.url` without validation, and megabasterd handles both formats. We can't reject these without breaking the UX — and we shouldn't, because `mega.nz/#F!…` is a perfectly valid mega.nz folder URL.

## Goals / Non-Goals

**Goals:**

- Old-format folder URLs (`mega.nz/#F!…`) are split into per-file children on first poll after submit, the same way new-format folder URLs already are.
- FileBot is told whether the download is a movie or TV series so it picks the right database.
- Existing failed records become recoverable via the existing Retry button (no special code path needed).

**Non-Goals:**

- Auto-requeueing existing failed records — user does this manually.
- Reworking the matching/expansion logic — only the folder-detection predicate changes.
- Touching `_update_file_from_megabasterd`'s "only set name on single-entry" rule — that's correct for non-folder files and becomes moot for folder URLs once expansion runs.
- Changing how FileBot is invoked beyond adding `--db`. The `{plex}` format and `-non-strict` flag are kept.

## Decisions

### 1. Folder-detection predicate

Introduce a small helper `_is_folder_url(url) -> bool` in `worker.py` that returns true for both `mega.nz/folder/…` and `mega.nz/#F!…`. Replace the two inline `"mega.nz/folder/" in df.url` checks (lines 76 and 124) with `_is_folder_url(df.url)`.

Alternative considered: regex match inline at both call sites. Rejected — duplication, and we want the predicate covered by a unit test independently.

### 2. Folder-ID extraction for old format

`_extract_folder_id` already handles `mega.nz/folder/{id}` and the `###n={id}` suffix. Add a third pattern: `mega.nz/#F!{id}!…` → `{id}`. This makes Tier-3 matching work for old folder URLs without changing the matching code.

Alternative considered: skip the folder-ID lookup for old URLs and rely on Tier-2 (sourceUrl). Rejected — sourceUrl works in current megabasterd builds but the folder-ID path is the defence-in-depth fallback that already exists; keeping it consistent is worth one extra regex.

### 3. FileBot `--db` argument

Pass `--db TheMovieDB` for `media_type=movie` and `--db TheTVDB` for `media_type=tv`. Insert immediately after `--q` in the rename command. FileBot accepts `--db` (double-dash long form, same as `--output`/`--format`/`--action`/`--q` — see commit `1525624` and `a701f627`).

Alternative considered: `TheMovieDB::TV` (TheMovieDB's TV side) instead of `TheTVDB`. Rejected for now — TheTVDB is FileBot's traditional TV default and matches what the existing spec hints at. Easy to switch later.

Alternative considered: `--script fn:amc` for full auto-detection. Rejected — heavier, requires extra config, and we'd lose the `{plex}` format control.

### 4. No auto-retry

The Retry route (`app.py:95`) already resets `status=queued`, `downloading_since=None`, clears errors, and resets per-file state. Once the code fixes land, clicking Retry on `For All Mankind`, `Gen V`, and `Birth (2004)` will replay them through the fixed code path. No extra code needed.

## Risks / Trade-offs

- **Retry of `For All Mankind` will re-download the 6.5 GB folder.** Megabasterd may dedupe against the existing files on disk, but worst case the user pays the bandwidth again. Mitigation: documented in tasks, not in code.
- **`--db TheTVDB` could fail to match a series that TheMovieDB would have found.** TheTVDB is what FileBot's `-rename` defaults to for TV anyway, so this should be a no-op for the happy path. If specific series fail, we can revisit and switch to `TheMovieDB::TV` per-call.
- **Old-format folder URL regex.** The pattern `mega.nz/#F!` must not false-positive on file URLs (`mega.nz/#!`). The `F` is the distinguishing character. Test covers both.

## Migration Plan

1. Land code + tests on the `megaqueue` submodule.
2. Bump the submodule pointer in the parent repo.
3. Deploy to the NUC.
4. User clicks Retry on the three failed downloads in the UI.

Rollback: revert the submodule bump. No DB or config changes to undo.

## Open Questions

None.
