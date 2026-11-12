#!/usr/bin/env python3
"""One-shot holdout validation for frozen Directional Engine v3."""
import json,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]
ENG=R/"data/history/directional-engine-v3.json"; SRC=R/"data/history/resilience-daily.json"
OUT=R/"data/history/directional-engine-v3-holdout.json"; START="2026-07-01"; H=(1,3,5,10)
def f(x):return isinstance(x,(int,float)) and math.isfinite(x)
def stats(a):
 return {"n":len(a),"meanPct":round(sum(a)/len(a),3) if a else None,
 "medianPct":round(sorted(a)[len(a)//2] if len(a)%2 else (sorted(a)[len(a)//2-1]+sorted(a)[len(a)//2])/2,3) if a else None,
 "positivePct":round(100*sum(x>0 for x in a)/len(a),1) if a else None}
def main():
 eng=json.loads(ENG.read_text()); doc=json.loads(SRC.read_text()); rec=doc.get("records") or {}; dates=sorted(rec); pos={d:i for i,d in enumerate(dates)}
 sox=[((rec[d].get("market") or {}).get("SOX") or {}).get("close") for d in dates]
 soxl=[((rec[d].get("market") or {}).get("SOXL") or {}).get("close") for d in dates]
 groups={k:[] for k in ["uptrend_pullback","washout_rebound","continuation","neutral_other"]}
 for row in eng["records"]:
  d=row["date"]
  if d<START:continue
  i=pos[d]; o={"date":d}
  for name,a in [("sox",sox),("soxl",soxl)]:
   for h in H:
    if i+h<len(dates) and f(a[i]) and f(a[i+h]) and a[i]:
     o[f"{name}{h}"]=100*(a[i+h]/a[i]-1)
  groups[row["setup"]].append(o)
 summary={}
 for g,rows in groups.items():
  summary[g]={name:{str(h):stats([r[f"{name}{h}"] for r in rows if f(r.get(f"{name}{h}"))]) for h in H} for name in ("sox","soxl")}
 allrows=[r for rows in groups.values() for r in rows]
 baseline={name:{str(h):stats([r[f"{name}{h}"] for r in allrows if f(r.get(f"{name}{h}"))]) for h in H} for name in ("sox","soxl")}
 payload={"schemaVersion":1,"validationVersion":"directional-engine-v3-holdout-1.0",
 "engineVersion":eng["engineVersion"],"specSha256":eng["frozenProtocol"]["specSha256"],
 "holdout":{"start":START,"end":dates[-1],"rule":"One-shot chronological holdout; thresholds were frozen before this file was generated."},
 "baselineAllHoldoutDays":baseline,"setupResults":summary,
 "status":"holdout validation only; do not retune directional-engine-v3.0 from these results"}
 OUT.write_text(json.dumps(payload,indent=2)+"\n"); print(json.dumps(payload,indent=2))
if __name__=="__main__":main()
