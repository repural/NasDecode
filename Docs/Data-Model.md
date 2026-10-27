# Data model, sources and refresh intervals

Reviewed: 2026-10-27 against main `d59d76f`. [Documentation index](README.md)

## Time and freshness

Trading dates and session boundaries use America/New_York. GitHub cron expressions are UTC. Source observation time, collection time, generated updatedET/asOf fields, commit time, and live publication time are distinct.

The intervals below are configured attempts, not SLAs. GitHub can delay or queue scheduled jobs; provider entitlements, stale data, holidays and failures can prevent a fresh observation. Reading a JSON file every 30 seconds does not make its upstream feed update every 30 seconds.

## Source-to-data map

| Data | Upstream source and fallback/qualification | Collector / destination | Configured refresh |
|---|---|---|---|
| Current Nasdaq, QQQ, SOX, SOXX, SMH, stocks and breadth constituents | CNBC quote service; source timestamps and quote status checked | refresh.py → daily/intraday history and dashboard | Main cash-session nominal 5-minute heartbeat, ET-gated; pre-open watchdogs and close triggers |
| 10Y and 2Y nominal yields | CNBC / Tradeweb quote observations | refresh.py → dashboard and history | Main refresh; browser does not independently recompute scores |
| Brent and WTI display | CNBC futures symbols @LCO.1 and @CL.1 | collect_live_oil.py → public/data/live-oil.json | Every 5 minutes weekdays, all UTC hours; browser rereads every 30 seconds |
| Cash index/futures display | Unofficial Yahoo chart API; query1 then query2 host | collect_live_indices.py → public/data/live-indices.json | Every 5 minutes weekdays; browser rereads every 30 seconds |
| Index selection | ^IXIC / ^GSPC during weekday 09:30–16:00 ET; NQ=F / ES=F otherwise | Same collector; mode and instrument retained | Selection evaluated on each collector run |
| Adjusted daily OHLCV/VWAP | Massive stock aggregates | collect_daily_bars.py / merge_daily_bars_archive.py → data/history/<ticker>-daily.json | 23:35 UTC weekdays; incremental scheduled collection, configurable manual backfill |
| Daily SMA20/SMA50 | Massive indicator API primary; controlled local adjusted-close fallback with complete windows and provenance | Same per-ticker daily bars, daily-bars-coverage.json | Daily-bar archive schedule |
| Historical context, RSI, ATR, Stoch, ADX/DMI, returns, drawdowns | Calculated from adjusted history; QQQ/SOXX SMA read from archive | refresh.py → dashboard.historicalContext / stored validation context | Recomputed during main refresh; newest underlying daily session may lag |
| Fed meeting probabilities | CME official Fed Funds settlements via cme-fedwatch 0.2.1; official EFFR/target context; legacy Barchart ZQ/H.15 fallback path | refresh.py → fedExpectations, row details and history | Reattempted during main refresh; settlement-based, not intraday probability ticks |
| FedWatch public-page diagnostics | CME public page; separate Tavily probe | refresh.py diagnostics; data/research/fedwatch-tavily-probe.json | Main refresh; Tavily probe at minute 12 during UTC hours 12–22 weekdays |
| 10Y real yield | U.S. Treasury real-yield XML | refresh.py → supporting valuation context | Main refresh attempts; official daily publication lag retained |
| Put/call observations | Cboe daily market statistics and five-session history | refresh.py → options positioning and history | Main refresh attempts; underlying data is daily, not transaction flow or dealer gamma |
| Macro actual/previous/consensus | Trading Economics calendar API/page; Tavily calendar retrieval fallback | refresh_macro_surprises.py → data/macro-surprises.json | Main refresh, before score calculation |
| Official macro actual verification | Release-specific official sources through verify_macro_actuals.py | Verification fields in macro-surprises.json | Main refresh; calendar consensus remains distinct from official actual |
| S&P 500 above-50DMA breadth (S5FI) | CNBC / EODData attempts; Tavily Investing/Barchart research observations | refresh.py; s5fi-single-provider.json; s5fi-tavily-observations.json | Main attempts plus 22:20 UTC weekday probe |
| Raw news candidates | Tavily search; regional/global company and macro source coverage | refresh_catalysts.py / market_watch_global.py → data/semiconductor-catalysts.json | 30 minutes UTC 00–08 and 11–23; hourly 09–10, weekdays |
| Curated Open Watch | Candidate sources plus explicitly authored/curated records; source URLs retained | refresh_market_watch.py → data/history/market-watch-events.json, status JSON, compact feed | Catalyst monitor schedule; source-file publisher on push/manual |
| Upcoming earnings | Nasdaq earnings calendar API, filtered to relevant universe | refresh_upcoming_earnings.py → data/upcoming-earnings.json | Catalyst monitor; next 28 days of relevance |
| Narrative research | Authored research with source URLs; not the quantitative collector | data/research/session-briefs.json | External authoring workflow/task; publish on main source-file push or manual dispatch |
| Legacy pre-market | Authored premarket-brief.json | sync_premarket_brief.py → data/premarket.json and public copy | Main refresh; distinct from unified source-file publisher |
| Numeric session checkpoints | Refined dashboard state and session observations | capture_session_analysis.py → session-analyses.json | Intended 10:30, 13:00, 15:30 ET, plus verified close path |
| Earnings AVWAP | Adjusted daily price/volume plus dated membership and earnings release anchors | collect_sox_avwap.py / sox_earnings_avwap.py → sox-avwap-daily.json, sox_avwap_latest.json | 22:40 UTC weekdays |
| Intraday AVWAP diagnostics | Massive adjusted 5-minute bars; entitlement-dependent current access | collect_intraday_avwap.py → research/intraday-avwap.json and public copy | Every 15 minutes UTC 13–21 weekdays; gate 09:30–16:10 ET |
| NVDA/SOXL WT historical candles | Massive adjusted 5-minute bars, extended-hours aggregation | research/refresh WT scripts → data/research/*-wavetrend.json | Update feed every 15 minutes in configured UTC windows; historical/manual jobs separate |
| Yahoo WT shadows/reconciliation | Yahoo intraday observations compared with later Massive history | Shadow JSON, reconciliation diagnostics and publication | Feed update/dependent workflow completion; reconciliation is not an independent source of prices |
| Phase 3 breadth and continuous macro research | Massive adjusted closes; dated membership snapshots; regime-context exact-date joins | phase3-constituent-breadth and validation research files | 05:20 UTC Tuesday–Saturday plus relevant code pushes/manual |
| Resilience/directional/context/hype research | Stored observations, point-in-time events and derived features | data/history research/model outputs | Main refresh or dedicated backfill/validation workflows; not new external data feeds |

S5FI research without independent verification is excluded from directional scoring. Options positioning here is put/call context, not the requested premium-weighted NVDA options flow or dealer-gamma analysis.

## Logical entities and schemas

Schemas are JSON-specific rather than a single relational database. Consult schemaVersion and the owning writer before editing.

| Entity / path | Grain / key | Important fields and meaning |
|---|---|---|
| data/dashboard.json | Current generated snapshot | updatedET, groups, rows, nasdaqScore, consolidationRisk, opportunityScore, soxlBuyScore, confirmationLayer, historicalContext, diagnostics |
| rows[] | Factor name within snapshot | factor, latest, signal, trend, currentImpact, freshness, source, explanation, scorecard. Display text is not a stable numeric interface |
| data/history/daily.json | records keyed by ET trading date | market observations, factors, sessionLevels, fedExpectations, validation, model state; closeSnapshot separate from intraday observations |
| data/history/intraday/YYYY-MM.json | snapshots[] keyed logically by timestampET | Market state, score snapshots and confirmation. Month-sharded history; not one independent observation per duplicated output |
| data/history/<ticker>-daily.json | Ticker and date | bars with date/open/high/low/close/volume/vwap; sma20, sma50 and provenance when available |
| daily-bars-coverage.json | Instrument collection manifest | asOfET, universeType, membershipAsOf, per-ticker status, session range, missing fields, SMA validation and fallback counts |
| data/macro-surprises.json | Economic release event | id/release key, period/releasedAt, actual, consensus, previous, units, sourceMode, official verification, scheduledEvents |
| research/session-briefs.json | sessions[YYYY-MM-DD][premarket/early_market/mid_market/near_close] | updatedET, bias, confidence, eventRisk, paragraphs, catalysts, whatChanged, whatToWatch, sources, publicationStatus, retrospective, verification flags |
| history/session-analyses.json | Trading date / stage | Scheduled/captured times, numeric checkpoints and generated checkpoint narrative; different from authored research |
| history/market-watch-events.json | events[] identified by stable id | eventTime, firstReported, category, companyMarket, headline, source/sourceUrl, whyItMatters, expectedImpact, marketConfirmation, status, initialAssessment, confirmationHistory |
| research/market-watch-monitor-status.json | Latest monitor attempt | Retrieval attempts/failures/results, accepted candidates, new publication count, active/total events; explains empty output |
| public/data/market-watch.json | Current active subset | activeEvents; empty active list can coexist with a nonempty historical archive |
| sox_avwap_membership.json | Dated universe and symbol anchors | membership asOf/source/status, constituents, original basket, per-symbol earningsDate/releaseSession/verification |
| sox_avwap_latest.json | As-of date and symbol | Coverage denominators, original-basket comparison, per-symbol AVWAP/distance/momentum, exclusions, scoringImpact |
| phase3-constituent-breadth.json | Date and explicitly labelled universe | Official dated snapshots, fixed proxy, retroactive current-constituent breadth, observed counts, missing symbols and coverage |
| regime-context-dataset.json | ET date and provenance cohort | features by trend/rates/volatility/energy/internals; outcomes separately labelled by instrument/horizon |
| Resilience/directional/context research | Date, version, horizon/state | Model specification, training/holdout protocol, features, scores/states, future outcomes and diagnostics |
| research/*-wavetrend.json | Symbol, timeframe, candle start/end | Source, generation/history-end times, session/boundary assumptions, completed OHLC, WT1/WT2/cross, validationStatus |
| WT backtest/research results | Frozen design + trade ledger | Input/code hashes, execution convention, costs, return, drawdown, baseline comparisons, unresolved equivalence |

## Units and null semantics

- Yield levels are percent; yield changes may be basis points. Keep bp and percent distinct.
- Relative return is percentage points; price return is percent.
- Forward horizons are trading sessions, not calendar days.
- Preserve raw values alongside derived explanations. Null is unavailable/unmatured, not zero.
- A source failure must not silently convert stale data into a current quote.
- Provider SMA values take precedence; local fallback must retain its own provenance and have a full valid window.
- Do not use publication mirrors as additional training observations.
- Corporate actions, adjusted prices, extended hours and anchor release session affect comparability.

## Ownership and lineage

Publishers may copy or filter authoritative data but must not independently edit the same conceptual observation. Per-instrument bar storage belongs to the collector/merge path. Main refresh consumes its SMA data.

Research session authority is the unified session-briefs file for its publisher and renderer. The legacy pre-market bridge remains a separate compatibility path; do not infer synchronization in both directions.

Current-source members applied retroactively are not historical point-in-time membership. The live SEMI_BREADTH list, Phase 3 snapshots, daily archive universe and earnings AVWAP membership currently differ; use the explicit label of each artifact.

## Publication map

See [Architecture](Architecture.md#parallel-publication-paths). Public replicas are deployment artifacts. A commit, a deployable JSON update, a Cloudflare build and browser-rendered values are separate verification steps.

Exact cron expressions for every workflow are recorded in [Workflow reference](Workflow-Reference.md). The older detailed field audit is preserved in [Archive](Archive/README.md).
