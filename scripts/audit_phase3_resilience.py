#!/usr/bin/env python3
"""Research-only Phase 3 resilience audit; no forward labels enter features."""
import json,math,statistics
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/"data/history/regime-context-dataset.json").read_text())["records"]
def valid(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
fields={"relative5":("trend","soxVsQqq5dPp"),"relative10":("trend","soxVsQqq10dPp"),"sox5":("trend","sox5dPct"),"sox10":("trend","sox10dPct"),"yield5":("rates","us10y5dChangeBp"),"vxn5":("volatility","vxn5dPct"),"brent5":("energy","brent5dPct"),"wti5":("energy","wti5dPct"),"breadth":("internals","semiBreadthPositivePct")}
def get(r,k):
 a,b=fields[k];return r.get("features",{}).get(a,{}).get(b)
cohorts={}
for cohort in sorted(set(r["cohort"] for r in rows)):
 subset=sorted((r for r in rows if r["cohort"]==cohort),key=lambda r:r["date"])
 coverage={k:{"available":sum(valid(get(r,k)) for r in subset),"total":len(subset)} for k in fields}
 output=[]
 for i,r in enumerate(subset):
  # Persistence counts only previously observed completed sessions, never forward labels.
  window=subset[max(0,i-9):i+1]
  vals=[get(q,"relative5") for q in window]
  persistence=sum(v>0 for v in vals)/len(vals) if len(vals)==10 and all(valid(v) for v in vals) else None
  y,v,o=get(r,"yield5"),get(r,"vxn5"),get(r,"brent5")
  adverse=(y>0 and v>0) if valid(y) and valid(v) else None
  oil_pressure=o>0 if valid(o) else None
  relative=get(r,"relative5")
  output.append({"date":r["date"],"leadershipPersistence10":persistence,"adverseRatesVolatility":adverse,"brentRising":oil_pressure,"resilientLeadership":(relative>0 and adverse) if valid(relative) and adverse is not None else None})
 cohorts[cohort]={"dates":{"start":subset[0]["date"],"end":subset[-1]["date"]},"rows":len(subset),"coverage":coverage,"derivedCoverage":{k:sum(x[k] is not None for x in output) for k in ("leadershipPersistence10","adverseRatesVolatility","brentRising","resilientLeadership")},"features":output}
events_path=ROOT/"data/history/market-watch-events.json"
events=json.loads(events_path.read_text()).get("events",[]) if events_path.exists() else []
event_quality={"total":len(events),"timestampedFirstReported":sum(isinstance(e.get("firstReported"),str) and "T" in e["firstReported"] for e in events),"datedFirstReported":sum(isinstance(e.get("firstReported"),str) and len(e["firstReported"])==10 for e in events),"sourceUrlPresent":sum(bool(e.get("sourceUrl")) for e in events),"explicitTimePrecision":dict(Counter(e.get("timePrecision","unspecified") for e in events))}
result={"schemaVersion":1,"status":"research_only","method":"Trailing within-cohort 10-session persistence; all inputs observed no later than completed close T; no forward outcomes used.","cohorts":cohorts,"catalystInventory":event_quality,"warnings":["First-reported date alone cannot establish pre-close availability; exclude from time-sensitive historical features.","Do not combine retrospective and canonical cohorts without source-alignment audit.","Persistence is a rolling average of overlapping five-day relative-return indicators.","This is a coverage/feature audit, not an out-of-sample predictive evaluation."]}
path=ROOT/"data/history/phase3-resilience-feature-audit.json"
path.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"cohorts":{k:{"rows":v["rows"],"coverage":v["coverage"],"derivedCoverage":v["derivedCoverage"]} for k,v in cohorts.items()},"catalysts":event_quality}))
