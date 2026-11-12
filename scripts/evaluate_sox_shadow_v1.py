#!/usr/bin/env python3
"""Evaluate frozen SOX shadow-v1 coefficients on the original 2026 holdout."""
import json,math,statistics
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
model=json.loads((ROOT/"data/history/sox-shadow-v1-validation.json").read_text())
rows=json.loads((ROOT/"data/history/regime-context-dataset.json").read_text())["records"]
features=[tuple(s.split(".")) for s in model["features"]]
prep=model["preprocessing"]
def sigmoid(z):return 1/(1+math.exp(-max(-35,min(35,z))))
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def predict(row):
 vals=[]
 for i,(group,key) in enumerate(features):
  v=row["features"].get(group,{}).get(key)
  if not finite(v):v=prep["medians"][i]
  vals.append((v-prep["means"][i])/prep["scales"][i])
 x=[1]+vals
 return sigmoid(sum(a*b for a,b in zip(x,model["classification"]["coefficients"]))),sum(a*b for a,b in zip(x,model["regression"]["coefficients"]))
hold=model["holdout"]
test=[r for r in rows if hold["start"]<=r["date"]<=hold["end"] and finite(r["outcomes"]["sox"].get("5"))]
assert len(test)==hold["n"],"holdout changed: do not silently evaluate new data"
entries=[]
for row in test:
 p,r=predict(row)
 y=row["outcomes"]["sox"]["5"]
 t=row["features"].get("trend",{})
 rates=row["features"].get("rates",{})
 vol=row["features"].get("volatility",{})
 strong=finite(t.get("sox5dPct")) and finite(t.get("soxVsQqq5dPp")) and t["sox5dPct"]>0 and t["soxVsQqq5dPp"]>0
 adverse=finite(rates.get("us10y5dChangeBp")) and finite(vol.get("vxn5dPct")) and rates["us10y5dChangeBp"]>0 and vol["vxn5dPct"]>0
 entries.append(dict(date=row["date"],actual=y,up=int(y>0),prob=p,returnPrediction=r,regime=("strong" if strong else "weak")+"_"+("adverse" if adverse else "not_jointly_adverse")))
basep=model["classification"]["trainingBaseRate"]
baser=model["regression"]["trainingMeanPct"]
def report(group):
 n=len(group)
 if not n:return {"n":0}
 brier=statistics.mean((x["prob"]-x["up"])**2 for x in group)
 baseb=statistics.mean((basep-x["up"])**2 for x in group)
 mse=statistics.mean((x["returnPrediction"]-x["actual"])**2 for x in group)
 basem=statistics.mean((baser-x["actual"])**2 for x in group)
 accuracy=sum((x["prob"]>=.5)==bool(x["up"]) for x in group)/n
 baselineacc=sum((basep>=.5)==bool(x["up"]) for x in group)/n
 return {"n":n,"upRate":round(statistics.mean(x["up"] for x in group),4),"directionalAccuracy":round(accuracy,4),"baselineDirectionalAccuracy":round(baselineacc,4),"brier":round(brier,6),"baselineBrier":round(baseb,6),"returnMSE":round(mse,6),"baselineReturnMSE":round(basem,6),"meanActualReturnPct":round(statistics.mean(x["actual"] for x in group),3)}
def grouped(key):
 groups=defaultdict(list)
 for x in entries:groups[key(x)].append(x)
 return {k:report(v) for k,v in sorted(groups.items())}
bins=[]
for lo,hi in [(0,.4),(.4,.5),(.5,.6),(.6,.7),(.7,1.000001)]:
 group=[x for x in entries if lo<=x["prob"]<hi]
 bins.append({"range":f"[{lo:.1f},{hi:.1f})","n":len(group),"meanPredicted":round(statistics.mean(x["prob"] for x in group),4) if group else None,"observedUpRate":round(statistics.mean(x["up"] for x in group),4) if group else None})
# Non-overlapping forward windows: select every fifth chronological observation.
nonoverlap=entries[::5]
high=[x for x in entries if x["prob"]>=.65 or x["prob"]<=.35]
result={"schemaVersion":1,"model":"sox-shadow-v1","status":"diagnostic_research_only","source":"frozen coefficients in sox-shadow-v1-validation.json","holdout":hold,"overall":report(entries),"nonOverlappingEveryFifthSession":report(nonoverlap),"monthly":grouped(lambda x:x["date"][:7]),"regimes":grouped(lambda x:x["regime"]),"probabilityCalibration":bins,"highConfidenceThreshold":"p >= 0.65 or p <= 0.35","highConfidence":report(high),"limitations":["No refitting or feature ablation in this diagnostic","2026 test labels overlap across adjacent five-session horizons","Every-fifth-session subset is one arbitrary nonoverlap offset, not a statistical significance test","Regime breakdown is descriptive and can have small sample sizes","Historical data sources have different provenance between training and holdout","Classification threshold 0.5 was not optimized on test data"]}
out=ROOT/"data/history/sox-shadow-v1-diagnostics.json"
out.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"overall":result["overall"],"nonoverlap":result["nonOverlappingEveryFifthSession"],"highConfidence":result["highConfidence"],"monthly":result["monthly"]}))
