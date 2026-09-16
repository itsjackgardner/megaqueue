## Why

Three failure modes are showing up in production (captured in `fail_screenshots/`):

1. **Old-format folder URLs (`mega.nz/#F!…`) don't get expanded into per-file children.** The expansion gate in `worker.py` only matches `mega.nz/folder/…`. The parent record matches multiple megabasterd entries, never gets a `name`, and post-processing crashes with `DownloadFile name not set for id=<n>`.
2. **FileBot misclassifies movies as TV episodes.** When a movie has extras (trailers, featurettes) in the file list, FileBot's auto-detect picks the episode renamer and the lookup fails. We already know the media type from the user's submission but never pass it to FileBot.
3. (Diagnosed but no code change needed) The "Gen V" `-q` failure in the screenshots is stale — commit `a701f627` already switched the flag to `--q`. Existing failed records need a manual retry; that's outside the code change.

## What Changes

- Treat `mega.nz/#F!…` URLs as folders for the purpose of split-expansion, alongside `mega.nz/folder/…`.
- Pass `--db TheMovieDB` for `media_type=movie` and `--db TheTVDB` for `media_type=tv` when invoking FileBot rename.
- Add tests for both behaviours.

No data migration, no UI change, no auto-retry of existing failed records — the user will click Retry manually after deployment.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `download-engine`: Folder-URL expansion recognises both `mega.nz/folder/…` and `mega.nz/#F!…` formats.
- `filebot-integration`: FileBot rename invocation includes a `--db` argument selected from `Download.media_type`.

## Impact

- Code: `megaqueue/megaqueue/worker.py` (folder detection in `_maybe_expand_folder_files` and `_match_megabasterd_files` folder-ID lookup), `megaqueue/megaqueue/filebot_organizer.py` (rename command).
- Tests: `megaqueue/tests/test_worker.py`, `megaqueue/tests/test_filebot_organizer.py`.
- Specs: `openspec/specs/download-engine/spec.md`, `openspec/specs/filebot-integration/spec.md`.
- No config, no DB schema, no external dependency changes.
