# NasBoard

NasBoard is a Nasdaq market-regime dashboard. It combines market observations into core directional factors, selective Earnings AVWAP leadership, two derived model outputs, and a daily narrative pre-market brief.

## Architecture

```text
Market / official data sources
          |
          v
scripts/refresh.py
  - normalizes observations
  - calculates 15 factor states
  - derives Signal / Trend / Current Impact
  - builds scorecards and explanations
  - calculates Nasdaq Setup
  - calculates Consolidation Risk
          |
          +--> data/dashboard.json       (working/generated snapshot)
          +--> data/history/             (private model history)
          |
          v
public/data/dashboard.json
          |
          v
public/index.html --> Cloudflare Worker static assets --> NasBoard
```

The daily qualitative brief is a separate path:

```text
06:00 Europe/Istanbul scheduled research
          |
          v
Fresh public-market/news research
          |
          v
public/data/premarket.json
          |
          v
Pre-Market Analysis panel in NasBoard
```

This separation is intentional: the quantitative factor engine is deterministic Python, while the pre-market brief is a researched narrative about what matters that particular morning.

## How to read the model

**Signal** describes direction: supportive for Nasdaq, a headwind, or mixed.

**Trend** describes how the factor is changing. A factor can have a supportive level while its short-term trend is deteriorating, or vice versa.

**Current Impact** estimates how much the factor matters *right now* based on the latest move, magnitude, event proximity, and freshness. It is separate from Signal.

**Nasdaq Setup** summarizes the current directional market backdrop using NasBoard's proprietary model. It incorporates both supporting/headwind conditions and the current degree of market extension.

**Consolidation Risk** estimates the near-term risk of a pause, pullback, or consolidation using NasBoard's proprietary market model. Missing inputs reduce data coverage rather than being guessed.

VXN is the primary volatility gauge because it is Nasdaq-specific; VIX is displayed and used as broad-market confirmation.

The nominal 10Y Treasury yield is the live directional rates factor. The 10Y real yield is supporting valuation context inside its explanation, not a separate factor, to avoid double-counting the same rates regime.

## Important files

- `scripts/refresh.py` — main quantitative data/model engine.
- `index.html` — dashboard presentation layer. It should render model output, not recreate model decisions in JavaScript.
- `data/dashboard.json` — generated working snapshot.
- `data/earnings_avwap_watchlist.json` — selective earnings anchors for the AVWAP leadership basket.
- `public/data/dashboard.json` — public snapshot deployed to the dashboard.
- `public/data/premarket.json` — daily narrative pre-market analysis.
- `data/history/` — stored observations/model states used for later historical analysis.
- `.github/workflows/refresh.yml` — scheduled/commit-triggered refresh and publishing workflow.
- `wrangler.jsonc` — Cloudflare static-asset deployment configuration.

## Refresh and deployment

GitHub Actions runs the quantitative refresh around the U.S. cash open using the `America/New_York` timezone so daylight-saving changes do not require manual UTC changes. A refresh writes the generated data, copies deployable files into `public/`, commits the snapshot/history, and pushes it to `main`.

Cloudflare is connected to the private GitHub repository and deploys only `./public`. Python source, workflows, private history, and other repository internals are therefore not part of the public static site.

The workflow deliberately regenerates data after a concurrent push instead of rebasing generated JSON/history files. Generated market snapshots are poor merge candidates and previously caused rebase conflicts.


## Economic / inflation data semantics

`Economic / inflation data` is a macro-surprise factor, not an event-calendar factor. It should move only when NasBoard has a verified release with both an actual value and a market-consensus value. The factor compares actual versus consensus and applies a release-specific direction mapping; upcoming releases and event proximity belong in the pre-market/event-risk layer and do not by themselves create a positive or negative signal. If a verified surprise is unavailable, the factor fails closed as mixed.

## Massive historical enrichment

Massive is an optional historical-data layer. The refresh engine reads `MASSIVE_API_KEY` from the GitHub Actions secret environment; the key is never written to JSON, source code, or Cloudflare assets. CNBC remains the current/session quote source while Massive daily bars add objective historical context such as consecutive sessions, five-day returns, and moving-average distance. Missing credentials, entitlement limits, rate limits, or API failures fail closed and do not stop the main dashboard refresh.

The first integration uses QQQ plus SOXX as a liquid U.S.-listed semiconductor-history proxy. This historical proxy supplements—not replaces—the live Semiconductor Leadership factor, which continues to use the existing semiconductor basket versus QQQ.

## Earnings Anchored VWAP

NasBoard maintains a selective Earnings AVWAP leadership signal for important technology and semiconductor shares. It evaluates how leadership is behaving around recent earnings reference levels and incorporates that information into both directional and extension analysis. Detailed construction, weighting, thresholds, and basket methodology are intentionally kept private.

## Data policy

NasBoard prefers official/free sources and explicitly records freshness. Missing, delayed, or unavailable inputs should remain marked stale/limited rather than being invented or silently substituted with old observations.

Browser code is presentation-only where practical. Signal rules, factor interpretation, model calculations, and scorecard decisions belong in the Python refresh engine so the public JavaScript does not become a second model implementation.

## Development convention

New functions should include a concise docstring/comment explaining:

1. what the function does,
2. why it exists when the reason is not obvious,
3. important source/freshness assumptions, and
4. how failure or missing data is handled.

Comments should explain model intent and non-obvious decisions rather than restating individual lines of code. Changes to factor/model logic should also update this README when they alter the architecture or interpretation.
