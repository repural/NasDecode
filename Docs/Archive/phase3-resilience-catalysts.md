# NasDecode — Phase 3: Resilience and catalyst feature engineering

Status: research specification; production directional v3 remains frozen.

## Objective
Explain and eventually predict when SOX leadership persists despite adverse rates, volatility, and energy conditions. Capture catalyst anticipation, surprise, and follow-through without introducing lookahead bias.

## Work sequence
1. Audit the 443-row regime-context dataset and resilience-engine history. Map available SOX relative strength, semiconductor breadth, persistence, drawdown, and adverse-macro response fields. Preserve missing values.
2. Build point-in-time resilience features at completed close T: SOX vs QQQ 5D/10D relative return, rolling leadership persistence, semiconductor breadth (when historically observed), adverse macro flags, and realized recovery after prior shocks. Avoid using any forward outcome as an input.
3. Inventory catalyst history from market-watch-events.json, earnings archives, and scheduled macro events. Record eventTime, firstReported, source, instrument relevance, direction, surprise when known, and market-session cutoff. Do not assign pre-announcement features based on later knowledge.
4. Add research-only daily catalyst features: known upcoming event within 1/3/7 sessions, material confirmed news in last 1/3 sessions, positive/negative directional exposure, and observed post-event follow-through. Unknown historical timestamps remain null.
5. Evaluate incremental predictive value with chronological walk-forward validation and comparisons to frozen directional v3 and simple baselines. Use ablations for resilience, catalyst, and oil groups; report coverage, calibration, overlapping horizons, and uncertainty.
6. Only after evidence of reliable improvement, propose shadow integration; production score changes require explicit approval.

## Guardrails
- Do not modify NasCal.
- Do not retune or replace frozen directional v3.
- No reconstructed hype scores based on hindsight; missing event coverage must be visible.
- Research artifacts belong under data/history, and methodology scripts under scripts.
- Avoid describing descriptive correlations as causal or validated predictive edge.
