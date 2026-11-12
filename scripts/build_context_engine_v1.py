#!/usr/bin/env python3
"""Context Engine v1 shadow research.

Compares state-only baseline with state-specific continuous context using strict
chronological expanding-window predictions. No production score consumes this.
Candidate A: ridge linear. Candidate B: ridge with fixed nonlinear basis
(x and x^2 for each standardized feature), allowing curvature without learned
breakpoints. Resilience is included when point-in-time available.
"""
import json,math
from pathlib import Path
R=Path(__file__).resolve().parents[1];SRC=R/"data/history/regime-context-dataset.json";OUT=R/"data/history/context-engine-v1.json"
P={"us10y":"rates.us10yPct","us10y5d":"rates.us10y5dChangePct","vxn":"volatility.vxn","vxn5d":"volatility.vxn5dPct","brent5d":"energy.brent5dPct","breadth":"internals.semiBreadthPositivePct","relative5d":"trend.soxVsQqq5dPp","sox5d":"trend.sox5dPct","resilience":"resilience.score"}
ST=("washout_rebound","uptrend_pullback","continuation","neutral_other");MIN=20
def g(r,p):
 x=r["features"]
 for k in p.split("."):x=x.get(k) if isinstance(x,dict) else None
 return float(x) if isinstance(x,(int,float)) and math.isfinite(x) else None
def mean(a):return sum(a)/len(a) if a else None
def corr(a,b):
 if len(a)<3:return None
 ma,mb=mean(a),mean(b);xy=sum((x-ma)*(y-mb) for x,y in zip(a,b));xx=sum((x-ma)**2 for x in a);yy=sum((y-mb)**2 for y in b)
 return xy/math.sqrt(xx*yy) if xx and yy else None
def mae(a,b):return mean([abs(x-y) for x,y in zip(a,b)])
def solve(A,b):
 n=len(b)
 for i in range(n):
  q=max(range(i,n),key=lambda k:abs(A[k][i]));A[i],A[q]=A[q],A[i];b[i],b[q]=b[q],b[i];z=A[i][i]
  if abs(z)<1e-9:return None
  for j in range(i,n):A[i][j]/=z
  b[i]/=z
  for k in range(n):
   if k==i:continue
   z=A[k][i]
   for j in range(i,n):A[k][j]-=z*A[i][j]
   b[k]-=z*b[i]
 return b
def fit(train,keys,nonlinear=False,lam=3):
 mu={k:mean([g(r,P[k]) for r in train]) for k in keys};sd={k:(mean([(g(r,P[k])-mu[k])**2 for r in train])**.5 or 1) for k in keys}
 def row(r):
  z=[(g(r,P[k])-mu[k])/sd[k] for k in keys];return [1]+z+([v*v for v in z] if nonlinear else [])
 X=[row(r) for r in train];y=[r["outcomes"]["soxl"]["5"] for r in train];n=len(X[0]);A=[[sum(x[i]*x[j] for x in X)+(lam if i==j and i else 0) for j in range(n)] for i in range(n)];b=[sum(x[i]*yy for x,yy in zip(X,y)) for i in range(n)]
 return solve(A,b),mu,sd,row
def main():
 d=json.loads(SRC.read_text());rows=[r for r in d["records"] if r["cohort"]=="canonical_point_in_time" and isinstance(r["outcomes"]["soxl"]["5"],(int,float))]
 out={"schemaVersion":1,"engineVersion":"context-engine-v1.0","status":"shadow research only; no production score consumes this output","target":"SOXL T+5 return","methodology":{"minimumSameStateTraining":MIN,"validation":"strict chronological expanding window within each frozen v3 state","models":["state-only expanding mean baseline","state-specific ridge linear","state-specific ridge fixed quadratic basis"],"selectionRule":"Do not promote unless context improves baseline out-of-sample with economically sensible stability; no thresholds learned from validation."},"states":{}}
 for s in ST:
  rr=[r for r in rows if r["setup"]["directionalV3"]==s]; keys=[k for k in P if sum(g(r,P[k])!=None for r in rr)>=max(MIN,int(.8*len(rr)))]
  cc=[r for r in rr if all(g(r,P[k])!=None for k in keys)]; actual=[];base=[];lin=[];quad=[];dates=[]
  for i in range(MIN,len(cc)):
   tr=cc[:i];r=cc[i];y=r["outcomes"]["soxl"]["5"];actual.append(y);base.append(mean([x["outcomes"]["soxl"]["5"] for x in tr]));dates.append(r["date"])
   for target,nl in ((lin,False),(quad,True)):
    beta,mu,sd,row=fit(tr,keys,nl)
    x=row(r);target.append(sum(a*b for a,b in zip(beta,x)) if beta else base[-1])
  def met(p):return {"n":len(p),"correlation":round(corr(p,actual),3) if len(p)>2 else None,"maePct":round(mae(p,actual),3) if p else None,"directionalHitPct":round(100*sum((a>0)==(b>0) for a,b in zip(p,actual))/len(p),1) if p else None}
  out["states"][s]={"observations":len(rr),"completeObservations":len(cc),"features":keys,"walkForward":{"firstPrediction":dates[0] if dates else None,"lastPrediction":dates[-1] if dates else None,"baseline":met(base),"linear":met(lin),"quadratic":met(quad)}}
 OUT.write_text(json.dumps(out,indent=2)+"\n");print("wrote",OUT)
if __name__=="__main__":main()
