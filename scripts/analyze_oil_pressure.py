#!/usr/bin/env python3
"""Research-only comparison of oil features against forward Nasdaq proxies.

No production score weights or trading rules are changed.
"""
import json, math, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/history/regime-context-dataset.json"
OUTPUT=ROOT/"data/history/oil-pressure-research.json"


def corr(pairs):
    if len(pairs)<20:return None
    xs,ys=zip(*pairs)
    mx,my=statistics.mean(xs),statistics.mean(ys)
    den=math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
    return sum((x-mx)*(y-my) for x,y in pairs)/den if den else None


def main():
    data=json.loads(SOURCE.read_text())
    records=data["records"]
    result={"version":"oil-pressure-research-1.0","status":"diagnostic_only",
            "method":"Pearson association of close-T oil features with forward SOX/SOXL T+5 returns; not causal or validated for production",
            "warnings":["Overlapping forward returns reduce independent sample size.",
                        "Daily completed-close data are not intraday signals.",
                        "Oil ticker mapping and contract continuity require verification before promoting a feature."],
            "cohorts":{}}
    for cohort in sorted({r["cohort"] for r in records}):
        rows=[r for r in records if r["cohort"]==cohort]
        checks={}
        for k in ("brent","wti"):
            vals=[r.get("features",{}).get("energy",{}).get(k) for r in rows]
            vals=[float(v) for v in vals if isinstance(v,(int,float)) and math.isfinite(v)]
            checks[k]={"n":len(vals),"min":min(vals) if vals else None,"max":max(vals) if vals else None,
                       "suspiciousUnder30":sum(v<30 for v in vals)}
        quality=all(checks[k]["n"]>=100 and checks[k]["suspiciousUnder30"]==0 for k in ("brent","wti"))
        metrics={}
        for name,fn in {
            "brent5dPct":lambda e:e.get("brent5dPct"),
            "wti5dPct":lambda e:e.get("wti5dPct"),
            "equalWeightOil5dPct":lambda e:(e["brent5dPct"]+e["wti5dPct"])/2 if isinstance(e.get("brent5dPct"),(int,float)) and isinstance(e.get("wti5dPct"),(int,float)) else None,
            "brentWtiSpreadUsd":lambda e:e["brent"]-e["wti"] if isinstance(e.get("brent"),(int,float)) and isinstance(e.get("wti"),(int,float)) else None,
        }.items():
            metrics[name]={}
            for asset in ("sox","soxl"):
                pairs=[]
                for r in rows:
                    x=fn(r.get("features",{}).get("energy",{}))
                    y=r.get("outcomes",{}).get(asset,{}).get("5")
                    if isinstance(x,(int,float)) and isinstance(y,(int,float)) and math.isfinite(x) and math.isfinite(y):
                        pairs.append((x,y))
                metrics[name][asset]={"n":len(pairs),"pearsonT5":round(corr(pairs),5) if corr(pairs) is not None else None}
        result["cohorts"][cohort]={"priceQuality":checks,"priceQualityPass":quality,"metrics":metrics,
                                   "eligibleForScoringRecommendation":False}
    OUTPUT.write_text(json.dumps(result,indent=2)+"\n")
    print("Oil research saved; no scoring changes.")
    for cohort,x in result["cohorts"].items():
        print(cohort,"qualityPass",x["priceQualityPass"],x["priceQuality"])


if __name__=="__main__":main()
