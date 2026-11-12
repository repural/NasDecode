#!/usr/bin/env python3
"""Validate Directional Regimes v2 separately against forward SOX/SOXL returns."""
import json,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]; IN=R/"data/history/directional-regimes-v2.json"; D=R/"data/history/resilience-daily.json"; L=R/"data/history/soxl-daily.json"; OUT=R/"data/history/directional-regimes-v2-backtest.json"
H=(1,3,5,10)
def f(x):return isinstance(x,(int,float)) and math.isfinite(x)
def avg(a):return sum(a)/len(a) if a else None
def corr(p):
 if len(p)<3:return None
 xm=avg([x for x,y in p]);ym=avg([y for x,y in p]); den=math.sqrt(sum((x-xm)**2 for x,y in p)*sum((y-ym)**2 for x,y in p))
 return round(sum((x-xm)*(y-ym) for x,y in p)/den,4) if den else None
def summ(rows,k):
 a=[r[k] for r in rows if f(r.get(k))];return {"n":len(a),"meanPct":round(avg(a),3) if a else None,"positivePct":round(100*sum(x>0 for x in a)/len(a),1) if a else None}
def grp(rows):return {a:{str(h):summ(rows,f"{a}{h}") for h in H} for a in ("sox","soxl")}
def main():
 e=json.loads(IN.read_text())["records"]; d=json.loads(D.read_text())["records"]; sd=json.loads(L.read_text()); lx={x["date"]:x["close"] for x in sd.get("bars",[]) if f(x.get("close"))}
 dates=sorted(d); pos={x:i for i,x in enumerate(dates)}; rows=[]
 for dt,v in sorted(e.items()):
  i=pos.get(dt); s0=((d[dt].get("market") or {}).get("SOX") or {}).get("close") if dt in d else None;l0=lx.get(dt)
  if i is None or not f(s0):continue
  r={"date":dt,"continuation":v["continuationScore"],"reversal":v["reversalScore"],"dominant":v["dominantSetup"]}
  for h in H:
   if i+h>=len(dates):continue
   x=dates[i+h]; sh=((d[x].get("market") or {}).get("SOX") or {}).get("close");lh=lx.get(x)
   if f(sh):r[f"sox{h}"]=100*(sh/s0-1)
   if f(l0) and f(lh):r[f"soxl{h}"]=100*(lh/l0-1)
  rows.append(r)
 def one(sig):
  return {"correlation":{a:{str(h):corr([(r[sig],r[f"{a}{h}"]) for r in rows if f(r.get(f"{a}{h}"))]) for h in H} for a in ("sox","soxl")},
   "buckets":{"<40":grp([r for r in rows if r[sig]<40]),"40-59.9":grp([r for r in rows if 40<=r[sig]<60]),"60-74.9":grp([r for r in rows if 60<=r[sig]<75]),"75+":grp([r for r in rows if r[sig]>=75])}}
 p={"schemaVersion":1,"validationVersion":"directional-regimes-v2-backtest-1.0","status":"retrospective shadow validation only; formulas must not be promoted from this test alone","timing":"Signal at completed close T; returns begin T+1.","signalSpan":{"start":rows[0]["date"] if rows else None,"end":rows[-1]["date"] if rows else None,"signals":len(rows)},"continuation":one("continuation"),"reversal":one("reversal"),"dominantSetup":{"Continuation":grp([r for r in rows if r["dominant"]=="Continuation"]),"Reversal":grp([r for r in rows if r["dominant"]=="Reversal"]),"No strong setup":grp([r for r in rows if r["dominant"]=="No strong setup"])}}
 OUT.write_text(json.dumps(p,indent=2)+"\n");print(json.dumps(p,indent=2))
if __name__=="__main__":main()
