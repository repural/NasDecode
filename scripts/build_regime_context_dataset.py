#!/usr/bin/env python3
"""Build reusable point-in-time regime-context observations for scoring research.

Rows are feature/outcome records, not a score. Feature namespaces are stable so
future engines can select inputs without coupling to Directional v3. Historical
2025 rows come from the frozen-v3 validation artifact; 2026+ rows use canonical
point-in-time resilience history. Missing features remain null rather than being
reconstructed with future knowledge.
"""
import json,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]
CAN=R/"data/history/resilience-daily.json"
V25=R/"data/history/directional-engine-v3-2025.json"
V3=R/"data/history/directional-engine-v3.json"
RES=R/"data/history/resilience-engine.json"
MACRO25=R/"data/history/regime-macro-2025.json"
OUT=R/"data/history/regime-context-dataset.json"
H=(1,3,5,10)
def f(x):return isinstance(x,(int,float)) and math.isfinite(x)
def pct(a,b):return 100*(a/b-1) if f(a) and f(b) and b else None
def main():
 can=json.loads(CAN.read_text()); rec=can.get("records") or {}; dates=sorted(rec); pos={d:i for i,d in enumerate(dates)}
 v3=json.loads(V3.read_text()); setups={x["date"]:x for x in v3.get("records",[])}
 res=json.loads(RES.read_text()) if RES.exists() else {"records":{}}; resrec=res.get("records") or {}
 macro25=json.loads(MACRO25.read_text()).get("series",{}) if MACRO25.exists() else {}
 def historical_macro(d):
  def value(k):return macro25.get(k,{}).get(d)
  def delta(k,n,basis=False):
   days=sorted(macro25.get(k,{})); prior=[z for z in days if z<=d]
   if len(prior)<=n or prior[-1]!=d:return None
   a=value(k);b=macro25[k][prior[-n-1]]
   return (a-b)*100 if basis else pct(a,b)
  y10=value("us10y");y2=value("us2y")
  return {"rates":{"us10yPct":y10,"us2yPct":y2,"curve2s10sBp":(y10-y2)*100 if f(y10) and f(y2) else None,"us10y5dChangeBp":delta("us10y",5,True),"us10y10dChangeBp":delta("us10y",10,True)}, "volatility":{"vxn":value("vxn"),"vix":value("vix"),"vxn5dPct":delta("vxn",5),"vxn10dPct":delta("vxn",10)},"energy":{"brent":value("brent"),"brent5dPct":delta("brent",5),"wti":value("wti"),"wti5dPct":delta("wti",5)}}
 rows=[]
 # External 2025 frozen validation: preserve its exact recorded inputs/outcomes.
 if V25.exists():
  old=json.loads(V25.read_text())
  for x in old.get("records",[]):
   inp=x.get("inputs") or {}; out=x.get("outcomes") or {}
   rows.append({"date":x["date"],"cohort":"2025_external_retrospective","setup":{"directionalV3":x.get("setup")},
    "features":{"trend":{"sox1dPct":inp.get("sox1"),"sox5dPct":inp.get("sox5"),"sox10dPct":inp.get("sox10"),
      "qqq1dPct":inp.get("qqq1"),"qqq5dPct":inp.get("qqq5"),"qqq10dPct":inp.get("qqq10"),
      "soxVsQqq5dPp":inp.get("rs5"),"soxVsQqq10dPp":inp.get("rs10")},
     "internals":{"semiBreadthPositivePct":inp.get("breadth")},
     **historical_macro(x["date"]),"resilience":{},"valuation":{},"catalyst":{}},
    "outcomes":{"sox":{str(h):out.get(f"sox{h}") for h in H},"soxl":{str(h):out.get(f"soxl{h}") for h in H}},
    "provenance":{"featureTime":"completed close T","source":"directional-engine-v3-2025.json","lookaheadSafe":True}})
 # Canonical 2026+ rows: enrich with market/macro context known at T.
 for d in dates:
  if d<"2026-01-01" or d not in setups: continue
  i=pos[d]; rr=rec[d]; m=rr.get("market") or {}; ma=rr.get("macro") or {}; der=rr.get("derived") or {}; inp=setups[d].get("inputs") or {}
  def close(ns,k):return ((ns.get(k) or {}).get("close"))
  def ret(k,h):
   return pct(close(m,k),close((rec[dates[i-h]].get("market") or {}),k)) if i>=h else None
  def mret(k,h):
   return pct(close(ma,k),close((rec[dates[i-h]].get("macro") or {}),k)) if i>=h else None
  y10=close(ma,"US10Y"); y2=close(ma,"US2Y")
  feat={"trend":{"sox1dPct":inp.get("sox1"),"sox5dPct":inp.get("sox5"),"sox10dPct":inp.get("sox10"),
    "qqq1dPct":inp.get("qqq1"),"qqq5dPct":inp.get("qqq5"),"qqq10dPct":inp.get("qqq10"),
    "soxVsQqq5dPp":inp.get("rs5"),"soxVsQqq10dPp":inp.get("rs10")},
   "internals":{"semiBreadthPositivePct":inp.get("breadth"),"semiBreadthOutperformQqqPct":der.get("basketOutperformQqqPct")},
   "rates":{"us10yPct":y10,"us2yPct":y2,"curve2s10sBp":round((y10-y2)*100,3) if f(y10) and f(y2) else None,
     "us10y5dChangeBp":(y10-close((rec[dates[i-5]].get("macro") or {}),"US10Y"))*100 if i>=5 and f(y10) and f(close((rec[dates[i-5]].get("macro") or {}),"US10Y")) else None,"us10y10dChangeBp":(y10-close((rec[dates[i-10]].get("macro") or {}),"US10Y"))*100 if i>=10 and f(y10) and f(close((rec[dates[i-10]].get("macro") or {}),"US10Y")) else None},
   "volatility":{"vxn":close(ma,"VXN"),"vxn5dPct":mret("VXN",5),"vxn10dPct":mret("VXN",10)},
   "energy":{"brent":close(ma,"Brent"),"brent5dPct":mret("Brent",5),"wti":close(ma,"WTI"),"wti5dPct":mret("WTI",5)},
   "resilience":{},"valuation":{},"catalyst":{}}
  outcomes={"sox":{},"soxl":{}}
  for name,key in (("sox","SOX"),("soxl","SOXL")):
   for h in H:
    outcomes[name][str(h)]=pct(close((rec[dates[i+h]].get("market") or {}),key),close(m,key)) if i+h<len(dates) else None
  rows.append({"date":d,"cohort":"canonical_point_in_time","setup":{"directionalV3":setups[d].get("setup")},
   "features":feat,"outcomes":outcomes,"provenance":{"featureTime":"completed close T","source":"resilience-daily.json + resilience-engine.json + frozen directional v3","lookaheadSafe":True}})
 rows.sort(key=lambda x:x["date"])
 payload={"schemaVersion":1,"datasetVersion":"regime-context-1.0",
  "purpose":"Reusable point-in-time feature/outcome dataset for regime diagnostics and future scoring mechanisms; this file defines no score.",
  "antiLeakage":["Features must be observable by completed close T.","Forward outcomes are labels only and must never be used as same-row features.","Missing historical context remains null; do not reconstruct catalysts, valuation or macro surprises from later knowledge."],
  "featureNamespaces":["trend","internals","rates","volatility","energy","resilience","valuation","catalyst"],
  "outcomeHorizonsTradingSessions":list(H),
  "cohorts":{"2025_external_retrospective":"Frozen v3.0 external validation; partial feature coverage.","canonical_point_in_time":"Canonical NasDecode history with context available at T."},
  "records":rows}
 OUT.write_text(json.dumps(payload,indent=2)+"
")
 print("stored",len(rows),"rows",rows[0]["date"] if rows else None,"through",rows[-1]["date"] if rows else None)
if __name__=="__main__":main()
