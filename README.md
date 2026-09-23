# NasBoard

NasBoard is a Nasdaq market-regime dashboard. It combines market observations into 15 underlying factors, two derived model outputs, and a daily narrative pre-market brief.

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

**Nasdaq Setup** is the weighted directional output of the underlying factors. It is a model output, not a 16th factor, so it is not counted again in the model.

**Consolidation Risk** measures short-term extension/pullback risk using inputs such as QQQ/SOX stretch, breadth, volatility, multi-day returns, moving-average extension, and RSI when enough history exists. It measures consolidation risk rather than market direction.

VXN is the primary volatility gauge because it is Nasdaq-specific; VIX is displayed and used as broad-market confirmation.

The nominal 10Y Treasury yield is the live directional rates factor. The 10Y real yield is supporting valuation context inside its explanation, not a separate factor, to avoid double-counting the same rates regime.

## Important files

- `scripts/refresh.py` — main quantitative data/model engine.
- `index.html` — dashboard presentation layer. It should render model output, not recreate model decisions in JavaScript.
- `data/dashboard.json` — generated working snapshot.
- `public/data/dashboard.json` — public snapshot deployed to the dashboard.
- `public/data/premarket.json` — daily narrative pre-market analysis.
- `data/history/` — stored observations/model states used for later historical analysis.
- `.github/workflows/refresh.yml` — scheduled/commit-triggered refresh and publishing workflow.
- `wrangler.jsonc` — Cloudflare static-asset deployment configuration.

## Refresh and deployment

GitHub Actions runs the quantitative refresh around the U.S. cash open using the `America/New_York` timezone so daylight-saving changes do not require manual UTC changes. A refresh writes the generated data, copies deployable files into `public/`, commits the snapshot/history, and pushes it to `main`.

Cloudflare is connected to the private GitHub repository and deploys only `./public`. Python source, workflows, private history, and other repository internals are therefore not part of the public static site.

The workflow deliberately regenerates data after a concurrent push instead of rebasing generated JSON/history files. Generated market snapshots are poor merge candidates and previously caused rebase conflicts.

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
