#!/usr/bin/env python3
"""Continuous/multivariate diagnostics for reusable regime-context observations.
Research only: no thresholds or production scores are changed.
Uses chronological expanding-window ridge models and univariate quantile response
curves so apparent nonlinearities can be inspected without baking sample medians
into NasDecode.
"""
import json,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]; SRC=R/"data/history/regime-context-dataset.json"; OUT=R/"data/history/regime-context-analysis.json"
FEATURES={"us10y":"rates.us10yPct","us10y5d":"rates.us10y5dChangePct","vxn":"volatility.vxn","vxn5d":"volatility.vxn5dPct","brent5d":"energy.brent5dPct","breadth":"internals.semiBreadthPositivePct","relative5d":"trend.soxVsQqq5dPp","sox5d":"trend.sox5dPct"}
STATES=("washout_rebound","uptrend_pullback","continuation","neutral_other")
def g(r,p):
 x=r["features"]
 for k in p.split("."): x=x.get(k) if isinstance(x,dict) else None
 return float(x) if isinstance(x,(int,float)) and math.isfinite(x) else None
def mean(a):return sum(a)/len(a) if a else None
def corr(a,b):
 if len(a)<3:return None
 ma,mb=mean(a),mean(b);xy=sum((x-ma)*(y-mb) for x,y in zip(a,b));xx=sum((x-ma)**2 for x in a);yy=sum((y-mb)**2 for y in b)
 return xy/math.sqrt(xx*yy) if xx and yy else None
def solve(A,b):
 n=len(b)
 for i in range(n):
  q=max(range(i,n),key=lambda k:abs(A[k][i]));A[i],A[q]=A[q],A[i];b[i],b[q]=b[q],b[i]
  z=A[i][i]
  if abs(z)<1e-9:return None
  for j in range(i,n):A[i][j]/=z
  b[i]/=z
  for k in range(n):
   if k==i:continue
   z=A[k][i]
   for j in range(i,n):A[k][j]-=z*A[i][j]
   b[k]-=z*b[i]
 return b
def ridge(train,keys,lam=2.0):
 mu={k:mean([g(r,FEATURES[k]) for r in train]) for k in keys}; sd={k:(mean([(g(r,FEATURES[k])-mu[k])**2 for r in train])**.5 or 1) for k in keys}
 X=[[1]+[(g(r,FEATURES[k])-mu[k])/sd[k] for k in keys] for r in train];y=[r["outcomes"]["soxl"]["5"] for r in train];p=len(keys)+1
 A=[[sum(x[i]*x[j] for x in X)+(lam if i==j and i else 0) for j in range(p)] for i in range(p)];b=[sum(x[i]*yy for x,yy in zip(X,y)) for i in range(p)]
 beta=solve(A,b);return beta,mu,sd
def main():
 d=json.loads(SRC.read_text());rows=[r for r in d["records"] if r["cohort"]=="canonical_point_in_time" and isinstance(r["outcomes"]["soxl"]["5"],(int,float))]
 out={"schemaVersion":1,"analysisVersion":"regime-context-continuous-1.0","status":"research only; no production thresholds or scores changed","target":"SOXL T+5 return","states":{}}
 for s in STATES:
  rr=[r for r in rows if r["setup"]["directionalV3"]==s]; z={"n":len(rr),"univariate":{}}
  for k,p in FEATURES.items():
   a=[r for r in rr if g(r,p)!=None]; a.sort(key=lambda r:g(r,p)); n=len(a); bins=[]
   for q in range(4):
    lo=q*n//4;hi=(q+1)*n//4; b=a[lo:hi]
    if b:bins.append({"n":len(b),"featureMean":round(mean([g(r,p) for r in b]),4),"soxlT5Mean":round(mean([r["outcomes"]["soxl"]["5"] for r in b]),3),"positivePct":round(100*sum(r["outcomes"]["soxl"]["5"]>0 for r in b)/len(b),1)})
   z["univariate"][k]={"pearson":round(corr([g(r,p) for r in a],[r["outcomes"]["soxl"]["5"] for r in a]),3) if len(a)>2 else None,"quartileResponse":bins}
  keys=list(FEATURES); complete=[r for r in rr if all(g(r,FEATURES[k])!=None for k in keys)];pred=[];actual=[]
  for i in range(20,len(complete)):
   beta,mu,sd=ridge(complete[:i],keys)
   if beta:
    x=[1]+[(g(complete[i],FEATURES[k])-mu[k])/sd[k] for k in keys];pred.append(sum(a*b for a,b in zip(beta,x)));actual.append(complete[i]["outcomes"]["soxl"]["5"])
  beta,mu,sd=ridge(complete,keys) if len(complete)>=20 else (None,None,None)
  z["multivariate"]={"method":"ridge; standardized continuous features; chronological expanding-window predictions after 20 same-state observations","walkForwardN":len(pred),"walkForwardCorrelation":round(corr(pred,actual),3) if len(pred)>2 else None,"fullSampleStandardizedCoefficients":({k:round(beta[i+1],3) for i,k in enumerate(keys)} if beta else None)}
  out["states"][s]=z
 OUT.write_text(json.dumps(out,indent=2)+"\n");print("wrote",OUT)
if __name__=="__main__":main()
