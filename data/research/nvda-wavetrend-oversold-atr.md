# NVDA: oversold entries and ATR exits

Fixed comparison: January 2–October 16, 2026; identical frozen adjusted Massive 4H input. Primary results use $10,000 inherited stock at the last 2025 close, next available 4H-open execution, 0.10% costs per buy/sell, and end-period marking without forced liquidation.

## Primary comparison

| Strategy | Net return | Final value | Max close drawdown | Win rate | Wins/closed | Profit factor | Missed/delayed rebound starts | ATR exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Original 4H WT | +18.96% | $11,896.25 | -10.67% | 41.82% | 23/55 | 1.39 | 0/10 | 0 |
| Oversold entry only | +39.68% | $13,967.94 | -3.83% | 77.78% | 7/9 | 18.86 | 6/10 | 0 |
| ATR exit only | +26.88% | $12,688.28 | -9.11% | 43.64% | 24/55 | 1.56 | 0/10 | 6 |
| Oversold entry + ATR exit | +35.60% | $13,559.51 | -4.50% | 77.78% | 7/9 | 17.38 | 6/10 | 1 |

## Sensitivities

| Strategy | No costs | 0.25%/side | Full period starting cash | Jan–Jun return | Jul–Oct return | Exposure |
|---|---:|---:|---:|---:|---:|---:|
| Original 4H WT | +33.07% | +0.54% | +16.86% | +16.37% | +2.23% | 49.50% |
| Oversold entry only | +42.50% | +35.54% | +38.58% | +20.74% | +15.69% | 16.83% |
| ATR exit only | +41.93% | +7.23% | +24.64% | +21.99% | +4.01% | 47.61% |
| Oversold entry + ATR exit | +38.34% | +31.58% | +34.53% | +17.21% | +15.69% | 15.83% |

## Final open positions

- Original 4H WT: open since 2026-10-16T08:00:00-04:00; marked net return -1.64%.
- Oversold entry only: open since 2026-10-16T08:00:00-04:00; marked net return -1.64%.
- ATR exit only: open since 2026-10-16T08:00:00-04:00; marked net return -1.64%.
- Oversold entry + ATR exit: open since 2026-10-16T08:00:00-04:00; marked net return -1.64%.

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
- Buy-and-hold on the inherited-position convention returned +14.64% before costs. TradingView candle/numerical equivalence remains unverified.
- The adjacent JSON contains the frozen design, source/code hashes, cost scenarios, full primary ledgers, cash-start and half-year diagnostics.
