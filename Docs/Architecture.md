# Architecture

Reviewed: 2026-10-27 against main `d59d76f`. [Documentation index](README.md)

## System purpose

NasDecode combines market observations, semiconductor participation, macro surprises, curated events, historical context, and narrative research into a Nasdaq-oriented dashboard. Direction, entry timing, consolidation vulnerability, and research model states are separate outputs.

## Components and boundaries

| Component | Responsibility | Implementation |
|---|---|---|
| Market collection/model | Normalize quotes, freshness, factor states, raw directional score, history | [refresh.py](../scripts/refresh.py) |
| Same-session confirmation | Refresh semiconductor leadership and internal confirmation when live coverage is adequate | [live_confirmation.py](../scripts/live_confirmation.py) |
| Market response | Bounded attenuation of the existing macro bucket after persistent contradictory internals | [apply_market_response.py](../scripts/apply_market_response.py) |
| Final scores | Publish directional score; calculate Consolidation Risk, Opportunity and SOXL entry measures | [refine_scores.py](../scripts/refine_scores.py) |
| Narrative research | Validate authored session briefs and publish their archive | [publish_session_research.py](../scripts/publish_session_research.py) |
| Numeric checkpoints | Capture quantitative early/mid/near-close and close observations | capture_session_analysis.py, select_session_checkpoint.py, verify_session_checkpoint.py |
| Open Watch | Discover, curate, deduplicate, validate and publish material events | refresh_catalysts.py, market_watch_global.py, refresh_market_watch.py, validate_open_watch.py |
| Independent quotes | Lightweight display-only index/futures and oil feeds | collect_live_indices.py, collect_live_oil.py |
| Historical/research jobs | Daily bars, SMA, AVWAP, breadth, WaveTrend and model diagnostics | Dedicated workflows and scripts |
| Presentation | Render generated JSON and narrative archives | index.html; public JavaScript |
| Hosting | Deploy static public assets | [wrangler.jsonc](../wrangler.jsonc) |

## Main refresh sequence

`refresh.yml` runs syntax validation, installs pinned FedWatch dependency, then:

1. Refresh the economic calendar and verify actual releases.
2. Run refresh.py to collect observations, derive factors, and write working/history state.
3. Sync the legacy pre-market bridge and publish unified session research.
4. Apply live confirmation, market response, final score refinement and pre-market score reconciliation.
5. Update the three-day watch; select, capture and verify the eligible numeric checkpoint.
6. Rebuild chart/hype histories and research artifacts: resilience, directional versions, regime context and prospective tracking.
7. Prepare public JSON, copy root index.html to public/index.html, inject the session-analysis UI, and commit generated outputs.

See [refresh.yml](../.github/workflows/refresh.yml) for exact command order, ET gates and retry behavior. The older [refresh-dashboard.yml](../.github/workflows/refresh-dashboard.yml) is a separate restricted refresh path; it is not equivalent to the full pipeline.

## Parallel publication paths

| Path | Authoritative input | Published artifact |
|---|---|---|
| Dashboard | data/dashboard.json | public/data/dashboard.json |
| Research sessions | data/research/session-briefs.json | public/data/session-research.json |
| Legacy pre-market | data/research/premarket-brief.json → data/premarket.json | public/data/premarket.json |
| Numeric sessions | data/history/session-analyses.json | public/data/session-analyses.json |
| Open Watch history | data/history/market-watch-events.json | public/history/market-watch-events.json |
| Active events | Curated event selection | public/data/market-watch.json |
| Earnings AVWAP | data/sox_avwap_latest.json | public/data/sox_avwap_latest.json |
| WaveTrend | data/research/nvda-wavetrend.json; soxl-wavetrend.json | Corresponding public/data files |
| Live quotes | Independent collectors | public/data/live-indices.json; live-oil.json |

A chat-generated report is not persisted merely because it appears in conversation. The publisher validates and copies records; it does not itself generate researched prose.

## Concurrency and persistence

The main refresh and legacy dashboard workflow share the nasboard-data-refresh lock. Other collectors use their own concurrency groups. Generated JSON has different retry policies: the main refresh regenerates from the latest main after a push race; daily bars merge their owned archive; some independent feeds rebase. Do not assume every writer has the same conflict policy.

Daily bars have a dedicated collector/merge ownership path. A general refresh may consume their indicators but must not overwrite that archive with a narrower history. Treat public copies as deployment artifacts.

## Hosting and exposure

wrangler.jsonc configures assets.directory=./public. The repository retains an older Worker name, nasboard. It does not declare a main entry for src/index.js. That source contains a read-only live macro proxy, but its existence is not proof that the endpoint is deployed.

GitHub reports the repository as public. Python, history and Docs are therefore visible through GitHub even though they are outside Cloudflare's public asset directory. No document here changes repository visibility.

## Change boundaries

This documentation change does not alter model code, market data, schedules, UI behavior, hosting configuration, or NasCal. For operational verification use the [runbook](Operations.md); for data ownership use the [data model](Data-Model.md).
