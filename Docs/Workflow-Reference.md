# Workflow reference

Reviewed: 2026-10-27 against main `d59d76f`. [Documentation index](README.md)

Cron expressions below are copied from the workflow files and interpreted in UTC. They are attempt schedules, not guaranteed refresh intervals. A workflow without cron is push/manual/dependency-driven; inspect its `on` block for exact filters. ET runtime gates can skip otherwise scheduled runs. ChatGPT task schedules are separate and are not configured here.

| Workflow | Configured cron (UTC) | Script entry points |
|---|---|---|
| [analyze-earnings-leadup.yml](../.github/workflows/analyze-earnings-leadup.yml) | No scheduled cron | analyze_earnings_leadup |
| [analyze-megacap-earnings.yml](../.github/workflows/analyze-megacap-earnings.yml) | No scheduled cron | analyze_megacap_earnings |
| [audit-data.yml](../.github/workflows/audit-data.yml) | `40 5 * * 1-5` | audit_data, audit_phase4_gaps |
| [backfill-last-week.yml](../.github/workflows/backfill-last-week.yml) | No scheduled cron | backfill_last_week |
| [backfill-regime-macro-2025.yml](../.github/workflows/backfill-regime-macro-2025.yml) | No scheduled cron | backfill_regime_macro_2025, analyze_regime_outcomes, train_sox_shadow_v1, evaluate_sox_shadow_v1, build_regime_context_dataset, analyze_oil_pressure |
| [catalyst-monitor.yml](../.github/workflows/catalyst-monitor.yml) | `*/30 0-8 * * 1-5`<br>`0 9-10 * * 1-5`<br>`*/30 11-23 * * 1-5` | refresh_catalysts, refresh_market_watch, market_watch_global, validate_open_watch, refresh_upcoming_earnings, build_hype_history |
| [collect-daily-bars.yml](../.github/workflows/collect-daily-bars.yml) | `35 23 * * 1-5` | collect_daily_bars, merge_daily_bars_archive, refresh |
| [daily-nvda-wavetrend.yml](../.github/workflows/daily-nvda-wavetrend.yml) | No scheduled cron | refresh_nvda_wavetrend, publish_nvda_wavetrend |
| [daily-soxl-wavetrend.yml](../.github/workflows/daily-soxl-wavetrend.yml) | No scheduled cron | refresh_soxl_wavetrend, publish_soxl_wavetrend, backtest_wavetrend |
| [enrich-earnings-fundamentals.yml](../.github/workflows/enrich-earnings-fundamentals.yml) | No scheduled cron | enrich_earnings_fundamentals |
| [intraday-avwap-research.yml](../.github/workflows/intraday-avwap-research.yml) | `*/15 13-21 * * 1-5` | collect_intraday_avwap, diagnose_intraday_access |
| [market-watch-code-validation.yml](../.github/workflows/market-watch-code-validation.yml) | No scheduled cron | refresh_catalysts, refresh_market_watch, market_watch_global, validate_open_watch |
| [phase3-constituent-breadth.yml](../.github/workflows/phase3-constituent-breadth.yml) | `20 5 * * 2-6` | backfill_phase3_constituent_breadth, analyze_phase3_breadth_divergence, analyze_phase3_breadth_recovery, analyze_phase3_validation_macro |
| [phase3-resilience-audit.yml](../.github/workflows/phase3-resilience-audit.yml) | No scheduled cron | audit_phase3_resilience, build_phase3_market_structure, audit_phase3_breadth_provenance |
| [phase4-soxx-recovery.yml](../.github/workflows/phase4-soxx-recovery.yml) | No scheduled cron | collect_daily_bars, merge_daily_bars_archive |
| [probe-fedwatch-tavily.yml](../.github/workflows/probe-fedwatch-tavily.yml) | `12 12-22 * * 1-5` | probe_fedwatch_tavily |
| [probe-index-providers.yml](../.github/workflows/probe-index-providers.yml) | No scheduled cron | probe_index_providers |
| [probe-massive-intraday-access.yml](../.github/workflows/probe-massive-intraday-access.yml) | No scheduled cron | probe_massive_intraday_access |
| [probe-massive-oil-futures.yml](../.github/workflows/probe-massive-oil-futures.yml) | No scheduled cron | probe_massive_oil_futures |
| [probe-s5fi-tavily.yml](../.github/workflows/probe-s5fi-tavily.yml) | `20 22 * * 1-5` | probe_s5fi_tavily |
| [probe-yahoo-intraday.yml](../.github/workflows/probe-yahoo-intraday.yml) | No scheduled cron | probe_yahoo_intraday |
| [probe_cnbc_brent.yml](../.github/workflows/probe_cnbc_brent.yml) | No scheduled cron |  |
| [publish-nvda-wavetrend.yml](../.github/workflows/publish-nvda-wavetrend.yml) | No scheduled cron | publish_nvda_wavetrend, append |
| [publish-open-watch.yml](../.github/workflows/publish-open-watch.yml) | No scheduled cron | validate_open_watch, build_hype_history |
| [publish-session-research.yml](../.github/workflows/publish-session-research.yml) | No scheduled cron | publish_session_research |
| [reconcile-nvda-yahoo-wavetrend.yml](../.github/workflows/reconcile-nvda-yahoo-wavetrend.yml) | No scheduled cron | reconcile_nvda_yahoo_wavetrend |
| [refresh-dashboard.yml](../.github/workflows/refresh-dashboard.yml) | `30 13,14,15 * * 1-5` | refresh_dashboard |
| [refresh-live-indices.yml](../.github/workflows/refresh-live-indices.yml) | `*/5 * * * 1-5` | collect_live_indices |
| [refresh-live-oil.yml](../.github/workflows/refresh-live-oil.yml) | `*/5 * * * 1-5` | collect_live_oil |
| [refresh.yml](../.github/workflows/refresh.yml) | `0 3 * * 1-5`<br>`15 8,9 * * 1-5`<br>`30 11,12,13 * * 1-5`<br>`10 13,14 * * 1-5`<br>`*/5 12-22 * * 1-5`<br>`30 14,15 * * 1-5`<br>`0 17,18 * * 1-5`<br>`30 19,20 * * 1-5`<br>`27 20,21 * * 1-5` | collect_live_oil, probe_fedwatch_tavily, probe_massive_intraday_access, probe_yahoo_intraday, shadow_nvda_yahoo_wavetrend, reconcile_nvda_yahoo_wavetrend, research_nvda_wavetrend, research_soxl_wavetrend, backtest_wavetrend, publish_nvda_wavetrend, refresh_nvda_wavetrend, sox_earnings_avwap, collect_sox_avwap, collect_daily_bars, collect_intraday_avwap, probe_s5fi_tavily, audit_data, audit_phase4_gaps, backfill_regime_macro_2025, analyze_oil_pressure, refresh_macro_surprises, verify_macro_actuals, refresh, sync_premarket_brief, publish_session_research, live_confirmation, apply_market_response, refine_scores, reconcile_premarket_scores, fix_three_day_watch, select_session_checkpoint, capture_session_analysis, verify_session_checkpoint, build_chart_history, build_hype_history, build_resilience_history, build_resilience_model, build_resilience_engine, backtest_resilience_engine, build_directional_edge, backtest_directional_edge, backtest_directional_edge_walkforward, build_directional_regimes_v2, backtest_directional_regimes_v2, research_directional_v3, build_directional_engine_v3, validate_directional_engine_v3_holdout, build_regime_context_dataset, analyze_regime_context, build_context_engine_v1, track_directional_v3_prospective, inject_session_analysis_ui |
| [research-nvda-wavetrend.yml](../.github/workflows/research-nvda-wavetrend.yml) | No scheduled cron | research_nvda_wavetrend |
| [research-soxl-wavetrend.yml](../.github/workflows/research-soxl-wavetrend.yml) | No scheduled cron | research_soxl_wavetrend, backtest_wavetrend |
| [shadow-nvda-yahoo-wavetrend.yml](../.github/workflows/shadow-nvda-yahoo-wavetrend.yml) | No scheduled cron | shadow_nvda_yahoo_wavetrend |
| [sox-earnings-avwap.yml](../.github/workflows/sox-earnings-avwap.yml) | `40 22 * * 1-5` | sox_earnings_avwap, collect_sox_avwap |
| [test-massive-benzinga.yml](../.github/workflows/test-massive-benzinga.yml) | No scheduled cron |  |
| [test-massive-premarket.yml](../.github/workflows/test-massive-premarket.yml) | No scheduled cron |  |
| [test-tavily.yml](../.github/workflows/test-tavily.yml) | No scheduled cron |  |
| [update-wavetrend-feeds.yml](../.github/workflows/update-wavetrend-feeds.yml) | `7,22,37,52 8-23 * * 1-5`<br>`7,22,37,52 0-1 * * 2-6` | wavetrend_presentation, update_wavetrend_feeds |
| [validate-code.yml](../.github/workflows/validate-code.yml) | No scheduled cron |  |
| [validate-directional-v3-2025.yml](../.github/workflows/validate-directional-v3-2025.yml) | No scheduled cron | validate_directional_engine_v3_2025 |
| [validate-engines.yml](../.github/workflows/validate-engines.yml) | No scheduled cron | build_resilience_history, build_resilience_model, build_resilience_engine, backtest_resilience_engine, build_directional_edge, backtest_directional_edge, backtest_directional_edge_walkforward, build_directional_regimes_v2, backtest_directional_regimes_v2, research_directional_v3 |

## Key gates and publishing behavior

- refresh.yml admits the main U.S. cash session, pre-open watchdog windows and post-close verification; multiple UTC triggers cover DST. Its numeric checkpoint target times differ from external prose-generation task times.
- refresh-dashboard.yml is an older narrow workflow with a9/10ET gate, not a complete substitute for refresh.yml.
- intraday-avwap-research.yml gates scheduled collection to weekdays09:30–16:10ET; manual invocation can run diagnostics outside the window.
- update-wavetrend-feeds.yml validates before collecting. Failed validation prevents new feed publication; dependent reconciliation can be skipped.
- publish-session-research.yml validates source session records on push/manual. It has no cron and does not generate prose.
- publish-open-watch.yml validates/publishes canonical history. Discovery belongs to catalyst-monitor.yml.
- collect-daily-bars.yml owns persisted per-ticker bar/SMA archive updates; general dashboard refresh must not overwrite its history.
- Research and probe workflow success does not imply incorporation in production scores or website rendering.

For source-to-file cadence and freshness semantics use [Data model](Data-Model.md); for failures use [Operations](Operations.md).
