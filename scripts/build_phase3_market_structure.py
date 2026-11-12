#!/usr/bin/env python3
"""Phase 3B: point-in-time market structure coverage; descriptive research only."""
import json,math,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=json.loads((ROOT/"data/history/regime-context-dataset.json").read_text())
def finite(v):return isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)
def val(row,group,key):return row.get("features",{}).get(group,{}).get(key)
cohorts={}
for cohort in sorted({r["cohort"] for r in source["records"]}):
 rows=sorted([r for r in source["records"] if r["cohort"]==cohort],key=lambda r:r["date"])
 output=[]
 for i,r in enumerate(rows):
  prior=rows[max(0,i-9):i+1]
  rel=[val(x,"trend","soxVsQqq5dPp") for x in prior]
  ret=[val(x,"trend","sox1dPct") for x in prior]
  qret=[val(x,"trend","qqq1dPct") for x in prior]
  breadth=val(r,"internals","semiBreadthPositivePct")
  # Trailing windows use observations through completed close T only.
  persistence=sum(x>0 for x in rel)/10 if len(rel)==10 and all(finite(x) for x in rel) else None
  rel_daily=[a-b for a,b in zip(ret,qret)] if len(ret)==10 and all(finite(x) for x in ret+qret) else []
  relative_vol=statistics.pstdev(rel_daily) if len(rel_daily)==10 else None
  relative_sharpe=(statistics.mean(rel_daily)/relative_vol) if relative_vol is not None and relative_vol>1e-9 else None
  # Return-path drawdown is an approximation using daily closes; no intraday high/low.
  if len(ret)==10 and all(finite(x) for x in ret):
   equity=peak=1.;max_dd=0.
   for x in ret:
    equity*=1+x/100;peak=max(peak,equity);max_dd=min(max_dd,equity/peak-1)
   drawdown=100*max_dd
  else:drawdown=None
  output.append({"date":r["date"],"semiBreadthPositivePct":breadth if finite(breadth) else None,"soxVsQqq5dPp":val(r,"trend","soxVsQqq5dPp"),"soxVsQqq10dPp":val(r,"trend","soxVsQqq10dPp"),"leadershipPersistence10":persistence,"relativeReturnVolatility10":relative_vol,"relativeRiskAdjustedMomentum10":relative_sharpe,"soxCloseToCloseMaxDrawdown10Pct":drawdown,"leadershipConcentration":None,"postShockRecoverySpeed":None})
 keys=list(output[0]);coverage={k:sum(v[k] is not None and (not isinstance(v[k],float) or finite(v[k])) for v in output) for k in keys if k!="date"}
 cohorts[cohort]={"rows":len(rows),"coverage":coverage,"features":output}
result={"schemaVersion":1,"status":"research_only_not_production","featureCutoff":"completed market close T","cohorts":cohorts,"limitations":["2025 retrospective cohort provenance differs from 2026 canonical cohort.","Constituent-level leadership concentration cannot be calculated from aggregate breadth alone; preserved null.","Post-shock recovery speed requires an explicit historical shock-event definition and dated prices; preserved null.","Ten-day drawdown uses daily returns, not intraday extremes.","Trailing relative momentum shares overlapping lookback observations.","No forward outcome or event hindsight is used in feature construction."]}
out=ROOT/"data/history/phase3-market-structure-features.json"
out.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"coverage":{k:v["coverage"] for k,v in cohorts.items()}}))
