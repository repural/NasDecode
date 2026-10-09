#!/usr/bin/env python3
"""Train shadow-only 5-session SOX models with a purged chronological holdout.
Standard-library logistic and ridge regression; no production inference.
"""
import json, math, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ROWS=json.loads((ROOT/"data/history/regime-context-dataset.json").read_text())["records"]
FEATURES=[
 ("trend","sox5dPct"),("trend","soxVsQqq5dPp"),
 ("rates","us10y5dChangeBp"),("volatility","vxn5dPct"),
 ("energy","brent5dPct"),("energy","wti5dPct"),
]
def finite(x): return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def feature(row): return [row["features"].get(group,{}).get(key) for group,key in FEATURES]
def target(row): return row["outcomes"]["sox"].get("5")
# 2025 is training, 2026 is strictly unseen evaluation. Purge last five
# trading sessions of 2025 so their forward outcomes cannot touch 2026.
train_rows=[r for r in ROWS if r["date"].startswith("2025-") and finite(target(r))]
train_rows=train_rows[:-5]
test_rows=[r for r in ROWS if r["date"].startswith("2026-") and finite(target(r))]
assert len(train_rows)>150 and len(test_rows)>100
medians=[];scales=[]
for j in range(len(FEATURES)):
 vals=[feature(r)[j] for r in train_rows if finite(feature(r)[j])]
 assert len(vals)>100,("insufficient training coverage",FEATURES[j])
 medians.append(statistics.median(vals))
def raw(row):
 return [x if finite(x) else medians[j] for j,x in enumerate(feature(row))]
for j in range(len(FEATURES)):
 vals=[raw(r)[j] for r in train_rows]
 sd=statistics.pstdev(vals)
 scales.append(sd if sd>1e-9 else 1.)
means=[statistics.mean(raw(r)[j] for r in train_rows) for j in range(len(FEATURES))]
def vector(r):
 return [1.]+[(x-means[j])/scales[j] for j,x in enumerate(raw(r))]
X=[vector(r) for r in train_rows];Y=[target(r) for r in train_rows]
XT=[vector(r) for r in test_rows];YT=[target(r) for r in test_rows]
def sigmoid(x):
 return 1/(1+math.exp(-max(-35,min(35,x))))
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def fit(labels,logistic):
 w=[0.]*len(X[0])
 for _ in range(4000):
  grads=[0.]*len(w)
  for x,y in zip(X,labels):
   e=(sigmoid(dot(w,x)) if logistic else dot(w,x))-y
   for j,v in enumerate(x): grads[j]+=e*v
  for j in range(len(w)):
   grads[j]=grads[j]/len(X)+(0 if j==0 else .12*w[j])
   w[j]-=(.08 if logistic else .015)*grads[j]
 return w
wl=fit([float(y>0) for y in Y],True)
wr=fit(Y,False)
p=[sigmoid(dot(wl,x)) for x in XT]
r=[dot(wr,x) for x in XT]
base_p=sum(y>0 for y in Y)/len(Y)
base_r=statistics.mean(Y)
def metrics(pred,baseline,kind):
 if kind=="probability":
  actual=[float(y>0) for y in YT]
  loss=lambda a,b:(a-b)**2
 else:
  actual=YT
  loss=lambda a,b:(a-b)**2
 return {"modelMSE":round(statistics.mean(loss(a,b) for a,b in zip(pred,actual)),6),
 "baselineMSE":round(statistics.mean(loss(baseline,b) for b in actual),6),
 "beatsBaseline":statistics.mean(loss(a,b) for a,b in zip(pred,actual))<statistics.mean(loss(baseline,b) for b in actual)}
payload={"version":"sox-shadow-v1","status":"research_only_not_production",
 "train":{"start":train_rows[0]["date"],"end":train_rows[-1]["date"],"n":len(train_rows)},
 "holdout":{"start":test_rows[0]["date"],"end":test_rows[-1]["date"],"n":len(test_rows),"purgedTradingSessions":5},
 "features":[".".join(pair) for pair in FEATURES],
 "preprocessing":{"missing":"training-median","medians":medians,"means":means,"scales":scales},
 "classification":{"algorithm":"L2 logistic regression","coefficients":wl,"trainingBaseRate":base_p,
 "holdout":metrics(p,base_p,"probability")},
 "regression":{"algorithm":"L2 linear regression","coefficients":wr,"trainingMeanPct":base_r,
 "holdout":metrics(r,base_r,"return")},
 "limitations":["Single 2026 chronological holdout","No nested cross-validation or hyperparameter tuning","Overlapping 5-session holdout outcomes","Market-close data timing and historical source alignment require audit"]}
out=ROOT/"data/history/sox-shadow-v1-validation.json"
out.write_text(json.dumps(payload,indent=2)+"\n")
print(json.dumps({"train":payload["train"],"holdout":payload["holdout"],"classification":payload["classification"]["holdout"],"regression":payload["regression"]["holdout"]}))
