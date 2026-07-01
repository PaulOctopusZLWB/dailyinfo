# Reader Analytics and Mobile Design

## Boundary

Info Radar reader is an internal information display surface. Analytics should measure reading behavior and content usefulness, not identify people. The first version stores anonymous sessions, item-level engagement, source opens, search/filter events, and short text-selection excerpts capped at 120 characters.

## Data Flow

The browser creates or reuses an anonymous `info_radar_session_id`. It batches client events and sends them to `POST /api/analytics/events` using `fetch` and `sendBeacon`. The server appends normalized events to `.info_radar/analytics/events.jsonl`. `GET /api/analytics/summary?date=YYYY-MM-DD` aggregates the event log by report date.

## Events

- `page_view`: report opened.
- `page_heartbeat`: active page dwell time.
- `item_view`: C/D/E item stayed in viewport.
- `source_open`: user opened a source drawer.
- `search`: user changed search text.
- `filter`: user changed direction filter.
- `text_select`: user selected text; store length and at most 120 characters.

## Reader Output

The web reader does not expose analytics to readers. Collection runs quietly in the background. Group-level summaries are available only through the internal `GET /api/analytics/summary` endpoint or the local `.info_radar/analytics/events.jsonl` log for later source weighting and quality analysis.

## Mobile Design

At small widths the layout becomes a single column. Header controls stack predictably, category tabs remain horizontal scroll, core/deep cards use full-width touch targets, and side rail blocks move below the content.
