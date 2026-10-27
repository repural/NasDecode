# NasDecode field-level data inventory and provenance audit
Date: 2026-10-12
Repository: repural/NasDecode
Scope: tracked JSON files under data/, public/data/, public/history/ at main; read-only audit. NasCal excluded.

## Inventory (verified from complete, non-truncated Git tree)
- 62 JSON files / approximately 24 MB of current tracked data.
- data/history: 41 files; data/research: 2 files; data/ root: 10 files.
- public/data: 8 files; public/history: 1 file.
- Biggest: data/history/intraday/2026-10.json (10,569,856 bytes), 2026-09.json (5,773,903), resilience-daily.json (1,460,562), daily.json (1,274,863).
- Current Git tree, NOT historical object-pack size or a database row count. Counts may change after this snapshot.

## Confirmed identical publication copies (Git blob SHA equality; seven pairs)
| Authoritative/research-side file | Published file |
|---|---|
| data/dashboard.json | public/data/dashboard.json |
| data/premarket.json | public/data/premarket.json |
| data/history/chart-history.json | public/data/chart-history.json |
| data/history/session-analyses.json | public/data/session-analyses.json |
| data/history/market-watch-events.json | public/history/market-watch-events.json |
| data/sox_avwap_latest.json | public/data/sox_avwap_latest.json |
| data/research/session-briefs.json | public/data/session-research.json |

These are intentional deployment replicas, not independent observations. data/semiconductor-catalysts.json (280,871 bytes) and public/data/semiconductor-catalysts.json (109,044) are NOT byte-identical: audit transformation/filtering before deduplication. public/data/market-watch.json has no confirmed byte-identical source in the paired paths.

## Field-level lineage and overlapping representations
| Domain | Likely upstream / observed schema | Derived or alternate locations | Fields overlapping / relevant caveats |
|---|---|---|---|
| Historical market observations | data/history/daily.json, data/history/intraday/YYYY-MM.json | resilience-daily, regime-context-dataset, directional-edge, phase3-market-structure-features, dashboard.historicalContext | trade date, prices, returns, SOX/QQQ relative returns, yields, VXN, oil, breadth. **Overlap confirmed by inspected downstream schemas, but row-by-row numeric equality NOT yet proven.** Large raw files could not be fully parsed through the connected GitHub reader. |
| Per-instrument OHLCV | data/history/soxl-daily.json and soxx-daily.json (Massive adjusted daily bars) | dashboard.historicalContext and score histories | bars contain date/open/high/low/close/volume/vwap; context also stores moving averages, RSI, ATR, distance-to-high, etc. Distinguish prices from calculated indicators. |
| Market structure & SOX proxy | data/history/phase3-constituent-breadth.json | phase3-market-structure-features, phase3-breadth-divergence-research, regime-context-dataset | constituent coverage, observed count, missing symbols, breadth %, SOX-vs-QQQ relative 5D/10D return. Proxy vs date-scoped verified membership must remain separate. |
| Resilience modeling | resilience-daily, resilience-model, resilience-engine | resilience-backtest, phase3-resilience-feature-audit, regime-context-dataset | horizon returns, residuals, persistence, confirmation, score, forward return labels. Separate point-in-time features from outcomes to prevent leakage. Engine/model/backtests are outputs not raw feeds. |
| Directional modeling | directional-edge, directional-regimes-v2, directional-engine-v3 | directional-*-backtest, directional-engine-v3-holdout, directional-v3-development, regime-context-dataset | SOX/QQQ 1D/5D/10D returns, relative momentum, breadth, setup labels, scores, forward horizons. Frozen validation sets should be retained as immutable/versioned artifacts. |
| Earnings studies | earnings_leadup_analysis, megacap_earnings_analysis | upcoming-earnings, earnings AVWAP watchlist, sox-avwap-daily, sox_avwap_latest | earnings date/release session, event-window offsets, OHLC, benchmarks; do not merge events across sessions by ticker/date without release-session and event-day keys. |
| Narrative and event research | research/session-briefs, research/premarket-brief, history/market-watch-events | data/premarket, public/data/session-research, public/data/premarket; macro-surprises, semiconductor-catalysts | tradingDate/session/updatedET, paragraphs/catalysts/sources vs numerical checkpoints in history/session-analyses. Pre-market exists in both unified research file and legacy premarket-brief; authority/migration needs clarification. |
| S5FI 50D breadth | history/s5fi-single-provider.json | dashboard.rows S&P 500 50D Breadth / Oversold | observations contain date, pctAbove50dma, sourceUrls, verification, independentlyVerified=false. Research-only; do not treat regional Investing sites as independent publishers or score provisional values. |
| Dashboard current snapshot | data/dashboard.json | public/data/dashboard.json | groups, rows (factor, latest, direction, signal, freshness, source, currentImpact, trend, scorecard), nasdaqScore, opportunityScore, risk, confirmation, contextual bars. Denormalized read model; NOT canonical raw history. |
| Session checkpoints | history/session-analyses.json | public/data/session-analyses.json | tradingDate, stage, capturedET, numeric market movements and scores; distinct from AI-written research sessions. |

## Provenance / structural risks
1. **Seven exact publication mirrors.** Expected for static hosting but should have clear ownership and must not be independently modified.
2. **Intraday history dominates size:** the two monthly files total 16,343,759 bytes (~69% of current data-file bytes). Rewriting large monthly JSON files for incremental ticks creates Git growth and merge contention.
3. **Feature materialization:** multiple shadow models preserve similar momentum and market context fields; whether values are truly duplicated or have differing cutoffs/cohorts must be determined from source join keys and feature lineage.
4. **Temporal leakage:** several datasets contain both T features and forward outcomes; avoid accidentally joining labels as predictors. Preserve frozen train/holdout partitions.
5. **Two pre-market research source shapes:** research/premarket-brief.json and research/session-briefs.json both contain premarket; identify one authoritative editor and bridge the old interface only as compatibility.
6. **Mixed data confidence:** S5FI single-provider history, fixed research proxy SOX breadth, and full verified SOX membership MUST retain distinct evidence labels.
7. **Historical schema versioning:** session, dashboard, and model schemas differ; avoid a blanket file merge without versioned migration.

## Recommended staged actions (not implemented)
1. Create a machine-readable catalog: file path, role (raw/derived/research/model/publication), grain (symbol/date/timestamp/event), keys, units, timezone, source/publisher, as-of cutoff, refresh cadence, schema version, retention, destination.
2. Add offline schema/uniqueness tests for (date,symbol,session), OHLCV constraints, S5FI evidence, and publication equality/expected transformation.
3. Perform row-by-row equality/field provenance on daily/intraday/resilience/regime datasets with a GitHub Actions job that can actually read large files. Report duplicate feature rows, missingness and coverage; do not conflate matching names with matching semantics.
4. Mark source-of-truth for premarket narrative and event research. Keep published JSON replicas as deployment artifacts.
5. Assess month-sharded compressed Parquet or an analytical store for intraday series, leaving UI snapshots and research in JSON. Avoid migration until reproducibility and cost are measured.

## Audit limitations
- This audit verified all 62 paths, file byte sizes and exact copy relationships from Git trees, and inspected JSON schema samples/full contents of smaller files.
- The GitHub file reader returned empty content for some multi-megabyte histories, so this report DOES NOT assert exact duplicate field counts, per-date value equality, total logical row counts, or null percentages across the largest source files.
- No data feeds, scoring algorithms, stored observations, or NasCal files were modified as part of this audit.
