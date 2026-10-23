#!/usr/bin/env python3
"""Phase 3: offset sensitivity, continuous interactions, purged walk-forward ridge.
Research only. No changes to live scoring or historical constituent selection.
"""
import json, math, statistics
from pathlib import Path
P=Path(__file__).resolve().parents[1]
A=sorted(json.loads((P/"data/history/phase3-breadth-recovery-research.json").read_text())["records"],key=lambda r:r["date"])
B=json.loads((P/"data/history/regime-context-dataset.json").read_text())["records"]
M={r["date"]:r for r in B}
H=(1,3,5,10)
def ok(v):return type(v) in (float,int) and math.isfinite(v)
def avg(v):return statistics.mean(v) if v else None
def fmt(v):return round(v,5) if ok(v) else None
def stats(rows,h):
 v=[r["labels"].get(str(h)) for r in rows];v=[x for x in v if ok(x)]
 return {"n":len(v),"meanPct":fmt(avg(v)),"positiveRate":fmt(sum(x>0 for x in v)/len(v)) if v else None}
def features(r):
 f=r["features"];m=M.get(r["date"],{}).get("features",{})
 t=m.get("trend",{});y=m.get("rates",{});v=m.get("volatility",{});e=m.get("energy",{})
 return {"breadth":f.get("breadthPct"),"breadthDelta3":f.get("breadthChange3Pp"),"breadthDelta5":f.get("breadthChange5Pp"),"soxMomentum":t.get("sox5dPct"),"soxRelative":t.get("soxVsQqq5dPp"),"yieldDelta":y.get("us10y5dChangeBp"),"vxn":v.get("vxn"),"oilDelta":e.get("brent5dPct")}
BASE=["soxMomentum","soxRelative","yieldDelta","vxn","oilDelta"]
FULL=BASE+["breadth","breadthDelta3","breadthDelta5"]
def vector(r,names):return [features(r).get(k) for k in names]
def solve(a,b):
 n=len(b);m=[a[i][:]+[b[i]] for i in range(n)]
 for k in range(n):
  pivot=max(range(k,n),key=lambda i:abs(m[i][k]))
  if abs(m[pivot][k])<1e-10:return None
  m[k],m[pivot]=m[pivot],m[k]
  z=m[k][k];m[k]=[v/z for v in m[k]]
  for i in range(n):
   if i!=k:
    z=m[i][k];m[i]=[x-z*y for x,y in zip(m[i],m[k])]
 return [m[i][-1] for i in range(n)]
def predict(train,test,names):
 xs=[vector(r,names) for r in train];ys=[r["_target"] for r in train]
 mu=[avg([x[j] for x in xs]) for j in range(len(names))]
 sd=[statistics.pstdev([x[j] for x in xs]) or 1 for j in range(len(names))]
 def norm(x):return [1.0]+[(v-u)/s for v,u,s in zip(x,mu,sd)]
 xx=[norm(x) for x in xs];p=len(names)+1
 gram=[[sum(x[i]*x[j] for x in xx)+(1.0 if i==j and i>0 else 0.0) for j in range(p)] for i in range(p)]
 rhs=[sum(x[i]*y for x,y in zip(xx,ys)) for i in range(p)]
 beta=solve(gram,rhs)
 return sum(w*v for w,v in zip(beta,norm(vector(test,names)))) if beta else None
def metric(pred):
 if not pred:return {"n":0}
 err=[y-yhat for y,yhat in pred]
 return {"n":len(pred),"maePct":fmt(avg([abs(x) for x in err])),"rmsePct":fmt(math.sqrt(avg([x*x for x in err]))),"directionAccuracy":fmt(sum((y>0)==(p>0) for y,p in pred)/len(pred))}
result={}
for cohort in sorted({r.get("cohort") for r in A if r.get("cohort")}):
 rows=[r for r in A if r.get("cohort")==cohort]
 horizons={}
 for h in H:
  offset={}
  for shift in range(h+1):
   sampled=[r for i,r in enumerate(rows) if i%(h+1)==shift and ok(r["labels"].get(str(h)))]
   offset[str(shift)]={s:stats([r for r in sampled if s=="all" or r["features"].get(s)],h) for s in ("all","deteriorating","stabilizing","recovering")}
  stability={}
  for state in ("all","deteriorating","stabilizing","recovering"):
   means=[v[state]["meanPct"] for v in offset.values() if v[state]["n"]>=5 and ok(v[state]["meanPct"])]
   stability[state]={"eligibleOffsets":len(means),"minMeanPct":fmt(min(means)) if means else None,"maxMeanPct":fmt(max(means)) if means else None,"medianMeanPct":fmt(statistics.median(means)) if means else None}
  horizons[str(h)]={"offsets":offset,"stability":stability}
 result[cohort]={"sessions":len(rows),"horizons":horizons}
# Only canonical cohort is eligible for chronological walk-forward. Never mix
# 2025 retrospective feature provenance into training or testing.
canonical=[r for r in A if r.get("cohort")=="canonical_point_in_time"]
walk={}
for h in H:
 predictions={"historicalMean":[],"macroOnly":[],"macroAndBreadth":[]}
 dated=[]
 for i,test in enumerate(canonical):
  # Train labels at index j only if their forward horizon ends before
  # prediction close i; this imposes an h-session purge.
  train=[dict(r,_target=r["labels"].get(str(h))) for j,r in enumerate(canonical[:max(0,i-h)]) if ok(r["labels"].get(str(h))) and all(ok(x) for x in vector(r,FULL))]
  y=test["labels"].get(str(h))
  if len(train)<60 or not ok(y) or not all(ok(x) for x in vector(test,FULL)):continue
  p0=avg([r["_target"] for r in train])
  p1=predict(train,test,BASE);p2=predict(train,test,FULL)
  if not all(ok(x) for x in (p0,p1,p2)):continue
  predictions["historicalMean"].append((y,p0));predictions["macroOnly"].append((y,p1));predictions["macroAndBreadth"].append((y,p2))
  dated.append({"date":test["date"],"actual":fmt(y),"mean":fmt(p0),"macro":fmt(p1),"full":fmt(p2),"trainingRows":len(train)})
 walk[str(h)]={"models":{k:metric(v) for k,v in predictions.items()},"predictions":dated,"trainMinimum":60,"purgeSessions":h}
joined=[r for r in A if r["date"] in M]
payload={"schemaVersion":2,"status":"research_only_no_production_change","sourceDates":{"breadth":A[-1]["date"],"regime":B[-1]["date"],"commonLast":joined[-1]["date"] if joined else None},"alignment":{"breadthSessions":len(A),"regimeSessions":len(B),"joinedSessions":len(joined),"breadthMissingRegimeDates":[r["date"] for r in A if r["date"] not in M],"regimeMissingBreadthDates":[r["date"] for r in B if r["date"] not in {x["date"] for x in A}],"policy":"Join only on exact date; do not forward-fill macro or fabricate missing rows. Refresh upstream datasets independently."},"offsetSensitivity":result,"walkForward":{"cohort":"canonical_point_in_time","model":"expanding-window ridge regression, training-only standardization, fixed L2=1, horizon-purged labels","baseline":"expanding historical mean and macro-only ridge","horizons":walk},"limitations":["Fixed-current-constituent breadth is retrospectively selected; point-in-time model claims are not supported.","2025 external retrospective cohort excluded from walk-forward due to provenance mismatch.","Feature availability at historical close depends on upstream data provenance; requires audit.","Only one fixed ridge penalty and limited history; no hyperparameter tuning or statistical significance claims.","Offset cohorts are not independent of each other.","No source data is invented or filled and production scores are unchanged."]}
out=P/"data/history/phase3-validation-macro-interactions.json"
out.write_text(json.dumps(payload,indent=2)+"\n")
print(json.dumps({"sourceDates":payload["sourceDates"],"alignment":{k:v for k,v in payload["alignment"].items() if not k.endswith("Dates")},"walkForward":{h:v["models"] for h,v in walk.items()}}))
