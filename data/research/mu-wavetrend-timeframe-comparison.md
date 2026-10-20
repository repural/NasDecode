# WaveTrend timeframe comparison

Research only. WT 10/21/4; identical next-4H-open execution and costs. No thresholds optimized.

## Main comparison

Common window: 2026-01-01 to 2026-10-16. Daily filter uses adjusted regular-session OHLC; 4H/8H retain the existing 04:00–20:00 ET session.

Initially invested at the last completed 2025 candle close, matching the earlier backtest. For pairs, higher timeframe gates entry only and exits use the lower-timeframe bearish crossover (4H or 8H). Standalone 8H/1D use their own WT entries and bearish-cross exits. Every variant executes on the next available 4H open and is marked on the same 4H closes.

### MU

| Strategy | Return, no costs | Return, 0.10%/side | Return, 0.25%/side | Max drawdown, 0.10% | Losing entry trades | Missed rebound starts | Fully missed rebounds |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4H alone | +164.84% | +137.47% | +101.60% | -28.54% | 29/54 | 0/19 | 0/19 |
| 8H alone | +110.92% | +99.03% | +82.42% | -39.99% | 13/28 | 15/19 | 0/19 |
| 1D alone | +196.59% | +188.69% | +177.21% | -23.21% | 5/13 | 12/19 | 2/19 |
| 4H + 8H | +75.57% | +60.61% | +40.50% | -32.43% | 25/44 | 15/19 | 0/19 |
| 4H + 1D | +91.04% | +77.59% | +59.14% | -17.41% | 17/36 | 12/19 | 2/19 |
| 8H + 1D | +91.34% | +83.65% | +72.68% | -19.03% | 9/20 | 15/19 | 2/19 |

Buy-and-hold, before costs: +206.17%.

#### Start-in-cash sensitivity (0.10% per side)

| Strategy | Return | Max drawdown | Executions |
|---|---:|---:|---:|
| 4H alone | +121.09% | -28.54% | 110 |
| 8H alone | +85.30% | -39.99% | 59 |
| 1D alone | +180.32% | -23.21% | 28 |
| 4H + 8H | +49.53% | -32.43% | 90 |
| 4H + 1D | +65.34% | -17.41% | 74 |
| 8H + 1D | +70.99% | -19.03% | 42 |

#### Session sensitivity: 2026-03-20 to 2026-10-16

Same shorter period for every row. Fully warmed daily bars; extended daily is built from four complete 4H bars.

| Strategy | Daily session | Return, 0.10%/side | Max drawdown |
|---|---|---:|---:|
| 4H alone | — | +60.17% | -28.54% |
| 8H alone | — | +25.02% | -39.99% |
| 1D alone | Regular | +107.99% | -23.21% |
| 4H + 8H | — | +3.55% | -32.43% |
| 4H + 1D | Regular | +13.75% | -26.73% |
| 8H + 1D | Regular | +26.57% | -29.89% |
| 1D alone | Extended | +95.06% | -17.51% |
| 4H + 1D | Extended | +13.94% | -26.73% |
| 8H + 1D | Extended | +18.83% | -29.89% |

## Interpretation

MU: 1D alone has the highest main-test net return at 0.10% per side. The best pair by return is 8H + 1D. Cost-scenario winners: zeroCosts: 1D alone, cost10bps: 1D alone, cost25bps: 1D alone. Starting in cash, the winner is 1D alone.

MU daily-filter trade-off versus 4H alone: -59.88 percentage points of return and +11.13 points of signed maximum drawdown (a positive drawdown difference means a shallower decline).

Fewer losing trades in absolute numbers can simply reflect fewer entries. Compare losing trades as a proportion of completed signal trades. Missed rebound starts include delayed entries and do not imply the entire rebound was untraded. Rebound windows are defined from 4H green crosses, so zero missed starts for 4H alone is by construction.

The paired strategies test a specific higher-timeframe entry gate, with lower-timeframe bearish-cross exits; the standalone strategies use their own timeframe exits. They do not measure every possible way to combine timeframes or establish universal predictive superiority. Session-matched and initial-position sensitivity results above show how dependent the findings are on those assumptions.

## Definitions and limitations

- Standalone strategies enter when their last completed 4H, 8H or daily WT is bullish while in cash. Pairs require bullish lower-timeframe WT (4H or 8H) AND last completed higher-timeframe WT bullish. If the higher timeframe confirms later while the lower timeframe remains bullish, entry is then allowed.
- Standalone strategies sell on a new confirmed bearish crossover of their own timeframe. Pairs sell on a confirmed lower-timeframe bearish crossover (4H for 4H pairs; 8H for 8H + 1D); a higher-timeframe bearish turn alone does not trigger an exit.
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
- Extended-hours opens are idealized fills. Friction scenarios do not model varying spreads, market impact, liquidity, dividends, taxes or cash interest. Leveraged ETF leverage, where applicable, is embedded in its price series.
- Rebound windows can overlap and are descriptive event counts, not independent statistical trials. A missed start may be entered later; complete misses are shown separately.
- TradingView candle alignment and numerical equivalence remain unverified. Only fully completed stored bars are used.
- MU warm-up history omits the 04:00–08:00 ET candle on December 8, 2025 under the existing end-of-bucket rule. No candle is synthesized. All 2026 evaluation sessions have complete 4H/8H bucket coverage; sparse underlying five-minute intervals and holiday warm-up sessions are disclosed in mu-wavetrend-coverage.json.

Full execution, trade and equity ledgers for the primary 0.10% cases are retained in the adjacent JSON.
