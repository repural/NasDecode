# Decisions and documentation backlog

Reviewed: 2026-10-27. [Documentation index](README.md)

## Established decisions

- Project is NasDecode, repository repural/NasDecode and website nasdecode.com. NasCal is outside this scope.
- Keep source data, research, working snapshots and public replicas distinct.
- CNBC supplies main current/session observations; Massive adjusted history supports historical context and bar archive.
- Independent Yahoo cash/futures display is source-labelled and potentially delayed.
- Preserve the original six-stock earnings AVWAP basket for comparison while broadening verified coverage.
- Direction, consolidation vulnerability, general entry quality, SOXL timing and research regimes answer different questions.
- Frozen model specifications must not be adjusted after inspecting their validation results.
- Missing/unverified/stale observations must be visible; do not substitute arbitrary constituents.
- Keep the selected minimalist black UI and separate section views.
- All maintained documentation is centralized in Docs; historical references are retained in Docs/Archive.

## Open implementation/documentation issues

| Item | Evidence / required follow-up |
|---|---|
| Constituent consistency | Live SEMI_BREADTH, historical archive, Phase3 and AVWAP universes differ; document dated evidence and reconcile through a separate implementation change |
| Full-SOX earnings AVWAP | Verify earnings release anchors and actual covered denominator before declaring complete |
| Four-session versus pre-market-only tasking | Repository supports four research slots; chat automation instructions may change independently. Inspect actual task configuration when operating it; do not infer from publisher YAML |
| Legacy/unified narrative authority | session-briefs publisher and premarket-brief compatibility bridge coexist; define migration/retirement before removing either |
| Open Watch freshness | Inspect retrieval status and newest event, not only file update time; Tavily-disabled periods require explicit failure/coverage interpretation |
| Requested Open Watch cadence | Earlier request15-minute market-hours/hourly closed differs from repository30-minute/hourly regional schedule |
| WaveTrend reliability | Audit validation failure, collection completion, reconciliation, generated/public timestamps and TradingView equivalence |
| Research branch integration | MU/GOOGL comparisons must retain their frozen designs and data when intentionally merged |
| Documentation-only triggers | refresh.yml ignores docs/** but not Docs/**; consider a separate reviewed trigger cleanup |
| Field-level catalog | Expand the logical data dictionary into schema/ownership validation when there is an implementation need |
| Repository exposure | Public source/history/Docs remain public; static deployment scope is not an access control |
| Source health / live QA | Current numerical/source and live-browser verification must be performed separately from this documentation change |

## Historical evidence

The [October23 handover](Archive/status-2026-10-23.md) contains dated repository/job observations, including failed searches and WaveTrend assertions. It is not a current October27 health report. Earlier audits, scoring notes and research proposals remain in Archive and are not discarded.

## Maintenance record

2026-10-27: consolidated architecture, data model/sources/refresh intervals, scoring, UI, operations, workflow reference and research guidance under Docs. Moved prior root/lowercase-docs references into Archive. Reduced the root README to project title and documentation link. No model, data, UI, schedule or NasCal changes are included.
