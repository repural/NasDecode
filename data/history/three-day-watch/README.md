# NasDecode 3-Day Watch storage contract

The UI reads `public/data/three-day-watch.json` and renders only the newest assessment and full seven-section editorial. This file intentionally contains **one** current entry, preserving `schemaVersion: 1`, `kind: "three-day-watch-history"`, `updated`, `horizon`, and `entries`.

## Preserved legacy history

The original 299-entry file (exact original Git blob SHA `b23f62636572573379fb0070b062656ed45d3954`) is preserved without alteration at `data/history/three-day-watch/legacy-through-2026-11-10.json`. Do not load or rewrite it for hourly publication. The earlier standalone 2026-10-27 history file remains intact.

## Hourly publication protocol

1. Fetch the small current JSON and its SHA from `main`; read the newest entry and check the exact run timestamp for idempotency.
2. Read curated Open Watch events; research market inputs with timestamps, units, and quality flags. Never silently scale Treasury yields.
3. If not already published for that run, create **one** independent history file at `data/history/three-day-watch/YYYY-MM-DDTHHMM-ET.json`, containing the full assessment, including `editorial.marketOverview`, `whatChanged`, `marketInterpretation`, `threeDayPath`, `bullCase`, `bearCase`, `watchNext`.
4. Update `public/data/three-day-watch.json` with the **single latest** full assessment and its three-session horizon, preserving the archive metadata. Commit the history file and current JSON atomically using Git blobs/tree/commit/ref if available; otherwise write the history file first and update the current file using the current SHA, verifying both. Retry SHA conflicts by rereading/merging; never discard archived records.
5. Notify only on material outlook change or major new catalyst. Operational publication errors may be reported.

Do not append to the legacy archive. Do not modify NasCal.
