# Operations and publication runbook

Reviewed: 2026-10-27. [Documentation index](README.md)

## Completion criteria

Record separately: source observation retrieved; validation passed; source/generated files committed; public JSON committed; hosting build completed; live endpoint/current browser verified. A successful Action can legitimately skip collection or preserve stale inputs. Check data times and diagnostics.

## Main jobs

Use [Workflow reference](Workflow-Reference.md) for exact triggers and UTC schedules. Main refresh is refresh.yml; refresh-dashboard.yml is a different narrow path. Narrative publisher runs on session-briefs source pushes and validates prose records; it is not a research generator. ChatGPT task scheduling is separate from GitHub Actions.

Do not run a full data refresh to validate documentation or a purely offline code change. The repository has dedicated validation workflows. The current main push filter ignores lowercase docs/** but not uppercase Docs/**; a Docs push can therefore trigger the existing refresh workflow. This migration does not change workflow behavior.

## Failure diagnosis

| Symptom | Inspect | Resolution criteria |
|---|---|---|
| Missing narrative analysis | source date/session record, publicationStatus, publisher log, public JSON, live URL | Valid current record, successful public commit and live delivery; retain retrospective label on repairs |
| Numeric checkpoint absent | schedule/gate selection, selected stage, verify_session_checkpoint output | Captured expected stage/time; do not count another date as current |
| Empty Open Watch | monitor-status retrieval errors, accepted/active counts, historical newest event | Distinguish no meaningful event from retrieval failure; preserve archive |
| Old WT data | test step, source entitlement, historicalDataEndET, reconciliation dependency | Tests pass, collection runs, new complete candle committed and served |
| SMA/AVWAP absent | archive manifest, provider/fallback provenance, stale date, verified earnings anchors | Adequate dated coverage; no inferred anchor or missing-price fabrication |
| Score/card mismatch | postprocessor ordering, effective/raw score, refreshed public snapshot | Same final values across snapshot/row/card/history where specified |
| Green Action but stale page | skipped steps, file timestamps, commit/path filter, hosting build, caching | Verify changed artifact and deployment, not just workflow conclusion |
| Push conflict | owning writer, lock, latest main, merge/regeneration method | Retry using owner-specific strategy without replacing newer independent data |

## Source/publication paths

- Unified narrative: edit data/research/session-briefs.json, validate with publish_session_research.py, inspect the publisher commit for public/data/session-research.json.
- Legacy pre-market: premarket-brief.json → sync_premarket_brief.py → data/premarket.json/public copy during main refresh.
- Open Watch: validate canonical data/history/market-watch-events.json; publish history/active representations; preserve IDs and confirmation history.
- Main dashboard: run ordered pipeline; copying dashboard JSON alone bypasses score/checkpoint consistency.
- Research: preserve spec, input/code hashes, ledgers and cohort labels; publication does not imply production promotion.

## Credentials and dependencies

GitHub Actions injects source credentials via secrets such as MASSIVE_API_KEY, TAVILY_KEY (mapped to TAVILY_API_KEY), and optional TRADING_ECONOMICS_API_KEY. Never put values in source, JSON, docs, browser bundles, or logs. Dependency/runtime versions belong to owning workflow; full refresh pins cme-fedwatch0.2.1.

Repository visibility and website asset scope are separate. Docs in this repository are public. src/index.js contains a possible live-macro Worker handler, but current wrangler configuration does not declare it as the main Worker entry.

## Change discipline

Preserve event history and daily-bar ownership. Avoid simultaneous independent edits to generated JSON. Main refresh regenerates after races; other workflows have different policies. Never force-push over concurrent market updates.

Documentation maintenance: update links, exact source/schedule map, schema grain/units, scoring versions and validation status with the relevant code change. Keep dated snapshots in Archive. Do not modify NasCal within NasDecode work.

## Validation for this documentation migration

Verify Markdown relative links, unchanged archived contents, absence of retired root/lowercase-docs files, minimal README and a commit diff limited to documentation paths. A docs-only change does not warrant rerunning market collection or backtests.
