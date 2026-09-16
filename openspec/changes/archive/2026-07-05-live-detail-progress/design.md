## Context

The dashboard (`index.html` + `refresh.js`) polls `GET /api/status` every 5 seconds and surgically updates progress bars in the DOM. The detail page (`detail.html` + `detail.js`) renders progress bars server-side but has no client-side polling — bars are static until a manual page refresh.

The detail page shows two types of progress bars:
1. **Overall progress bar** — aggregates `progress_bytes` and `total_bytes` across all leaf files
2. **Per-file progress bars** — one per leaf file with status `downloading` and `total_bytes > 0`

## Goals / Non-Goals

**Goals:**
- Make detail page progress bars update live, matching the dashboard's 5-second polling
- Reuse the existing `/api/status` endpoint and status-change-triggers-reload pattern
- Keep the implementation simple — surgical DOM updates for progress, full reload for state changes

**Non-Goals:**
- Adding a dedicated single-download API endpoint (the existing endpoint returns all downloads; filtering client-side is sufficient)
- WebSocket or SSE-based updates (the polling pattern is established and adequate)

## Decisions

### 1. Reuse `/api/status` and filter client-side

**Decision**: Fetch the full download list from `/api/status` and find the current download by ID, matching the dashboard's approach.

**Rationale**: Avoids adding a new API endpoint. The response is small (tens of downloads at most). A dedicated endpoint would be marginally more efficient but adds surface area for no real benefit.

### 2. Add data attributes for DOM targeting

**Decision**: Add `data-id`, `data-status` to the card, `id="overall-progress"` to the overall bar wrapper, `data-file-id` to per-file cards, `data-progress` and `data-file-progress` to stats containers.

**Rationale**: Enables surgical DOM updates without fragile CSS selector chains. Matches the dashboard's `data-id` and `data-progress` pattern.

### 3. Reload on status change or new progress bars

**Decision**: If the download's status changes, or if `total_bytes` becomes available but no progress bar is rendered yet, trigger `location.reload()`.

**Rationale**: Status transitions change the entire page layout (badges, forms, action buttons). Building all that via DOM manipulation would be fragile. A full reload is simple and correct.

### 4. Only poll for active downloads

**Decision**: Skip polling entirely if the initial status is not `downloading` or `queued`.

**Rationale**: Terminal states (`complete`, `failed`, `cancelled`) and `processing`/`needs_review` don't have progress to track. Avoids unnecessary network requests.

## Risks / Trade-offs

- **Polling overhead** — Every 5 seconds the detail page fetches all downloads, not just the one being viewed. Acceptable given the small payload size and existing dashboard precedent.
