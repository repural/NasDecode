#!/usr/bin/env python3
"""Frozen Directional Engine v3 classifier.

IMPORTANT: This specification was frozen from development data ending 2026-06-30.
Do not alter thresholds after inspecting holdout results. Any subsequent redesign
must receive a new engine version and a new validation protocol.
"""
import json, math, hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1]
SRC=R/"data/history/resilience-daily.json"
OUT=R/"data/history/directional-engine-v3.json"
ENGINE="directional-engine-v3.0"
DEV_END="2026-06-30"; HOLDOUT_START="2026-07-01"

SPEC={
 "priority":["uptrend_pullback","washout_rebound","continuation","neutral_other"],
 "uptrend_pullback":{"sox10_gt":3.0,"rs10_gt":1.0,"sox1_lt":0.0,"sox1_gt":-3.0},
 "washout_rebound":{"sox5_lt":-2.0,"sox10_lt":0.0},
 "continuation":{"sox5_gt":2.0,"sox10_gt":3.0,"rs5_gt":0.5,"breadth_gte":60.0,"sox1_gte":0.0},
 "notes":[
  "Washout is intentionally not gated by same-day recovery confirmation; development diagnostics showed confirmation was late.",
  "Classification is a setup type, not a monotonic bullish/bearish score.",
  "SOXL indicators are excluded from classification and remain entry-quality inputs only."
 ]
}
def finite(x): return isinstance(x,(int,float)) and math.isfinite(x)
def pct(a,b): return 100*(a/b-1) if finite(a) and finite(b) and b else None
def classify(x):
 if x["sox10"]>3 and x["rs10"]>1 and -3<x["sox1"]<0: return "uptrend_pullback"
 if x["sox5"]<-2 and x["sox10"]<0: return "washout_rebound"
 if x["sox5"]>2 and x["sox10"]>3 and x["rs5"]>.5 and finite(x["breadth"]) and x["breadth"]>=60 and x["sox1"]>=0:return "continuation"
 return "neutral_other"
def main():
 doc=json.loads(SRC.read_text()); rec=doc.get("records") or {}; dates=sorted(rec)
 sox=[((rec[d].get("market") or {}).get("SOX") or {}).get("close") for d in dates]
 qqq=[((rec[d].get("market") or {}).get("QQQ") or {}).get("close") for d in dates]
 rows=[]
 for i,d in enumerate(dates):
  if i<10: continue
  vals={}
  for h in (1,5,10):
   vals[f"sox{h}"]=pct(sox[i],sox[i-h]); vals[f"qqq{h}"]=pct(qqq[i],qqq[i-h])
  if not all(finite(v) for v in vals.values()):continue
  vals["rs5"]=vals["sox5"]-vals["qqq5"]; vals["rs10"]=vals["sox10"]-vals["qqq10"]
  vals["breadth"]=(rec[d].get("derived") or {}).get("basketPositiveBreadthPct")
  rows.append({"date":d,"setup":classify(vals),"inputs":vals})
 spec_text=json.dumps(SPEC,sort_keys=True,separators=(",",":"))
 payload={"schemaVersion":1,"engineVersion":ENGINE,
  "status":"FROZEN shadow candidate; holdout not used in construction; no production score consumes this output",
  "frozenProtocol":{"developmentEnd":DEV_END,"holdoutStart":HOLDOUT_START,
   "specSha256":hashlib.sha256(spec_text.encode()).hexdigest(),
   "rule":"Do not modify this engine version after holdout inspection. Redesign requires a new version."},
  "spec":SPEC,"latest":rows[-1] if rows else None,"records":rows}
 OUT.write_text(json.dumps(payload,indent=2)+"\n")
 print(json.dumps({k:v for k,v in payload.items() if k!="records"},indent=2))
if __name__=="__main__":main()
