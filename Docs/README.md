# NasDecode documentation

Reviewed: 2026-10-27. Source baseline: `d59d76f36a0a5c529fd75412680a4d8371c70d99` on `main`.
Scope: `repural/NasDecode`; NasCal is excluded.

| Document | Contents |
|---|---|
| [Architecture](Architecture.md) | Components, processing order, publication, deployment boundaries |
| [Data model](Data-Model.md) | Sources, schemas, grain, lineage, ownership, refresh intervals |
| [Scoring mechanisms](Scoring-Mechanisms.md) | Implemented score versions, components, weights, gates, interpretation |
| [UI architecture](UI-Architecture.md) | Rendering, routes, feeds, polling, styling, failure states |
| [Operations](Operations.md) | Refresh/publication runbooks, failure diagnosis, credentials, safe changes |
| [Workflow reference](Workflow-Reference.md) | Exact configured schedules and workflow entry points |
| [Validation and research](Validation-and-Research.md) | Model lifecycle, leakage controls, research vs production |
| [Decisions and backlog](Decisions-and-Backlog.md) | Established decisions, known gaps, next documentation work |
| [Archive](Archive/README.md) | Preserved earlier documents and dated audit |

## Reading and maintenance rules

The executable implementation and workflow YAML determine actual behavior. These documents describe the reviewed baseline; dates and observed failures are not permanent health claims. A configured schedule is not a guaranteed successful update.

Keep source timestamp, retrieval timestamp, generation timestamp, commit, publication, and live-site verification separate. Research outputs are not automatically production inputs. Unknown or stale data must retain its status.

All maintained project documentation belongs in `Docs/`. Keep the root README minimal. Numeric research datasets remain under `data/` and deployment assets remain under `public/`.

This repository is public. Moving a document into Docs does not restrict GitHub access. Cloudflare serving only public assets is a separate boundary.

When changing a source, schema, score, workflow schedule, or UI consumer, update its document in the same change. Retain prior protocols and dated audits in Archive rather than silently rewriting their conclusions.
