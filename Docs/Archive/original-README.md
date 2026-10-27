# NasDecode

NasDecode is a Nasdaq market-regime dashboard. It combines market observations into core directional factors, selective Earnings AVWAP leadership, derived model outputs, and scheduled narrative market analysis checkpoints.

## Architecture

```text
Market / official data sources
          |
          v
scripts/refresh.py
  - normalizes observations
  - calculates factor states
  - derives Signal / Trend / Current Impact
  - builds scorecards and explanations
  - calculates Nasdaq Setup
          |
          v
scripts/live_confirmation.py
scripts/refine_scores.py
  - current-session confirmation
  - Consolidation Risk v3
  - Opportunity Score v3
          |
          +--> data/dashboard.json
          +--> data/history/
          |
          v
public/data/dashboard.json
          |
          v
public/index.html --> Cloudflare Worker static assets --> NasDecode
```

The pre-market researched brief remains a separate narrative path through `data/premarket.json` / `public/data/premarket.json`.

During the U.S. cash session NasDecode also stores three deterministic analysis checkpoints generated from the same refined market state:

```text
10:30 ET  Early Market Analysis
13:00 ET  Mid-Market Analysis
15:30 ET  Near-Close Analysis
16:15 ET  Canonical verified close snapshot
```

The checkpoint narratives are stored privately in `data/history/session-analyses.json` and copied to `public/data/session-analyses.json` for the current dashboard timeline. This creates a historical sequence of opening thesis → midday evolution → near-close persistence → final outcome for later calibration.

## How to read the model

**Signal** describes direction: supportive for Nasdaq, a headwind, or mixed.

**Trend** describes how the factor is changing. A factor can have a supportive level while its short-term trend is deteriorating, or vice versa.

**Current Impact** estimates how much the factor matters *right now* based on the latest move, magnitude, event proximity, and freshness. It is separate from Signal.

**Nasdaq Score** summarizes the current directional market backdrop.

**Consolidation Risk v3** measures 1–3 session vulnerability to a fade or sideways reset from extension, intraday rejection, breadth/leadership divergence and cross-asset stress. It does not mechanically alter Nasdaq Score.

**Opportunity Score v3** measures current long-entry quality from directional edge, entry quality, recovery confirmation, macro timing and catalyst asymmetry. It is not a next-session return forecast.

VXN is the primary volatility gauge because it is Nasdaq-specific; VIX is displayed and used as broad-market confirmation.

The nominal 10Y Treasury yield is the live directional rates factor. The 10Y real yield is supporting valuation context inside its explanation, not a separate factor, to avoid double-counting the same rates regime.

## Important files

- `scripts/refresh.py` — main quantitative data/model engine.
- `scripts/live_confirmation.py` — live current-session semiconductor/internal confirmation.
- `scripts/refine_scores.py` — v3 secondary-score refinement.
- `scripts/capture_session_analysis.py` — scheduled Early/Mid/Near-Close analysis snapshots.
- `scripts/inject_session_analysis_ui.py` — injects the session timeline renderer into deployed `public/index.html`.
- `public/session-analysis.js` — presentation-only renderer for the intraday analysis timeline.
- `index.html` — dashboard presentation source.
- `data/dashboard.json` — generated working snapshot.
- `data/history/session-analyses.json` — private checkpoint history.
- `public/data/session-analyses.json` — deployable checkpoint timeline data.
- `public/data/premarket.json` — daily narrative pre-market analysis.
- `.github/workflows/refresh.yml` — scheduled/commit-triggered refresh and publishing workflow.
- `wrangler.jsonc` — Cloudflare static-asset deployment configuration.

## Refresh and deployment

GitHub Actions uses `America/New_York` schedules for U.S. market checkpoints so daylight-saving changes do not require manual UTC changes. The workflow refreshes market data, applies live confirmation and v3 scores, captures a session analysis only when an analysis checkpoint schedule triggered the run, then publishes deployable files under `public/`.

Cloudflare is connected to the private GitHub repository and deploys only `./public`. Python source, workflows, private history, and other repository internals are therefore not part of the public static site.

The workflow deliberately regenerates data after a concurrent push instead of rebasing generated JSON/history files. Generated market snapshots are poor merge candidates and previously caused rebase conflicts.

## Economic / inflation data semantics

`Economic / inflation data` is a macro-surprise factor, not an event-calendar factor. It should move only when NasDecode has a verified release with both an actual value and a market-consensus value. Upcoming releases and event proximity belong in the pre-market/event-risk layer and do not by themselves create a positive or negative signal. If a verified surprise is unavailable, the factor fails closed as mixed.

## Daily validation history

Each trading-day record in `data/history/daily.json` keeps the raw observations plus a structured validation block for model calibration. The validation data includes model state, numeric market context, same-day returns, completeness information and forward-return targets that remain null until future sessions exist.

Raw `market`, `sessionLevels`, `factors`, `fedExpectations` and `earningsAvwap` fields remain in the record so future research is not limited to the current validation schema.

## Massive historical enrichment

Massive is an optional historical-data layer. The refresh engine reads `MASSIVE_API_KEY` from the GitHub Actions secret environment; the key is never written to JSON, source code, or Cloudflare assets. CNBC remains the current/session quote source while Massive daily bars add objective historical context. Missing credentials, entitlement limits, rate limits, or API failures fail closed and do not stop the main dashboard refresh.

## Earnings Anchored VWAP

NasDecode maintains a selective Earnings AVWAP leadership signal for important technology and semiconductor shares. It evaluates how leadership is behaving around recent earnings reference levels and incorporates that information into directional and extension analysis. Detailed construction, weighting, thresholds, and basket methodology are intentionally kept private.

## Data policy

NasDecode prefers official/free sources and explicitly records freshness. Missing, delayed, or unavailable inputs should remain marked stale/limited rather than being invented or silently substituted with old observations.

Browser code is presentation-only where practical. Signal rules, factor interpretation, model calculations, and scorecard decisions belong in the Python refresh engine so the public JavaScript does not become a second model implementation.
