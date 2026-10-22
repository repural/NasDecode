# WaveTrend zone-cross simulation

Fixed evaluation window: January 2–October 16, 2026. Prior adjusted Massive input snapshots; no parameter optimization.

Baseline uses the prior bullish-state entry and red-cross exit. Zone rules require a NEW green cross with WT1 ≤ −45 (strict: −53) to buy, and a NEW red cross with WT1 ≥ +45 (strict: +53) to sell. Crosses outside these zones are ignored; positions persist until an eligible opposite cross. More extreme readings qualify. WT1 is measured at the completed crossover candle close.

All variants start with the same inherited $10,000 stock position at the last completed 2025 close. Decisions use completed 4H or 8H candles; execute at the next available 4H open with 0.10% friction each side. Final positions are marked, not forced liquidated.

## NVDA

| Timeframe | Rule | Net return | Max close drawdown | Win rate | Wins/closed | Losing trades | Missed/delayed rebound starts | Fully missed rebounds | Final position |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 4H | Original WT | +18.96% | -10.67% | +41.82% | 23/55 | 32 | 0/10 | 0/10 | shares |
| 4H | Zone ±45 | +35.43% | -15.79% | +80.00% | 4/5 | 1 | 3/10 | 3/10 | shares |
| 4H | Zone ±53 | +17.41% | -16.39% | +100.00% | 3/3 | 0 | 3/10 | 3/10 | shares |
| 8H | Original WT | +18.04% | -16.96% | +44.00% | 11/25 | 14 | 7/10 | 0/10 | cash |
| 8H | Zone ±45 | +28.25% | -17.29% | +100.00% | 1/1 | 0 | 2/10 | 2/10 | cash |
| 8H | Zone ±53 | +7.37% | -17.29% | — | 0/0 | 0 | 5/10 | 5/10 | cash |

Open signal-entry positions at the final mark (entry cost included; no hypothetical exit cost):

- 4H Original WT: entered 2026-10-16T08:00:00-04:00, marked return -1.64%. Included in portfolio return/drawdown, excluded from completed-trade win rate.
- 4H Zone ±45: entered 2026-10-16T08:00:00-04:00, marked return -1.64%. Included in portfolio return/drawdown, excluded from completed-trade win rate.
- 4H Zone ±53: entered 2026-10-16T08:00:00-04:00, marked return -1.64%. Included in portfolio return/drawdown, excluded from completed-trade win rate.

### Cost and initial-position sensitivity

| Timeframe | Rule | No costs | 0.25%/side | Start in cash, 0.10%/side | Jan–Jun return | Jul–Oct return | Exposure |
|---|---|---:|---:|---:|---:|---:|---:|
| 4H | Original WT | +33.07% | +0.54% | +16.86% | +16.37% | +2.23% | 49.50% |
| 4H | Zone ±45 | +37.06% | +33.01% | +34.38% | +6.97% | +26.60% | 51.76% |
| 4H | Zone ±53 | +18.35% | +16.00% | +26.29% | -1.32% | +18.98% | 64.07% |
| 8H | Original WT | +24.21% | +9.33% | +16.12% | +5.87% | +11.49% | 50.50% |
| 8H | Zone ±45 | +28.63% | +27.67% | +35.07% | +7.98% | +18.77% | 71.11% |
| 8H | Zone ±53 | +7.48% | +7.21% | +13.45% | +7.37% | +18.77% | 36.43% |

Buy and hold before costs: +14.64%.

## SOXL

| Timeframe | Rule | Net return | Max close drawdown | Win rate | Wins/closed | Losing trades | Missed/delayed rebound starts | Fully missed rebounds | Final position |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 4H | Original WT | +127.08% | -53.49% | +47.17% | 25/53 | 28 | 0/25 | 0/25 | cash |
| 4H | Zone ±45 | +46.24% | -54.18% | +66.67% | 2/3 | 1 | 17/25 | 17/25 | shares |
| 4H | Zone ±53 | +61.87% | -43.97% | +100.00% | 2/2 | 0 | 17/25 | 17/25 | shares |
| 8H | Original WT | -17.60% | -68.97% | +40.00% | 14/35 | 21 | 16/25 | 0/25 | cash |
| 8H | Zone ±45 | +20.01% | -44.64% | +100.00% | 1/1 | 0 | 16/25 | 16/25 | cash |
| 8H | Zone ±53 | -27.31% | -44.64% | — | 0/0 | 0 | 16/25 | 16/25 | shares |

Open signal-entry positions at the final mark (entry cost included; no hypothetical exit cost):

- 4H Zone ±45: entered 2026-10-14T04:00:00-04:00, marked return -25.53%. Included in portfolio return/drawdown, excluded from completed-trade win rate.
- 4H Zone ±53: entered 2026-10-16T04:00:00-04:00, marked return -10.66%. Included in portfolio return/drawdown, excluded from completed-trade win rate.
- 8H Zone ±53: entered 2026-07-21T04:00:00-04:00, marked return -37.19%. Included in portfolio return/drawdown, excluded from completed-trade win rate.

### Cost and initial-position sensitivity

| Timeframe | Rule | No costs | 0.25%/side | Start in cash, 0.10%/side | Jan–Jun return | Jul–Oct return | Exposure |
|---|---|---:|---:|---:|---:|---:|---:|
| 4H | Original WT | +152.74% | +93.36% | +106.17% | +266.34% | -38.01% | 51.76% |
| 4H | Zone ±45 | +47.42% | +44.50% | +18.53% | +71.15% | -44.47% | 35.18% |
| 4H | Zone ±53 | +62.85% | +60.42% | +31.20% | +71.15% | -51.47% | 37.31% |
| 8H | Original WT | -11.54% | -25.94% | -25.19% | +72.73% | -52.30% | 51.26% |
| 8H | Zone ±45 | +20.37% | +19.47% | +3.69% | +15.74% | -42.17% | 30.15% |
| 8H | Zone ±53 | -27.16% | -27.52% | -37.19% | +15.74% | -64.97% | 33.92% |

Buy and hold before costs: +123.69%.

## Definitions and limitations

- Win rate and losing trades use completed signal-entry round trips after costs. The inherited initial position and still-open trades affect portfolio results but are excluded from trade statistics. Small samples can make win rates misleading.
- Maximum drawdown is measured at 4H portfolio closes, so intrabar declines can be larger.
- A rebound is a 4H green cross followed by at least 5% from next open to close 20 bars later. Missed starts include delays; windows can overlap. Original 4H has zero missed starts by construction.
- Subperiods are independently initialized with inherited positions. They are exploratory diagnostics, not holdouts or concatenating segments.
- Ignoring red crosses outside the upper zone can keep a position invested through deep declines. Ignoring green crosses outside the lower zone can leave cash uninvested during rallies.
- Extended-hours 04:00–20:00 ET candles and next-open fills are retained from the prior experiment. Fixed cost scenarios do not model varying spreads, impact, taxes, dividends or cash interest. TradingView numerical equivalence is unverified.
- These are retrospective 2026 results using the frozen earlier comparison period, not current live signals. No thresholds were selected after inspecting these results.

The adjacent JSON retains input/code hashes, all three costs, full primary execution/trade/equity ledgers, initial-position sensitivities and independent half-year diagnostics.
