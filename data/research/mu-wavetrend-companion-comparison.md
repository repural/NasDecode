# 4H WaveTrend companion experiments

Period: 2026-01-01–2026-10-16. Frozen single-addition rules; WT 10/21/4.

Research only. All fills use the next available 4H open. Main results include 0.10% friction per buy/sell. The identical inherited $10,000 position starts at the last completed 2025 close. No live score, signal or chart behavior is changed.

## Main results

### MU

| Strategy | Net return | Max close drawdown | Win rate | Wins / closed trades | Profit factor | Missed/delayed rebound starts |
|---|---:|---:|---:|---:|---:|---:|
| 4H WT alone | +137.47% | -28.54% | 46.30% | 25/54 | 1.64 | 0/19 |
| WT + EMA20 | +96.73% | -28.37% | 47.92% | 23/48 | 1.58 | 9/19 |
| WT + DMI14 | +108.84% | -21.85% | 48.84% | 21/43 | 1.82 | 8/19 |
| WT + DMI14 + rising ADX14 | +95.90% | -19.72% | 51.85% | 14/27 | 2.42 | 16/19 |
| WT + ATR14 trailing exit | +121.42% | -28.54% | 44.44% | 24/54 | 1.53 | 0/19 |
| WT + price confirmation | +122.51% | -19.99% | 56.25% | 18/32 | 2.38 | 18/19 |

#### Payoff, costs and turnover

| Strategy | Average winner | Average loser | Mean closed-trade return | Executions | Return, no costs | Return, 0.25%/side |
|---|---:|---:|---:|---:|---:|---:|
| 4H WT alone | +7.69% | -3.42% | +1.72% | 109 | +164.84% | +101.60% |
| WT + EMA20 | +6.56% | -3.25% | +1.45% | 97 | +116.78% | +70.05% |
| WT + DMI14 | +6.78% | -3.05% | +1.75% | 87 | +127.83% | +83.25% |
| WT + DMI14 + rising ADX14 | +7.35% | -2.83% | +2.45% | 55 | +106.98% | +80.36% |
| WT + ATR14 trailing exit | +8.00% | -3.55% | +1.58% | 109 | +146.94% | +87.97% |
| WT + price confirmation | +6.71% | -2.93% | +2.49% | 65 | +137.46% | +101.81% |

#### Period and initial-position diagnostics (0.10%/side)

| Strategy | Jan–Jun return | Jan–Jun win rate | Jul–Oct return | Jul–Oct win rate | Full period starting in cash |
|---|---:|---:|---:|---:|---:|
| 4H WT alone | +163.37% | 53.12% | -9.83% | 38.1% | +121.09% |
| WT + EMA20 | +127.46% | 58.62% | -13.51% | 33.33% | +83.16% |
| WT + DMI14 | +116.64% | 57.14% | -6.60% | 33.33% | +94.43% |
| WT + DMI14 + rising ADX14 | +91.27% | 57.14% | -0.77% | 33.33% | +82.38% |
| WT + ATR14 trailing exit | +151.21% | 53.12% | -11.86% | 33.33% | +106.15% |
| WT + price confirmation | +127.70% | 73.68% | -5.32% | 30.77% | +101.63% |

Variants improving both main-period return and win rate: none.

## Frozen rules

- **4H WT alone:** Enter while completed 4H WT1 > WT2; exit on completed 4H bearish crossover.
- **WT + EMA20:** Baseline entry AND completed 4H close > EMA(close,20). Baseline WT exit.
- **WT + DMI14:** Baseline entry AND Wilder +DI(14) > -DI(14). Baseline WT exit.
- **WT + DMI14 + rising ADX14:** DMI14 entry condition AND ADX(14) > its previous completed 4H value. Baseline WT exit.
- **WT + ATR14 trailing exit:** Baseline entries. Sell at next 4H open after either WT red cross or close < trailing stop. Stop = max(previous stop, highest completed high since entry - 2 * ATR(14)). After an ATR exit wait for a new WT green cross before re-entry; no intrabar stop execution.
- **WT + price confirmation:** Baseline entry AND close strictly above the most recent WT green crossover candle high in the current bullish phase. Re-evaluate at each completed close; red cross cancels setup. Baseline WT exit.

## Interpretation and limitations

- All 2026 results are exploratory. The period has already been examined; the half-year diagnostics are not untouched holdouts. No claim of validated future improvement is made.
- Each addition is tested alone against the same baseline. DMI plus rising ADX is a predeclared directional-strength variant; there is no search over periods, thresholds or stacked winners.
- Entry gates are re-evaluated while WT remains bullish and can delay entries. Rejected setups may later enter if the gate turns favorable before WT turns bearish.
- The ATR test uses completed-close breaches and next-open fills, not idealized fills at the stop. Intrabar breaches are ignored. ATR exits require a new WT green cross before re-entry.
- Each subperiod is an independently initialized diagnostic with the same inherited-position convention; subperiod returns do not concatenate to the full-period result.
- Historic extended-hours opens are idealized fills. Costs are fixed friction scenarios, not a full liquidity/impact model. No cash interest, dividends or taxes are modeled.
- The source is the frozen adjusted Massive 4H archive used in the prior comparison. WT and companion indicator numerical equivalence to TradingView is not independently verified.
- MU warm-up history omits the 04:00–08:00 ET candle on December 8, 2025 under the existing end-of-bucket rule. No candle is synthesized. All 2026 evaluation sessions have complete 4H/8H bucket coverage; sparse underlying five-minute intervals and holiday warm-up sessions are disclosed in mu-wavetrend-coverage.json.

## Metric definitions

- Win rate = positive-net-return completed signal-entry round trips / all completed signal-entry round trips. Breakevens count in the denominator. Inherited initial and still-open positions are excluded from trade statistics but included in portfolio return and drawdown.
- Profit factor = sum of positive net dollar P&L / absolute sum of negative net dollar P&L over completed signal-entry trades. All entry/exit friction is included; no-loss denominator is reported as undefined, never fabricated.
- Average winner/loser and mean trade return are arithmetic net percentage returns on completed signal-entry trades. Position sizes vary as portfolio wealth compounds.
- Maximum drawdown uses completed 4H portfolio marks and can understate intrabar declines.
- Rebounds and missed starts retain the previous comparison definition: a 4H green cross followed by at least +5% over the next 20 bars. A cash position at the first executable open is a missed/delayed start. Windows may overlap; zero baseline misses is by construction.

The adjacent JSON contains the full primary 0.10% execution, closed-trade and equity ledgers, all three cost cases, the two subperiods and start-in-cash sensitivity.
