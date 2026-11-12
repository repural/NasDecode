#!/usr/bin/env python3
"""Descriptive four-regime SOX research; no production scoring changes."""
import json, math
from pathlib import Path
root=Path(__file__).resolve().parents[1]
data=json.loads((root/"data/history/regime-context-dataset.json").read_text())
def valid(x): return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def summary(rows):
 out={"sessions":len(rows)}
 for h in (1,3,5,10):
  values=[r["outcomes"]["sox"][str(h)] for r in rows if valid(r["outcomes"]["sox"].get(str(h)))]
  out[str(h)]={"n":len(values),"meanPct":round(sum(values)/len(values),3) if values else None,"positivePct":round(100*sum(x>0 for x in values)/len(values),1) if values else None}
 return out
regimes={};pressure={};missing=[];oil_groups={};oil_missing=[]
for r in data["records"]:
 t=r["features"]["trend"];y=r["features"]["rates"].get("us10y5dChangeBp");v=r["features"]["volatility"].get("vxn5dPct")
 if not all(valid(x) for x in (t.get("sox5dPct"),t.get("soxVsQqq5dPp"),y,v)):
  missing.append(r["date"]);continue
 strong=t["sox5dPct"]>0 and t["soxVsQqq5dPp"]>0
 p="combined" if y>0 and v>0 else "yields_only" if y>0 else "volatility_only" if v>0 else "neither"
 name=("strong" if strong else "weak")+"_"+("adverse" if p=="combined" else "not_jointly_adverse")
 regimes.setdefault(name,[]).append(r);pressure.setdefault(p,[]).append(r)
 e=r["features"].get("energy",{})
 b=e.get("brent");b5=e.get("brent5dPct");w=e.get("wti");w5=e.get("wti5dPct")
 if not all(valid(x) for x in (b,b5,w,w5)):
  oil_missing.append(r["date"])
 else:
  state="brent_rising" if b5>0 else "brent_flat_or_falling"
  for label in (state,p+"__"+state,name+"__"+state,"brent_above_90" if b>90 else "brent_at_or_below_90","both_oils_rising" if b5>0 and w5>0 else "not_both_oils_rising"):
   oil_groups.setdefault(label,[]).append(r)
payload={"schemaVersion":1,"status":"descriptive_not_predictive","sourceRecords":len(data["records"]),"classified":sum(map(len,regimes.values())),"unclassifiedDates":missing,"oilMissingDates":oil_missing,"definition":{"strong":"SOX 5D > 0 and SOX relative QQQ 5D > 0","adverse":"10Y 5D change > 0 and VXN 5D change > 0","not_jointly_adverse":"includes mixed macro pressure"},"limitations":["Overlapping forward windows","Point-in-time availability not independently audited","No out-of-sample test","Brent $90 cutoff is exploratory, not calibrated","Spot oil close timing may differ from equity market close"],"regimes":{k:summary(v) for k,v in sorted(regimes.items())},"macroPressure":{k:summary(v) for k,v in sorted(pressure.items())},"oilPressure":{k:summary(v) for k,v in sorted(oil_groups.items())},"byCohort":{c:{k:summary([r for r in v if r["cohort"]==c]) for k,v in sorted(regimes.items())} for c in sorted({r["cohort"] for r in data["records"]})}}
(root/"data/history/regime-outcomes-research.json").write_text(json.dumps(payload,indent=2)+"\n")
print("classified",payload["classified"],"unclassified",missing)
