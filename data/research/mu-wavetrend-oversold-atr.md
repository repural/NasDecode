# MU: oversold entries and ATR exits

Fixed comparison: January 2–October 16, 2026; identical frozen adjusted Massive 4H input. Primary results use $10,000 inherited stock at the last 2025 close, next available 4H-open execution, 0.10% costs per buy/sell, and end-period marking without forced liquidation.

## Primary comparison

| Strategy | Net return | Final value | Max close drawdown | Win rate | Wins/closed | Profit factor | Missed/delayed rebound starts | ATR exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Original 4H WT | +137.47% | $23,747.37 | -28.54% | 46.30% | 25/54 | 1.64 | 0/19 | 0 |
| Oversold entry only | +12.63% | $11,263.25 | -17.42% | 40.00% | 4/10 | 1.10 | 14/19 | 0 |
| ATR exit only | +121.42% | $22,142.26 | -28.54% | 44.44% | 24/54 | 1.53 | 0/19 | 3 |
| Oversold entry + ATR exit | +13.22% | $11,322.07 | -17.42% | 40.00% | 4/10 | 1.10 | 14/19 | 1 |
| Buy and hold | +206.17% | $30,616.90 | -40.40% | — | — | — | — | — |

Buy-and-hold uses the identical inherited starting shares and ending mark. It makes no trades and is not sold at the end, so no transaction costs apply. Win rate is not applicable.

## Sensitivities

| Strategy | No costs | 0.25%/side | Full period starting cash | Jan–Jun return | Jul–Oct return | Exposure |
|---|---:|---:|---:|---:|---:|---:|
| Original 4H WT | +164.84% | +101.60% | +121.09% | +163.37% | -9.83% | 48.74% |
| Oversold entry only | +15.02% | +9.13% | +3.34% | +18.20% | -7.67% | 11.93% |
| ATR exit only | +146.94% | +87.97% | +106.15% | +151.21% | -11.86% | 48.37% |
| Oversold entry + ATR exit | +15.62% | +9.70% | +3.34% | +18.81% | -7.67% | 11.81% |

## Final open positions

- Original 4H WT: cash.
- Oversold entry only: cash.
- ATR exit only: cash.
- Oversold entry + ATR exit: cash.

## Frozen rules

- Original: enter while completed WT1 > WT2; exit on any confirmed red crossover.
- Oversold entry: enter only on a new confirmed green cross with WT1 ≤ -45; exit on any confirmed red crossover.
- ATR exit: original entries; exit on any red cross OR completed-close ATR trailing breach.
- Combined: oversold entries; exit on any red cross OR completed-close ATR trailing breach.

## Definitions and limitations

- The entry-only strategy sells on every new red cross, regardless of WT level. It does not wait for an overbought red cross. The combined strategy sells on a red cross OR an ATR breach.
- ATR(14) uses Wilder smoothing. Trail = max(previous trail, highest completed high since entry - 2 × current ATR14). Trigger only when a completed close is below the trail; fill at the next open, never at the stop price. After ATR exit, wait for a new green cross; oversold variants also require that new cross to qualify at WT1 ≤ -45.
- Initial inherited stock is identical in every primary row and can be held before the first qualifying entry. Start-in-cash sensitivity removes this inherited holding.
- Win rate and profit factor use completed signal-entry round trips, including costs. Inherited and still-open positions are excluded from trade statistics, but their gains/losses are included in portfolio return and drawdown.
- Maximum drawdown is measured at completed 4H closes, not intrabar lows. Extended-hours fills are idealized and fixed costs do not model varying spreads/impact. No dividends, taxes or cash interest.
- Rebounds use original 4H green crosses followed by at least +5% from next open to close 20 bars later. Windows may overlap; zero original-baseline missed starts is by construction. Missed starts include later entries.
- Half-year runs initialize independently with inherited stock; their returns do not concatenate. These are exploratory diagnostics, not holdouts.
- The -45 entry threshold and 2×ATR14 exit were chosen before this run, based on earlier analysis of this same 2026 period. No grid search was performed. These results are not independent validation; all rules require testing on later untouched data.
- Buy-and-hold on the inherited-position convention returned +206.17% before costs. TradingView candle/numerical equivalence remains unverified.
- The adjacent JSON contains the frozen design, source/code hashes, cost scenarios, full primary ledgers, cash-start and half-year diagnostics.

MU data coverage: all 2026 evaluation sessions have complete 4H/8H bucket coverage. The December 8, 2025 04:00–08:00 ET warm-up bucket is excluded by the existing collector rule; it is not synthesized. Sparse five-minute source intervals and short warm-up sessions are documented in mu-wavetrend-coverage.json.
