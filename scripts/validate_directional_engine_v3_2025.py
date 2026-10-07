#!/usr/bin/env python3
"""Backfill and validate frozen Directional Engine v3 on calendar 2025.

This is an external historical validation. The frozen v3.0 rules/thresholds are
copied verbatim by importing build_directional_engine_v3.classify; this script
must not tune them from 2025 outcomes. Dec 2024 is fetched only as feature warm-up.
"""
import datetime,json,math,os,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
from build_directional_engine_v3 import classify, ENGINE, SPEC
R=Path(__file__).resolve().parents[1]
OUT=R/"data/history/directional-engine-v3-2025.json"
START=datetime.date(2024,12,1); END=datetime.date(2025,12,31)
EVAL_START="2025-01-01"; EVAL_END="2025-12-31"; H=(1,3,5,10)
API="https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
TICKERS={"SOX":"I:SOX","QQQ":"QQQ","SOXL":"SOXL","NVDA":"NVDA","AMD":"AMD","AVGO":"AVGO","TSM":"TSM","MU":"MU"}
_last=0.0
def f(x): return isinstance(x,(int,float)) and math.isfinite(x)
def fetch(t):
 global _last
 key=os.environ.get("MASSIVE_API_KEY","").strip()
 if not key: raise RuntimeError("MASSIVE_API_KEY is missing")
 wait=15.0-(time.monotonic()-_last)
 if _last and wait>0: time.sleep(wait)
 url=API.format(ticker=urllib.parse.quote(t,safe=""),start=START.isoformat(),end=END.isoformat())+"?adjusted=true&sort=asc&limit=50000"
 req=urllib.request.Request(url,headers={"Authorization":f"Bearer {key}","User-Agent":"NasDecode/1.0"})
 with urllib.request.urlopen(req,timeout=45) as resp: p=json.load(resp)
 _last=time.monotonic()
 out={}
 for b in p.get("results") or []:
  d=datetime.datetime.fromtimestamp(b["t"]/1000,datetime.timezone.utc).date().isoformat()
  out[d]=float(b["c"])
 print(t,len(out)); return out
def pct(a,b): return 100*(a/b-1) if f(a) and f(b) and b else None
def stats(a):
 a=[x for x in a if f(x)]
 if not a:return {"n":0,"meanPct":None,"medianPct":None,"positivePct":None}
 s=sorted(a); n=len(s); med=s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
 return {"n":n,"meanPct":round(sum(a)/n,3),"medianPct":round(med,3),"positivePct":round(100*sum(x>0 for x in a)/n,1)}
def main():
 s={k:fetch(v) for k,v in TICKERS.items()}
 dates=sorted(set(s["SOX"]) & set(s["QQQ"]))
 pos={d:i for i,d in enumerate(dates)}
 rows=[]
 for i,d in enumerate(dates):
  if i<10: continue
  vals={}
  for h in (1,5,10):
   vals[f"sox{h}"]=pct(s["SOX"].get(d),s["SOX"].get(dates[i-h]))
   vals[f"qqq{h}"]=pct(s["QQQ"].get(d),s["QQQ"].get(dates[i-h]))
  basket=[pct(s[k].get(d),s[k].get(dates[i-1])) for k in ("NVDA","AMD","AVGO","TSM","MU")]
  valid=[x for x in basket if f(x)]
  vals["breadth"]=100*sum(x>0 for x in valid)/len(valid) if valid else None
  vals["rs5"]=vals["sox5"]-vals["qqq5"]; vals["rs10"]=vals["sox10"]-vals["qqq10"]
  if not all(f(vals[k]) for k in ("sox1","sox5","sox10","qqq1","qqq5","qqq10","rs5","rs10")): continue
  setup=classify(vals); row={"date":d,"setup":setup,"inputs":vals,"outcomes":{}}
  if EVAL_START<=d<=EVAL_END:
   for name in ("SOX","SOXL"):
    for h in H:
     if i+h<len(dates): row["outcomes"][f"{name.lower()}{h}"]=pct(s[name].get(dates[i+h]),s[name].get(d))
   rows.append(row)
 groups={k:[] for k in ("uptrend_pullback","washout_rebound","continuation","neutral_other")}
 for r in rows: groups[r["setup"]].append(r)
 summary={}
 for g,rs in groups.items():
  summary[g]={name:{str(h):stats([r["outcomes"].get(f"{name}{h}") for r in rs]) for h in H} for name in ("sox","soxl")}
 payload={"schemaVersion":1,"validationVersion":"directional-engine-v3-2025-1.0","engineVersion":ENGINE,
  "period":{"warmupStart":START.isoformat(),"evaluationStart":EVAL_START,"evaluationEnd":EVAL_END},
  "protocol":"Frozen v3.0 applied unchanged. 2025 results are external retrospective validation and are not used to tune thresholds.",
  "setupResults":summary,"records":rows}
 OUT.write_text(json.dumps(payload,indent=2)+"\n"); print(json.dumps({"rows":len(rows),"setupResults":summary},indent=2))
if __name__=="__main__": main()
