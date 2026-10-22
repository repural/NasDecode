# SOXL: oversold entries and ATR exits

Fixed comparison: January 2–October 16, 2026; identical frozen adjusted Massive 4H input. Primary results use $10,000 inherited stock at the last 2025 close, next available 4H-open execution, 0.10% costs per buy/sell, and end-period marking without forced liquidation.

## Primary comparison

| Strategy | Net return | Final value | Max close drawdown | Win rate | Wins/closed | Profit factor | Missed/delayed rebound starts | ATR exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Original 4H WT | +127.08% | $22,708.18 | -53.49% | 47.17% | 25/53 | 1.20 | 0/25 | 0 |
| Oversold entry only | +12.32% | $11,231.73 | -27.03% | 37.50% | 3/8 | 0.75 | 21/25 | 0 |
| ATR exit only | +35.19% | $13,519.46 | -53.49% | 45.28% | 24/53 | 1.04 | 0/25 | 2 |
| Oversold entry + ATR exit | +12.32% | $11,231.73 | -27.03% | 37.50% | 3/8 | 0.75 | 21/25 | 0 |

## Sensitivities

| Strategy | No costs | 0.25%/side | Full period starting cash | Jan–Jun return | Jul–Oct return | Exposure |
|---|---:|---:|---:|---:|---:|---:|
| Original 4H WT | +152.74% | +93.36% | +106.17% | +266.34% | -38.01% | 51.76% |
| Oversold entry only | +14.24% | +9.48% | -8.97% | +18.64% | -20.57% | 9.92% |
| ATR exit only | +50.47% | +15.12% | +22.74% | +118.10% | -38.01% | 48.62% |
| Oversold entry + ATR exit | +14.24% | +9.48% | -8.97% | +18.64% | -20.57% | 9.92% |

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
- Buy-and-hold on the inherited-position convention returned +123.69% before costs. TradingView candle/numerical equivalence remains unverified.
- The adjacent JSON contains the frozen design, source/code hashes, cost scenarios, full primary ledgers, cash-start and half-year diagnostics.
