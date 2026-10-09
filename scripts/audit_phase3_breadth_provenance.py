#!/usr/bin/env python3
"""Audit semiconductor breadth provenance before Phase 3B predictive research."""
import json,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]
data=json.loads((R/"data/history/regime-context-dataset.json").read_text())
result={"schemaVersion":1,"status":"research_only","finding":"2025 semiBreadthPositivePct is five-stock basket breadth, not full SOX breadth.","cohorts":{},"fullSoxConstituentBreadth":{"status":"unavailable","coverage":0,"constituentUniverse":None,"historicalMembershipVerified":False},"limitations":["2025 basket is NVDA AMD AVGO TSM MU, per scripts/validate_directional_engine_v3_2025.py.","2026 semiBreadthPositivePct is copied from directional-engine-v3 inputs; verify its generating lineage before classifying.","A breadth percentage without dated constituent-level prices and membership cannot establish leadership concentration.","Do not merge basket breadth with full SOX breadth."]}
for cohort in sorted(set(r["cohort"] for r in data["records"])):
 rows=[r for r in data["records"] if r["cohort"]==cohort]
 vals=[r.get("features",{}).get("internals",{}).get("semiBreadthPositivePct") for r in rows]
 valid=[v for v in vals if isinstance(v,(int,float)) and math.isfinite(v)]
 result["cohorts"][cohort]={"rows":len(rows),"recordedBreadthCount":len(valid),"seriesClassification":"verified_five_stock_basket" if cohort=="2025_external_retrospective" else "unverified_upstream_definition","distinctValues":sorted(set(round(v,5) for v in valid)),"fullSoxBreadthCount":0}
p=R/"data/history/phase3-breadth-provenance-audit.json"
p.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"cohorts":result["cohorts"]}))
