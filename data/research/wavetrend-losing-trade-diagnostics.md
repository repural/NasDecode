# Losing-trade diagnostics: 4H WaveTrend

January 2–October 16, 2026; unchanged frozen NVDA/SOXL inputs. 0.10% friction on each side. Completed signal-entry trades only; inherited initial and still-open positions excluded from trade statistics.

Entry groups use information confirmed before execution. All buckets were declared before inspecting this diagnostic run. These are retrospective descriptions; correlated observations, small groups and repeated exploration preclude treating them as proven predictors.

## NVDA

Completed trades: 55; losing: 32; winning: 23.
Losses exiting within four 4H bars: 19. Gross nonnegative trades made negative by costs: 3. Losing trades with an intratrade high at least 1% above entry: 13.
After a losing exit, 7/31 eligible windows rose at least 5% by the close of 20 subsequent 4H bars. This is a future outcome, not an entry feature.

| Entry characteristic | Trades | Losses | Loss rate | Mean net trade return |
|---|---:|---:|---:|---:|
| WT <= -45 | 9 | 2 | 22.22% | 3.969% |
| -45 < WT < 0 | 23 | 16 | 69.57% | -0.251% |
| WT >= 0 | 23 | 14 | 60.87% | -0.403% |
| Price > EMA20 | 37 | 22 | 59.46% | -0.142% |
| Price <= EMA20 | 18 | 10 | 55.56% | 1.44% |
| +DI > -DI | 35 | 23 | 65.71% | -0.375% |
| +DI <= -DI | 20 | 9 | 45.0% | 1.689% |
| ADX rising | 27 | 15 | 55.56% | -0.136% |
| ADX flat/falling | 28 | 17 | 60.71% | 0.869% |
| 8H bullish | 19 | 10 | 52.63% | -0.195% |
| 8H bearish | 36 | 22 | 61.11% | 0.677% |
| Daily bullish | 27 | 17 | 62.96% | -0.386% |
| Daily bearish | 28 | 15 | 53.57% | 1.11% |
| Entry Jan-Jun | 34 | 19 | 55.88% | 0.416% |
| Entry Jul-Oct | 21 | 13 | 61.9% | 0.311% |

| Metric | Losing-trade median | Winning-trade median |
|---|---:|---:|
| holding4hBars | 3.0 | 9 |
| wt1 | -5.124 | -22.166 |
| wtSeparation | 1.696 | 2.034 |
| emaDistancePct | 0.625 | 0.473 |
| diSpread | 5.67 | 1.977 |
| adx14 | 22.778 | 24.409 |
| atrPct | 1.554 | 1.777 |
| prior3barReturnPct | 1.569 | 1.17 |
| mfePct | 0.836 | 4.233 |
| maePct | -1.631 | -0.729 |
| entryGapPct | 0.001 | 0.004 |

| Worst trade entry ET | Exit ET | Net return | WT1 at signal | ADX | ATR % | Best intratrade gain % | Worst intratrade decline % |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-06-18T12:00:00-04:00 | 2026-06-23T04:00:00-04:00 | -3.38% | -4.87 | 16.17 | 1.51 | 2.40 | -3.19 |
| 2026-06-09T08:00:00-04:00 | 2026-06-09T12:00:00-04:00 | -3.13% | -37.14 | 15.76 | 2.01 | 1.05 | -3.04 |
| 2026-07-10T12:00:00-04:00 | 2026-07-13T16:00:00-04:00 | -2.83% | 39.82 | 17.10 | 1.87 | 0.99 | -2.88 |
| 2026-10-13T16:00:00-04:00 | 2026-10-14T12:00:00-04:00 | -2.81% | -42.94 | 27.35 | 1.18 | 0.56 | -2.76 |
| 2026-08-17T12:00:00-04:00 | 2026-08-18T04:00:00-04:00 | -2.65% | 47.26 | 46.43 | 1.16 | 0.02 | -2.45 |

Previously tested companion strategies (full portfolio backtests; not hypothetical deletion of losing trades):

| Rule | Net return | Win rate | Wins / closed trades | Max close drawdown |
|---|---:|---:|---:|---:|
| baseline | +18.96% | 41.82% | 23/55 | -10.67% |
| ema20 | +3.93% | 41.30% | 19/46 | -12.52% |
| dmi14 | +1.19% | 38.64% | 17/44 | -13.68% |
| dmi_adx | -7.30% | 44.12% | 15/34 | -16.51% |
| atr_exit | +26.88% | 43.64% | 24/55 | -9.11% |
| price_confirmation | -2.09% | 33.33% | 11/33 | -14.75% |

## SOXL

Completed trades: 53; losing: 28; winning: 25.
Losses exiting within four 4H bars: 18. Gross nonnegative trades made negative by costs: 0. Losing trades with an intratrade high at least 1% above entry: 22.
After a losing exit, 9/26 eligible windows rose at least 5% by the close of 20 subsequent 4H bars. This is a future outcome, not an entry feature.

| Entry characteristic | Trades | Losses | Loss rate | Mean net trade return |
|---|---:|---:|---:|---:|
| WT <= -45 | 8 | 5 | 62.5% | -0.79% |
| -45 < WT < 0 | 16 | 9 | 56.25% | 6.353% |
| WT >= 0 | 29 | 14 | 48.28% | 0.301% |
| Price > EMA20 | 33 | 17 | 51.52% | 0.952% |
| Price <= EMA20 | 20 | 11 | 55.0% | 3.631% |
| +DI > -DI | 26 | 12 | 46.15% | 0.676% |
| +DI <= -DI | 27 | 16 | 59.26% | 3.203% |
| ADX rising | 25 | 11 | 44.0% | 2.782% |
| ADX flat/falling | 28 | 17 | 60.71% | 1.232% |
| 8H bullish | 12 | 5 | 41.67% | 3.591% |
| 8H bearish | 41 | 23 | 56.1% | 1.487% |
| Daily bullish | 25 | 12 | 48.0% | 0.956% |
| Daily bearish | 28 | 16 | 57.14% | 2.863% |
| Entry Jan-Jun | 31 | 14 | 45.16% | 3.905% |
| Entry Jul-Oct | 22 | 14 | 63.64% | -0.773% |

| Metric | Losing-trade median | Winning-trade median |
|---|---:|---:|
| holding4hBars | 4.0 | 10 |
| wt1 | -0.651 | 16.528 |
| wtSeparation | 3.109 | 1.902 |
| emaDistancePct | 2.439 | 3.627 |
| diSpread | -1.033 | 6.31 |
| adx14 | 22.794 | 31.848 |
| atrPct | 5.528 | 5.047 |
| prior3barReturnPct | 6.669 | 5.253 |
| mfePct | 3.172 | 14.805 |
| maePct | -8.234 | -2.679 |
| entryGapPct | -0.013 | 0.0 |

| Worst trade entry ET | Exit ET | Net return | WT1 at signal | ADX | ATR % | Best intratrade gain % | Worst intratrade decline % |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-06-09T08:00:00-04:00 | 2026-06-09T12:00:00-04:00 | -21.68% | -12.74 | 24.61 | 7.70 | 1.41 | -21.86 |
| 2026-09-11T16:00:00-04:00 | 2026-09-14T08:00:00-04:00 | -15.74% | 14.23 | 18.09 | 4.11 | 0.36 | -15.77 |
| 2026-06-25T08:00:00-04:00 | 2026-06-26T08:00:00-04:00 | -13.31% | 0.49 | 18.88 | 7.74 | 2.46 | -14.02 |
| 2026-07-14T12:00:00-04:00 | 2026-07-15T12:00:00-04:00 | -12.65% | -21.53 | 27.21 | 8.01 | 6.12 | -12.98 |
| 2026-10-16T04:00:00-04:00 | 2026-10-16T16:00:00-04:00 | -11.32% | -63.04 | 44.91 | 6.58 | 3.65 | -11.38 |

Previously tested companion strategies (full portfolio backtests; not hypothetical deletion of losing trades):

| Rule | Net return | Win rate | Wins / closed trades | Max close drawdown |
|---|---:|---:|---:|---:|
| baseline | +127.08% | 47.17% | 25/53 | -53.49% |
| ema20 | +50.32% | 51.06% | 24/47 | -69.33% |
| dmi14 | +105.26% | 54.05% | 20/37 | -66.21% |
| dmi_adx | +103.78% | 55.56% | 15/27 | -34.32% |
| atr_exit | +35.19% | 45.28% | 24/53 | -53.49% |
| price_confirmation | +102.31% | 51.35% | 19/37 | -51.59% |

## Conclusions and next validation

- Rapid reversal is the strongest common descriptive pattern: most losses exited within four bars, whereas median winners lasted nine bars for NVDA and ten for SOXL. This explains whipsaw damage but does not identify bad trades in advance.
- Entry WT level behaves differently by asset. NVDA entries at or below -45 lost 2/9 times, versus 30/46 outside that zone. SOXL entries at or below -45 lost 5/8 times, versus 23/45 outside. A universal oversold-only entry filter is not supported.
- SOXL winners entered with materially higher median ADX and positive directional spread. Its previously tested DMI plus rising ADX filter improved win rate and drawdown while reducing total return. NVDA directional/EMA gates did not improve the prior full portfolio results.
- Some losing trades first moved favorably. This supports investigating exits, but does not prove a particular stop or profit target: the existing ATR exit helped NVDA and hurt SOXL.
- Costs explain three NVDA losses and zero SOXL losses by flipping nonnegative gross returns negative; price reversals, rather than costs alone, explain most losing trades.
- Next controlled experiments should isolate oversold entry from overbought exit, retain the original strategy as comparator, and validate frozen rules on later untouched data. The prior zone strategy changed both entry and exit, so its benefit cannot be attributed to entry filtering alone.

## Interpretation limits

- A rapid losing exit describes a whipsaw after it happened; it is not information available when buying. The reported holding time is in available extended-hours 4H bars, not continuous clock hours.
- MFE/MAE use highs/lows while held plus the exit fill itself. The entry candle is included; later high/low of the exit candle is excluded because execution is at its open. They do not establish executable stop/profit targets or high/low order.
- Entry gap is the next-open move from the signal close. That exact fill gap is an execution observation, not known at the preceding signal close.
- Mean trade returns are unweighted arithmetic averages, not portfolio returns. Winner and loser characteristics describe association, not causation.
- Rejecting one original trade changes position timing and subsequent trades. Only the existing complete backtests support portfolio comparisons; entry-group loss rates do not establish filter profitability.
- Already explored 2026 data; no independent validation. Comparing many characteristics creates selection risk. Asset-specific findings need later, untouched data with rules frozen first.
- Existing baseline enters in a bullish WT state and exits on red crosses. The separately tested zone strategy changes both entry and exit; this diagnostic concerns the original baseline.
- Source and code hashes and trade-level features are retained in the adjacent JSON. No live signals or UI were changed.
