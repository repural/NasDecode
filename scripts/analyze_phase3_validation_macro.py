#!/usr/bin/env python3
"""Exploratory breadth validation with spaced observations and macro associations."""
import json,math,statistics
from pathlib import Path
root=Path(__file__).resolve().parents[1]
a=json.loads((root/"data/history/phase3-breadth-recovery-research.json").read_text())["records"]
b=json.loads((root/"data/history/regime-context-dataset.json").read_text())["records"]
market={r["date"]:r for r in b}
def good(x):return isinstance(x,(int,float)) and math.isfinite(x)
def summary(rows,h):
 v=[r["labels"].get(str(h)) for r in rows]
 v=[x for x in v if good(x)]
 return {"n":len(v),"meanPct":round(statistics.mean(v),4) if v else None,"positiveRate":round(sum(x>0 for x in v)/len(v),4) if v else None}
def spaced(rows,h):
 chosen=[];last=-h-1
 for i,r in enumerate(rows):
  if i-last>h and good(r["labels"].get(str(h))):
   chosen.append(r);last=i
 return chosen
def correlation(pairs):
 if len(pairs)<12:return None
 x,y=zip(*pairs)
 mx,my=statistics.mean(x),statistics.mean(y)
 xx=sum((v-mx)**2 for v in x);yy=sum((v-my)**2 for v in y)
 return round(sum((u-mx)*(v-my) for u,v in pairs)/math.sqrt(xx*yy),4) if xx and yy else None
fields={"sox5d":("trend","sox5dPct"),"relative5d":("trend","soxVsQqq5dPp"),"yield5d":("rates","us10y5dChangeBp"),"vxn":("volatility","vxn"),"oil5d":("energy","brent5dPct")}
result={}
for cohort in sorted({r["cohort"] for r in a if r["cohort"]}):
 rows=[r for r in a if r["cohort"]==cohort]
 out={}
 for h in (1,3,5,10):
  chosen=spaced(rows,h)
  states={s:summary([r for r in chosen if s=="all" or r["features"].get(s)],h) for s in ("all","deteriorating","stabilizing","recovering")}
  assoc={}
  for name,(section,key) in fields.items():
   pairs=[]
   for r in chosen:
    v=market.get(r["date"],{}).get("features",{}).get(section,{}).get(key)
    y=r["labels"].get(str(h))
    if good(v) and good(y):pairs.append((v,y))
   assoc[name]={"n":len(pairs),"pearsonR":correlation(pairs)}
  out[str(h)]={"nonOverlapping":states,"macroAssociations":assoc}
 result[cohort]={"sessions":len(rows),"horizons":out}
payload={"status":"research_only","method":"Chronological non-overlap by horizon; Pearson correlations for continuous macro variables.","sourceDates":{"breadth":a[-1]["date"],"regime":b[-1]["date"]},"cohorts":result,"limitations":["Fixed current constituents introduce look-ahead selection bias.","Different cohort provenance; do not pool.","Small non-overlapping samples and overlapping source features.","Exploratory correlations do not establish incremental prediction.","No production scoring changes."]}
(root/"data/history/phase3-validation-macro-interactions.json").write_text(json.dumps(payload,indent=2)+"\n")
print(json.dumps({"cohorts":{k:v["horizons"]["5"]["nonOverlapping"] for k,v in result.items()}}))
