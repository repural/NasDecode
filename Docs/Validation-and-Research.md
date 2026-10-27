# Validation and research

Reviewed: 2026-10-27. [Documentation index](README.md)

## Status vocabulary

| State | Meaning |
|---|---|
| Descriptive study | Summarizes a historical association; not predictive validation |
| Retrospective external cohort | Different period, possibly reconstructed features; disclose provenance |
| Chronological holdout | Later period reserved within a model version |
| Pseudo-out-of-sample | Model was frozen for this run, but research process previously saw related period |
| Walk-forward | Fit only on eligible earlier rows for each prediction |
| Prospective shadow | Frozen model evaluated on later observations without production scoring |
| Production | Explicitly integrated into published behavior |

Do not promote a research model merely because files exist, an Action passes, or one state has a favorable average.

## Model history and current boundaries

Resilience is a structural residual/persistence/confirmation measure. Earlier directional v1/v2 scores did not establish reliable monotonic short-horizon prediction. Frozen v3 separates Uptrend Pullback, Washout/Rebound, Continuation and Neutral/Other; its development period ends2026-06-30 and holdout starts2026-07-01. SOXL is an outcome/timing instrument, not a classifier input.

The October6 engine note is preserved in Archive. Its sample counts/results describe that date and must not overwrite newer report outputs. Holdout files are recomputed artifacts; preserve versions/spec hashes when publishing an evaluation.

Context Engine v1 compares state means to continuous ridge and fixed quadratic research. Its source should be audited for label maturity and feature selection before any strong leakage-free claim. The newer Phase3 research explicitly adds offset sensitivity, horizon-purged expanding-window ridge, macro-only/historical-mean baselines, continuous breadth/macro interactions and exact-date alignment.

## Required controls

1. Features at T must use information available by the declared cutoff. Outcomes are labels only.
2. Purge training labels whose horizon has not matured before prediction time.
3. Fit normalization/imputation on training data only.
4. Keep 2025 reconstructed and canonical cohorts distinct; never pool merely for sample size.
5. Keep official date-scoped membership separate from fixed-current constituents applied retrospectively.
6. Report denominator, missing symbols, coverage and unavailable rows. Do not fill absent history with invented values.
7. Evaluate mean, median, hit rate, sample size, baseline and dispersion; account for overlapping horizons.
8. Use multiple sampling offsets when a non-overlap design depends on the initial offset.
9. A frozen specification changed after holdout inspection needs a new version/protocol.
10. Retain point-in-time event availability; first-reported/detected times are not interchangeable with hindsight event times.

## WaveTrend and simulation protocol

Historical candles use adjusted Massive five-minute observations aggregated into completed4H/8H blocks over04:00–20:00 ET. Verify session boundaries, extended hours, adjustments and TradingView equivalence explicitly. Yahoo incremental observations remain source-labelled and require reconciliation.

Simulation reports must specify evaluation period, warm-up, inherited-stock versus cash start, next-open execution, transaction costs, terminal marking, dividends/taxes exclusion and drawdown sampling. Compare to buy-and-hold on the same convention. Preserve trade ledgers and hashes, not only a return table.

NVDA/SOXL production-publication files and expanded MU/GOOGL research-branch studies are distinct. A study saved on a branch is not automatically merged or visible in the live UI. Inspect the current branch tree and Actions before reporting integration status.

## Research files and workflow families

- Resilience history/model/engine/backtest under data/history.
- Directional edge, regimesv2, frozenv3, development, holdout, retrospective2025 and prospective tracking files.
- Regime-context dataset and analyses; Context Engine output.
- Phase3 constituent breadth, recovery/divergence, provenance and continuous-macro validation.
- SOX shadow training/validation diagnostics and oil-pressure research.
- Earnings lead-up/mega-cap studies and event windows.
- WaveTrend data, shadows, reconciliation, backtests and separate branch reports.

Exact configured entry points are in [Workflow reference](Workflow-Reference.md). No numerical experiment was rerun as part of the documentation migration.
