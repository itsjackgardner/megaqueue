## Why

MegaQueue handles TV shows well when all episodes are already released, but there's no support for **currently airing shows**. The real-world workflow for ongoing shows is: save a mega.nz folder link that gets new episodes added over time, then periodically re-download only the new episodes. MegaQueue can't do this today — re-submitting the same folder link creates a duplicate entry, re-downloads everything, and the organiser clashes with files already in the Plex library.

## What Changes

- **Folder re-check**: A "Re-check" action on completed folder downloads that queries megabasterd for the current folder contents, identifies episodes not yet downloaded, and automatically queues only the new ones — reusing the existing Download entry.
- **Megabasterd folder-list endpoint**: A new REST endpoint in megabasterd that returns the file listing for a mega.nz folder without starting a download.
- **Ongoing status**: Manual "mark as ongoing" / "mark as finished" toggle on any download. Ongoing downloads appear in a dedicated "Ongoing" section at the top of the queue page for quick access to currently airing shows.
- **Duplicate folder detection**: When submitting a folder link that already exists in the queue, warn the user and suggest re-checking the existing entry instead of creating a duplicate.
- **Organiser skip-existing**: The file organiser skips files that already exist at the destination path, so re-checked episodes that were already organised don't cause errors.

## Capabilities

### New Capabilities

- `folder-recheck`: Re-checking a mega.nz folder link for new files, diffing against already-downloaded files, and queuing only new ones within the existing Download entry.
- `download-ongoing`: Manual "mark as ongoing" toggle on downloads, with a dedicated "Ongoing" section in the queue UI.

### Modified Capabilities

- `download-engine`: The download engine must support re-opening a completed download to add new files and return it to downloading status. Megabasterd client gains a folder-list method.
- `web-ui`: The queue page adds an ongoing section and re-check/ongoing toggle actions. The add form warns on duplicate folder links.
- `file-organizer`: The organiser must skip files that already exist at the destination rather than failing or overwriting.
- `data-model`: Download model adds an `ongoing` flag. DownloadFile records for already-completed episodes must be preserved when new ones are added.

## Impact

- **megabasterd (Java)**: New `/folder-list` REST endpoint that accepts a folder URL and returns file metadata without downloading.
- **megaqueue Python package**: Changes to `worker.py`, `sync.py`, `lifecycle.py`, `organiser.py`, `models.py`, `migrations.py`, `app.py`, and templates.
- **Database**: New `ongoing` boolean column on `downloads` table (migration required).
- **No breaking changes**: Existing downloads and workflows are unaffected. The new features are additive.
