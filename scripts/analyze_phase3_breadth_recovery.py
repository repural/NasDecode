#!/usr/bin/env python3
"""Research-only breadth recovery features and forward SOX outcome study.
Fixed October 2026 constituent selection is retrospective (survivorship/lookahead
selection bias); forward outcomes are labels, never features.
"""
import json, math, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
breadth=json.loads((ROOT/"data/history/phase3-constituent-breadth.json").read_text())
regime=json.loads((ROOT/"data/history/regime-context-dataset.json").read_text())
source=sorted(breadth["records"],key=lambda r:r["date"])
lookup={r["date"]:r for r in regime["records"]}
def valid(x): return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def avg(xs): return statistics.mean(xs) if xs else None
def rounded(x): return round(x,4) if valid(x) else None
def summary(rows,h):
    vals=[r["labels"].get(str(h)) for r in rows]
    vals=[v for v in vals if valid(v)]
    return {"n":len(vals),"meanPct":rounded(avg(vals)),"medianPct":rounded(statistics.median(vals)) if vals else None,"positiveRate":rounded(sum(v>0 for v in vals)/len(vals)) if vals else None}
records=[]
for i,r in enumerate(source):
    b=r.get("currentConstituentSoxObservedBreadthPct")
    def previous(n):
        if i<n:return None
        v=source[i-n].get("currentConstituentSoxObservedBreadthPct")
        return v if valid(v) else None
    p1,p3,p5=previous(1),previous(3),previous(5)
    d1=b-p1 if valid(b) and valid(p1) else None
    d3=b-p3 if valid(b) and valid(p3) else None
    d5=b-p5 if valid(b) and valid(p5) else None
    last5=[x.get("currentConstituentSoxObservedBreadthPct") for x in source[max(0,i-4):i+1]]
    mean5=avg(last5) if len(last5)==5 and all(valid(x) for x in last5) else None
    trough=min(last5) if mean5 is not None else None
    # Signals are evaluated after close T, using information available at T.
    deteriorating=valid(d3) and d3<=-20 and valid(d1) and d1<0
    stabilizing=valid(d3) and d3<=-20 and valid(d1) and d1>=0
    recovering=valid(d3) and d3>=20 and valid(d1) and d1>0 and valid(p3) and p3<=40
    ref=lookup.get(r["date"],{})
    outcomes=ref.get("outcomes",{}).get("sox",{})
    labels={str(h):outcomes.get(str(h)) if valid(outcomes.get(str(h))) else None for h in (1,3,5,10)}
    records.append({"date":r["date"],"cohort":ref.get("cohort"),"features":{"breadthPct":b,"observedCount":r.get("currentConstituentSoxObservedCount"),"coveragePct":r.get("currentConstituentSoxCoveragePct"),"missingSymbols":r.get("currentConstituentSoxMissingSymbols"),"breadthChange1Pp":rounded(d1),"breadthChange3Pp":rounded(d3),"breadthChange5Pp":rounded(d5),"breadthMean5Pct":rounded(mean5),"breadthTrough5Pct":rounded(trough),"fiveStockMinusCurrentBreadthPp":rounded(r["fiveStockPositiveBreadthPct"]-b) if valid(r.get("fiveStockPositiveBreadthPct")) and valid(b) else None,"deteriorating":deteriorating,"stabilizing":stabilizing,"recovering":recovering},"labels":labels})
studies={}
for cohort in sorted(set(r["cohort"] for r in records if r["cohort"])):
    rs=[r for r in records if r["cohort"]==cohort]
    groups={"all":rs,"deteriorating":[r for r in rs if r["features"]["deteriorating"]],"stabilizing":[r for r in rs if r["features"]["stabilizing"]],"recovering":[r for r in rs if r["features"]["recovering"]]}
    studies[cohort]={name:{str(h):summary(rows,h) for h in (1,3,5,10)} for name,rows in groups.items()}
payload={"schemaVersion":1,"status":"descriptive_research_only","featureCutoff":"completed close T","constituentSelection":"fixed 2026-10-13 SOX members retroactively; not point-in-time membership","coveragePolicy":"observed-only breadth, denominator and missing symbols retained","definitions":{"deteriorating":"breadthChange3Pp <= -20 and breadthChange1Pp < 0","stabilizing":"breadthChange3Pp <= -20 and breadthChange1Pp >= 0","recovering":"breadthChange3Pp >= 20 and breadthChange1Pp > 0 and breadth three sessions earlier <= 40"},"outcomeSource":"regime-context-dataset.json outcomes.sox; label only","horizonsTradingSessions":[1,3,5,10],"cohortComparisons":studies,"records":records,"limitations":["Fixed-current membership introduces survivorship and look-ahead selection bias; descriptive research only, not point-in-time predictive validation.","Overlapping forward horizons inflate apparent sample sizes; do not interpret as independent observations.","Signal thresholds are exploratory and not tuned or validated.","Observed-only breadth uses 29 stocks before Q history becomes available; coverage must be considered.","Missing forward labels remain null; no synthetic prices or outcomes."]}
out=ROOT/"data/history/phase3-breadth-recovery-research.json"
out.write_text(json.dumps(payload,indent=2)+"\n")
print(json.dumps({"records":len(records),"cohortComparisons":studies},separators=(",",":")))
