#!/usr/bin/env python3
"""Directional research protocol v3.

Pre-registers a chronological development/holdout boundary and diagnoses state
transitions using DEVELOPMENT data only. The holdout must not be inspected while
designing the next candidate.
"""
# Trigger marker: v3 development validation
import json,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]
D=R/"data/history/resilience-daily.json"; OUT=R/"data/history/directional-v3-development.json"
# Fixed before v3 candidate design. Roughly final quarter of the available one-year sample.
HOLDOUT_START="2026-07-01"
H=(1,3,5,10)
def f(x):return isinstance(x,(int,float)) and math.isfinite(x)
def ret(a,i,h):
 if i<h or not f(a[i]) or not f(a[i-h]) or not a[i-h]:return None
 return 100*(a[i]/a[i-h]-1)
def avg(a):return sum(a)/len(a) if a else None
def summ(rows,k):
 a=[x[k] for x in rows if f(x.get(k))]
 return {"n":len(a),"meanPct":round(avg(a),3) if a else None,"positivePct":round(100*sum(v>0 for v in a)/len(a),1) if a else None}
def main():
 doc=json.loads(D.read_text()); rec=doc.get("records") or {}; dates=sorted(rec)
 sox=[((rec[d].get("market") or {}).get("SOX") or {}).get("close") for d in dates]
 qqq=[((rec[d].get("market") or {}).get("QQQ") or {}).get("close") for d in dates]
 dev=[d for d in dates if d<HOLDOUT_START]; pos={d:i for i,d in enumerate(dates)}
 groups={"trend_persistence":[],"uptrend_pullback":[],"washout_unconfirmed":[],"confirmed_recovery":[],"other":[]}
 for d in dev:
  i=pos[d]
  if i<10:continue
  sr={h:ret(sox,i,h) for h in H};qr={h:ret(qqq,i,h) for h in H}
  if not all(f(sr[h]) and f(qr[h]) for h in H):continue
  rs={h:sr[h]-qr[h] for h in H}
  der=rec[d].get("derived") or {}; pb=der.get("basketPositiveBreadthPct");ob=der.get("basketOutperformQqqPct")
  # Explicit, interpretable states. These are diagnostic definitions, not a score.
  if sr[5]>2 and sr[10]>3 and rs[5]>0.5 and f(pb) and pb>=60 and sr[1]>=0:
   state="trend_persistence"
  elif sr[10]>3 and rs[10]>1 and sr[1]<0 and sr[1]>-3:
   state="uptrend_pullback"
  elif sr[5]<-2 and sr[10]<0 and sr[1]<=0:
   state="washout_unconfirmed"
  elif sr[5]<0 and sr[10]<0 and sr[1]>0.5 and rs[1]>0 and f(pb) and pb>=60:
   state="confirmed_recovery"
  else:state="other"
  row={"date":d,"sox1":sr[1],"sox3":sr[3],"sox5":sr[5],"sox10":sr[10],"rs1":rs[1],"rs5":rs[5],"pb":pb,"ob":ob}
  for h in H:
   if i+h<len(dates) and dates[i+h]<HOLDOUT_START and f(sox[i+h]):row[f"fwd{h}"]=100*(sox[i+h]/sox[i]-1)
  groups[state].append(row)
 payload={"schemaVersion":1,"researchVersion":"directional-v3-development-1.0",
  "status":"development-only diagnostics; HOLDOUT MUST REMAIN UNINSPECTED until candidate formula is frozen",
  "protocol":{"developmentEnd":"2026-06-30","holdoutStart":HOLDOUT_START,
    "rule":"No holdout outcomes, bucket statistics, correlations, threshold tuning, or candidate comparisons may be used during v3 design.",
    "goal":"Model explicit state transitions rather than map trailing momentum monotonically to forward return."},
  "stateDefinitions":{
   "trend_persistence":"5D SOX >2%, 10D >3%, 5D RS >0.5pp, breadth >=60%, current day non-negative.",
   "uptrend_pullback":"10D SOX >3%, 10D RS >1pp, current day negative but >-3%.",
   "washout_unconfirmed":"5D SOX <-2%, 10D negative, current day non-positive.",
   "confirmed_recovery":"5D and 10D still negative, current day >0.5%, 1D RS positive, breadth >=60%."},
  "developmentSummary":{k:{str(h):summ(v,f"fwd{h}") for h in H} for k,v in groups.items()},
  "developmentRecords":groups}
 OUT.write_text(json.dumps(payload,indent=2)+"\n")
 print(json.dumps({k:v for k,v in payload.items() if k!="developmentRecords"},indent=2))
if __name__=="__main__":main()
