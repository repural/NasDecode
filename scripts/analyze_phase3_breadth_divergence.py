#!/usr/bin/env python3
"""Phase 3B research: breadth divergence and descriptive forward-outcome study.
Fixed 30-stock proxy only; not historical SOX membership, no model training.
"""
import json,math,statistics
from pathlib import Path
R=Path(__file__).resolve().parents[1]
raw=json.loads((R/"data/history/phase3-constituent-breadth.json").read_text())
reg=json.loads((R/"data/history/regime-context-dataset.json").read_text())
bydate={r["date"]:r for r in reg["records"]}
records=sorted(raw["records"],key=lambda r:r["date"])
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
enriched=[]
for i,r in enumerate(records):
 b=r.get("proxyPositiveBreadthPct");small=r.get("fiveStockPositiveBreadthPct")
 prior=records[max(0,i-4):i+1]
 seq=[x.get("proxyPositiveBreadthPct") for x in prior]
 breadth5=statistics.mean(seq) if len(seq)==5 and all(finite(x) for x in seq) else None
 prev=records[i-5].get("proxyPositiveBreadthPct") if i>=5 else None
 spread=(small-b) if finite(small) and finite(b) else None
 top=r.get("topFiveAverageReturnPct");mean=r.get("allConstituentAverageReturnPct")
 dispersion=top-mean if finite(top) and finite(mean) else None
 ref=bydate.get(r["date"])
 out=ref.get("outcomes",{}).get("sox",{}).get("5") if ref else None
 enriched.append({"date":r["date"],"cohort":ref.get("cohort") if ref else None,"proxyBreadthPct":b,"fiveStockBreadthPct":small,"basketMinusProxyBreadthPp":spread,"proxyBreadthMean5":breadth5,"proxyBreadthChange5Pp":b-prev if finite(b) and finite(prev) else None,"topFiveMinusUniverseAverageReturnPp":dispersion,"soxForward5dPct_labelOnly":out if finite(out) else None,"missingSymbols":r.get("missingSymbols",[])})
def summary(group):
 values=[x["soxForward5dPct_labelOnly"] for x in group if finite(x["soxForward5dPct_labelOnly"])]
 return {"n":len(values),"meanForward5dPct":round(statistics.mean(values),4) if values else None,"positiveRate":round(sum(v>0 for v in values)/len(values),4) if values else None}
studies={}
for cohort in sorted(set(x["cohort"] for x in enriched if x["cohort"])):
 rs=[x for x in enriched if x["cohort"]==cohort and finite(x["proxyBreadthPct"])]
 studies[cohort]={"highBreadthGte60":summary([x for x in rs if x["proxyBreadthPct"]>=60]),"lowBreadthLt40":summary([x for x in rs if x["proxyBreadthPct"]<40]),"basketOutperformsBreadthBy20pp":summary([x for x in rs if finite(x["basketMinusProxyBreadthPp"]) and x["basketMinusProxyBreadthPp"]>=20]),"basketUnderperformsBreadthBy20pp":summary([x for x in rs if finite(x["basketMinusProxyBreadthPp"]) and x["basketMinusProxyBreadthPp"]<=-20])}
incomplete=[{"date":x["date"],"missingSymbols":x["missingSymbols"],"observedCount":next((r["observedCount"] for r in records if r["date"]==x["date"]),None)} for x in enriched if x["proxyBreadthPct"] is None]
payload={"schemaVersion":1,"status":"descriptive_research_only","proxyUniverse":raw["universe"],"historicalSoxMembershipVerified":False,"nasdaqMethodologyUrl":"https://indexes.nasdaq.com/docs/methodology_SOX.pdf","officialMembershipStatus":"not independently retrieved for each historical effective date","featureCutoff":"completed close T","incompleteSessions":incomplete,"cohortComparisons":studies,"records":enriched,"limitations":["Fixed 30-stock proxy has survivorship bias; not official SOX constituent breadth.","Official Nasdaq SOX methodology specifies 30 constituents, not this specific list.","Forward five-session outcomes are labels only and never enter feature calculation.","Overlapping five-session labels and descriptive thresholds are not predictive validation.","No index weights or dated constituent membership; market-cap contribution concentration is unavailable.","Source dataset must be regenerated to populate missingSymbols on historical rows."]}
out=R/"data/history/phase3-breadth-divergence-research.json"
out.write_text(json.dumps(payload,indent=2)+"\n")
print(json.dumps({"incomplete":incomplete,"comparisons":studies}))
