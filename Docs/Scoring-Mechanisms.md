# Scoring mechanisms

Reviewed: 2026-10-27 against main `d59d76f`. [Documentation index](README.md)

This is the implementation reference for engineering. Public dashboard explanations should explain meaning, evidence and freshness without reproducing scoring recipes. These documents remain visible because the GitHub repository is public.

## Distinct questions and current versions

| Output | Scale / version | Question | Owner |
|---|---|---|---|
| Nasdaq Score | -100..100; raw factor model plus market-response layer | Is the directional environment supportive or restrictive? | refresh.py → apply_market_response.py → refine_scores.py |
| Semiconductor Leadership | 0..100 | Is SOX leadership confirmed by ETFs and participation? | refresh.py / live_confirmation.py |
| Internal Confirmation | 0..100 | Do internals confirm the tape? | live_confirmation.py |
| Consolidation Risk | 0..100; v4 | How vulnerable is the next 1–3 sessions to a fade/reset? | refine_scores.py |
| Opportunity | 0..100; v5 | How attractive is new general Nasdaq long exposure? | refine_scores.py |
| SOXL Buy Score | 0..100; v3.3 | How attractive is a tactical SOXL entry over 1–5 sessions? | refine_scores.py |
| Directional Engine | Frozen v3.0 states | Which historically defined setup is present? | build_directional_engine_v3.py |
| Resilience | Shadow score | Is semiconductor strength durable relative to macro expectations? | build_resilience_model.py / build_resilience_engine.py |
| Context / SOX shadow research | Separate research versions | Does continuous context improve chronological baselines? | Dedicated research scripts |

Opportunity's “Directional edge” component is a transform of the published Nasdaq Score; it is not the frozen v3 classifier or a validated probability.

## Shared calculation conventions

Usable components are usually renormalized by available weights. Individual implementations also contain neutral/default behavior for missing data; do not describe this as universal exclusion. Clip component scales, retain coverage and preserve raw versus final values. Scores are not expected returns, win probabilities or position-sizing rules.

RSI14 and ATR14 use stored historical calculations; stochastic daily 9/6 is displayed but not scored. S5FI without verification has zero directional freshness weight.

## Nasdaq factor aggregation

For each factor, effective weight = impact weight × freshness × regime multiplier. Impact weights are Very High 4, High 3, Medium 2, Low 1. Freshness weights are 1 normally, 0.70 previous close, 0.35 stale/research/official lag, 0.20 awaiting/insufficient. Research-background inputs are capped at 0.35.

Within each correlation bucket compute weighted mean strength, then cap its contribution weight:

| Bucket | Cap |
|---|---:|
| Rates / Macro | 9 |
| Leadership | 9 |
| Breadth | 6 |
| Volatility / Positioning | 7 |
| Event Risk | 4 |
| Other | 4 |

Raw score = round(100 × sum(bucket strength × capped weight) / sum(capped weight)).
Strength is bounded -1..1. Rates/macro receives 1.25× sensitivity at 10Y ≥4.85%; volatility/positioning 1.20× at VXN ≥22; high-impact leadership 1.15×.

Transforms include yield level/velocity, Fed policy score, SOX-relative performance, breadth, VXN/VIX regime/moves, inverse oil moves, put/call levels/trend, and the decaying verified macro impulse. Unverified S5FI is explicitly excluded. Exact factor transforms are in [refresh.py](../scripts/refresh.py), continuous_factor and bucket aggregation.

Confidence = 60% coverage/freshness + 40% bucket agreement. It is a model evidence measure, not prediction calibration.

Published score uses effectiveScore if available, otherwise rawScore. Consolidation risk is not subtracted. Labels: ≥45 Strong Positive; ≥15 Cautiously Positive; >-15 Mixed; >-45 Cautiously Negative; otherwise Strong Negative.

## Market-response adjustment

[apply_market_response.py](../scripts/apply_market_response.py) only attenuates Rates / Macro; it never flips that bucket's sign. Negative macro with strong internals is constraint absorption; positive macro with weak internals is support rejection.

Activation requires macro magnitude ≥0.15, response evidence ≥0.60 and 15 minutes persistence. Continuity resets across trading days or observation gaps over 12 minutes. Active attenuation ranges from 25% to at most 50%, scaled by evidence. Retain raw/effective macro and Nasdaq values and candidate timestamps.

## Semiconductor and internal confirmation

The live pass requires all five core market readings and at least 10 same-session constituent quotes. Otherwise retain the existing basis and disclose coverage.

Live Semiconductor Leadership = 55% SOX relative score + 15% SOXX + 10% SMH + 20% semiconductor participation score. Relative-to-Nasdaq bins are ≥+0.50pp:100, ≥+0.20:75, >-0.20:50, >-0.50:25, otherwise 0. Participation is fraction outperforming QQQ, scored at 70/55/45/30% boundaries. SOX ≥+0.50pp with both ETF relative returns positive establishes a floor of 75.

Internal Confirmation = 35% breadth + 35% semiconductor leadership + 20% volatility + 10% mega-cap leadership. Discrete signals map positive/mixed/negative to 100/50/0.

The live breadth universe in source is a configured list; do not equate it automatically with current verified SOX membership.

## Consolidation Risk v4

Separate structural extension from evidence of a fade.

| Structural component | Weight |
|---|---:|
| QQQ vs 20DMA | 20% |
| QQQ RSI14 | 15% |
| QQQ 3D/5D acceleration | 10% |
| QQQ high proximity × extension | 15% |
| SOXX vs 20DMA | 15% |
| SOXX RSI14 | 10% |
| SOXX high proximity × extension | 15% |

QQQ distance scales +1..+6%, RSI60..80; SOXX distance +2..+10%, RSI60..85. Near-high proximity fades from 100 at the 20-day high to zero at ≥2% away and is multiplied by extension pressure. Merely being at a high is not inherently bearish.

Structural floor = 0.65 × structural extension.

Confirmation components: rejection 30%, breadth divergence 25%, leadership divergence 20%, volatility/rates stress 20%, event risk 5%. Giveback is observed regular-session return high-water mark minus current return.

Final risk = floor + (100 − floor) × confirmation/100.
Labels: <35 Low; 35–54 Moderate; 55–74 Elevated; ≥75 High. Retain component breakdown, coverageWeight, historyDays, floor and giveback.

## Opportunity v5

| Component | Weight |
|---|---:|
| Entry quality | 35% |
| Recovery confirmation | 20% |
| Directional edge | 20% |
| Macro timing | 15% |
| Catalyst asymmetry | 10% |

Direction = clip(50 + 1.25 × Nasdaq Score, 0,100).
Entry quality combines QQQ 20DMA location 25%, RSI 20%, five-day return 10%, high×extension 20%, SOXX extension 15%, and QQQ ATR regime 10%. RSI has a nonlinear reset/continuation curve. ATR uses its own history percentile and ATR14/ATR50 ratio, not raw dollar ATR. VXN/ATR interaction can add up to 8 or subtract 8 points.

Recovery combines internal confirmation and factor participation signals. Macro uses yield changes, Fed repricing and oil. Catalyst asymmetry starts neutral, adjusts for pending risk and observed positive/negative persistence, and clips to range.

Consolidation is a final gate, not a sixth weighted component:

- Weak direction (<40) and recovery (<50): cap 44.
- Moderate risk with entry <45: cap 59.
- Elevated risk with entry <50: cap 54.
- High risk: cap 44 without strong entry/recovery, otherwise 49.
- Pending high-impact catalyst: cap 64.

Labels: ≥75 Strong Long Opportunity; ≥60 Attractive; ≥45 Selective; ≥30 Wait for Confirmation; otherwise Poor Long Opportunity.

## SOXL Buy Score v3.3

| Component | Weight |
|---|---:|
| Semiconductor trend | 30% |
| SOXL entry quality | 25% |
| Market confirmation | 15% |
| Volatility / leverage safety | 15% |
| Rates / macro | 10% |
| Catalyst asymmetry | 5% |

These are distinct from general Opportunity weights.

Semiconductor trend mixes SOXX technical trend 30%, SOX relative strength 25%, SOXX relative strength 15%, SMH relative strength 10%, breadth 20%. SOXX technical trend uses 20DMA distance 30%, five-day momentum 25%, RSI 25%, directional ADX/DMI 20%.

SOXL entry quality uses 20DMA distance 30%, five-day return 20%, RSI20%, distance from 20-day high20%, intraday giveback10%. RSI favors healthy bullish momentum before overheating. When semiconductor trend ≥70 and SOX/relative confirmation is positive, a controlled pullback is rewarded, peaking around 12% below the recent high; deeper drawdowns reduce the reward. Without confirmed strength the conservative curve applies.

Leverage safety includes consolidation safety35%, VXN signal25%, VXN change15%, SOXL ATR regime25%. Stoch9/6 is observational only.

Apply continuous extension penalty above 8% over 20DMA, up to35 points, with partial relief in strongly confirmed semiconductor regimes. Add a separate RSI×extension overheating penalty, then enforce regime/event caps:

- Semiconductor trend <40 →45.
- At least two semiconductor relative readings, all negative →50.
- Consolidation risk ≥75 →45.
- VXN daily increase >8% and 10Y change >5bp →45.
- Pending high-impact catalyst →64.

Retain rawScore, preGateScore, final score, gates, indicatorSnapshot, entry and trend components. Labels: ≥85 Exceptional Tactical Entry; ≥70 Attractive; ≥55 Selective/Starter; ≥40 Wait; ≥25 Poor Entry; otherwise Avoid Long.

## Research mechanisms and implementation authority

Frozen v3 classification priority: Uptrend Pullback, Washout/Rebound, Continuation, Neutral/Other. Exact frozen specification and SHA are retained by the classifier. Thresholds must not be retuned after holdout inspection.

Resilience combines residual strength60%, persistence15%, internal confirmation25%; residual horizons1/3/5/10 use15/25/35/25%. It is structural shadow research, not a proven short-term entry predictor. Context and Phase3 research remain separate from production weights.

For detailed historical curves and earlier reasoning, see [preserved scoring reference](Archive/scores.txt) and [engine evolution](Archive/ENGINE_EVOLUTION_AND_VALIDATION.txt). Those files are historical references; current scripts and this version table take precedence. Update this file alongside any score implementation change.
