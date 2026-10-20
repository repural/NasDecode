# WaveTrend timeframe comparison

Research only. WT 10/21/4; identical next-4H-open execution and costs. No thresholds optimized.

## Main comparison

Common window: 2026-01-01 to 2026-10-16. Daily filter uses adjusted regular-session OHLC; 4H/8H retain the existing 04:00–20:00 ET session.

Initially invested at the last completed 2025 candle close, matching the earlier backtest. For pairs, higher timeframe gates entry only and exits use the 4H bearish crossover. Standalone 8H/1D use their own WT entries and bearish-cross exits. Every variant executes on the next available 4H open and is marked on the same 4H closes.

### NVDA

| Strategy | Return, no costs | Return, 0.10%/side | Return, 0.25%/side | Max drawdown, 0.10% | Losing entry trades | Missed rebound starts | Fully missed rebounds |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4H alone | +33.07% | +18.96% | +0.54% | -10.67% | 32/55 | 0/10 | 0/10 |
| 8H alone | +24.21% | +18.04% | +9.33% | -16.96% | 14/25 | 7/10 | 0/10 |
| 1D alone | -12.34% | -15.36% | -19.69% | -23.84% | 12/17 | 6/10 | 0/10 |
| 4H + 8H | +12.87% | +4.29% | -7.38% | -15.32% | 21/39 | 7/10 | 0/10 |
| 4H + 1D | -9.96% | -17.63% | -27.94% | -23.12% | 29/44 | 6/10 | 0/10 |

Buy-and-hold, before costs: +14.64%.

#### Start-in-cash sensitivity (0.10% per side)

| Strategy | Return | Max drawdown | Executions |
|---|---:|---:|---:|
| 4H alone | +16.86% | -10.67% | 113 |
| 8H alone | +16.12% | -16.96% | 52 |
| 1D alone | -16.85% | -23.84% | 36 |
| 4H + 8H | +2.60% | -15.32% | 80 |
| 4H + 1D | -19.09% | -23.12% | 90 |

#### Session sensitivity: 2026-03-19 to 2026-10-16

Same shorter period for every row. Fully warmed daily bars; extended daily is built from four complete 4H bars.

| Strategy | Daily session | Return, 0.10%/side | Max drawdown |
|---|---|---:|---:|
| 4H alone | — | +14.39% | -10.67% |
| 8H alone | — | +27.78% | -11.28% |
| 1D alone | Regular | +2.20% | -20.60% |
| 4H + 8H | — | +11.98% | -10.04% |
| 4H + 1D | Regular | -10.37% | -17.58% |
| 1D alone | Extended | +6.74% | -18.24% |
| 4H + 1D | Extended | -7.44% | -15.45% |

### SOXL

| Strategy | Return, no costs | Return, 0.10%/side | Return, 0.25%/side | Max drawdown, 0.10% | Losing entry trades | Missed rebound starts | Fully missed rebounds |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4H alone | +152.74% | +127.08% | +93.36% | -53.49% | 28/53 | 0/25 | 0/25 |
| 8H alone | -11.54% | -17.60% | -25.94% | -68.97% | 21/35 | 16/25 | 0/25 |
| 1D alone | +110.28% | +104.27% | +95.56% | -58.45% | 9/14 | 12/25 | 0/25 |
| 4H + 8H | +28.39% | +17.69% | +3.27% | -64.82% | 23/43 | 16/25 | 0/25 |
| 4H + 1D | +98.36% | +83.28% | +62.77% | -44.63% | 22/39 | 12/25 | 0/25 |

Buy-and-hold, before costs: +123.69%.

#### Start-in-cash sensitivity (0.10% per side)

| Strategy | Return | Max drawdown | Executions |
|---|---:|---:|---:|
| 4H alone | +106.17% | -53.49% | 108 |
| 8H alone | -25.19% | -68.97% | 72 |
| 1D alone | +82.08% | -58.45% | 30 |
| 4H + 8H | +6.85% | -64.82% | 88 |
| 4H + 1D | +63.38% | -44.63% | 80 |

#### Session sensitivity: 2026-03-19 to 2026-10-16

Same shorter period for every row. Fully warmed daily bars; extended daily is built from four complete 4H bars.

| Strategy | Daily session | Return, 0.10%/side | Max drawdown |
|---|---|---:|---:|
| 4H alone | — | +127.01% | -53.49% |
| 8H alone | — | -3.72% | -68.97% |
| 1D alone | Regular | +92.55% | -58.45% |
| 4H + 8H | — | +40.45% | -64.82% |
| 4H + 1D | Regular | +117.18% | -40.45% |
| 1D alone | Extended | +45.81% | -55.80% |
| 4H + 1D | Extended | +79.16% | -40.98% |

## Interpretation

NVDA: 4H alone has the highest main-test net return at 0.10% per side. The best pair by return is 4H + 8H. Cost-scenario winners: zeroCosts: 4H alone, cost10bps: 4H alone, cost25bps: 8H alone. Starting in cash, the winner is 4H alone.

NVDA daily-filter trade-off versus 4H alone: -36.59 percentage points of return and -12.45 points of signed maximum drawdown (a positive drawdown difference means a shallower decline).

SOXL: 4H alone has the highest main-test net return at 0.10% per side. The best pair by return is 4H + 1D. Cost-scenario winners: zeroCosts: 4H alone, cost10bps: 4H alone, cost25bps: 1D alone. Starting in cash, the winner is 4H alone.

SOXL daily-filter trade-off versus 4H alone: -43.80 percentage points of return and +8.86 points of signed maximum drawdown (a positive drawdown difference means a shallower decline).

Fewer losing trades in absolute numbers can simply reflect fewer entries. Compare losing trades as a proportion of completed signal trades. Missed rebound starts include delayed entries and do not imply the entire rebound was untraded. Rebound windows are defined from 4H green crosses, so zero missed starts for 4H alone is by construction.

The paired strategies test a specific higher-timeframe entry gate, with unchanged 4H exits; the standalone strategies use their own timeframe exits. They do not measure every possible way to combine timeframes or establish universal predictive superiority. Session-matched and initial-position sensitivity results above show how dependent the findings are on those assumptions.

## Definitions and limitations

- Standalone strategies enter when their last completed 4H, 8H or daily WT is bullish while in cash. Pairs require bullish 4H AND last completed higher-timeframe WT bullish. If the higher timeframe confirms later while 4H remains bullish, entry is then allowed.
- Standalone strategies sell on a new confirmed bearish crossover of their own timeframe. Pairs sell on a confirmed 4H bearish crossover; a higher-timeframe bearish turn alone does not trigger an exit.
- Decide at 4H close using only higher candles whose end timestamp is at or before that close; execute at the next available 4H open, never on the signal close.
- Apply identical friction to each buy and sell: 0%, 0.10%, or 0.25% per side. Initial inherited position and final open position are not forced-liquidated or charged entry/exit fees.
- Largest peak-to-trough portfolio decline measured at completed 4H closes, including initial capital. Does not capture intrabar drawdown.
- Operational proxy: completed signal-entry trades with a negative net round-trip return. Excludes the inherited initial position and still-open trades; report losses/count, not just number of losses.
- Subset of losing signal trades exited within four 4H bars of entry.
- For each 4H green cross with 20 subsequent bars available, label a rebound when close after those 20 bars is at least 5% above the next-bar open. Missed start: cash at that open. Completely missed: no held position during the entire window. Also report windows with nonpositive net strategy returns, and retain 2% and 10% threshold sensitivity. These labels never influence trades.
- Main daily WT uses Massive adjusted regular-session OHLC released conservatively at 16:00 ET. Existing 4H/8H bars use extended hours. A separate same-window test compares regular and extended daily aggregation.

- Retrospective 2026 comparison, not an untouched prospective holdout or proof of predictive advantage. No rule, threshold or WT parameter was selected by maximizing returns.
- The daily archive ends October 16 although intraday history reaches October 19. All variants stop October 16 for a common fully covered period.
- Daily regular-session and extended intraday histories are different session definitions; the shorter session-matched sensitivity isolates this issue.
- Extended-hours opens are idealized fills. Friction scenarios do not model varying spreads, market impact, liquidity, dividends, taxes or cash interest. SOXL leverage is embedded in its price series.
- Rebound windows can overlap and are descriptive event counts, not independent statistical trials. A missed start may be entered later; complete misses are shown separately.
- TradingView candle alignment and numerical equivalence remain unverified. Only fully completed stored bars are used.

Full execution, trade and equity ledgers for the primary 0.10% cases are retained in the adjacent JSON.
