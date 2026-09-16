## Why

The dashboard's progress bars update live every 5 seconds via polling, but the download detail page renders progress bars only at page-load time. Users watching a download in progress on the detail page see stale progress data and must manually refresh to see updates. This is inconsistent and frustrating.

## What Changes

- Add polling logic to `static/detail.js` that fetches `/api/status` every 5 seconds and surgically updates the overall and per-file progress bars (width, byte counts, percentage, speed)
- Add `data-` attributes to `templates/detail.html` to enable DOM targeting for live updates
- Reuse the same status-change-triggers-reload pattern from the dashboard: if the download's status changes or progress bars appear for the first time, the page reloads

## Capabilities

### Modified Capabilities
- `web-ui`: The detail page progress bars now update live, matching the dashboard behavior

## Impact

- **Code**: `static/detail.js` (polling logic), `templates/detail.html` (data attributes for DOM targeting)
- **Tests**: No new tests — this is client-side JS using the existing `/api/status` endpoint
- **No breaking changes**: No API changes, no backend changes
