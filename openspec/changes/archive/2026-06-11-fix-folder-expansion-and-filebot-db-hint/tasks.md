## 1. Worker — folder URL detection

- [x] 1.1 Add `_is_folder_url(url) -> bool` helper in `megaqueue/megaqueue/worker.py` matching both `mega.nz/folder/…` and `mega.nz/#F!…`.
- [x] 1.2 Replace the two inline `"mega.nz/folder/" in df.url` checks (in `_match_megabasterd_files` and `_maybe_expand_folder_files`) with `_is_folder_url(df.url)`.
- [x] 1.3 Extend `_extract_folder_id` to also recognise `https://mega.nz/#F!{folderId}!…` and return `{folderId}`.

## 2. FileBot — db hint

- [x] 2.1 In `megaqueue/megaqueue/filebot_organizer.py`, derive `db = "TheMovieDB" if download.media_type == "movie" else "TheTVDB"`.
- [x] 2.2 Add `"--db", db` to the rename `cmd` (place it next to `--q`).

## 3. Tests

- [x] 3.1 Add `test_worker.py` cases: `_is_folder_url` returns True for `mega.nz/folder/abc#xyz`, True for `mega.nz/#F!abc!xyz`, False for `mega.nz/file/abc#xyz`, False for `mega.nz/#!abc!xyz`.
- [x] 3.2 Add `test_worker.py` case: `_extract_folder_id` returns `abc` for `mega.nz/#F!abc!xyz`.
- [x] 3.3 Add `test_worker.py` case: old-format folder URL with multiple matching megabasterd entries gets expanded into per-file children (mirrors the existing new-format expansion test).
- [x] 3.4 Add `test_filebot_organizer.py` case: invoking with `media_type=movie` includes `--db TheMovieDB` in the subprocess args.
- [x] 3.5 Add `test_filebot_organizer.py` case: invoking with `media_type=tv` includes `--db TheTVDB` in the subprocess args.
- [x] 3.6 Update any existing `test_filebot_organizer.py` cases that assert the exact argv list to account for the new `--db` flag.

## 4. Verify

- [x] 4.1 Run `cd megaqueue && source .venv/bin/activate && pytest` and confirm the full suite passes.
- [ ] 4.2 Bump the `megaqueue` submodule pointer in the parent repo with a commit message summarising the fix.
- [ ] 4.3 Deploy to the NUC, then manually click Retry on the three failing downloads (For All Mankind, Gen V, Birth (2004)) to confirm each one completes through file organisation.
