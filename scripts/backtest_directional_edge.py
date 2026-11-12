#!/usr/bin/env python3
"""Validate Directional Edge against forward SOX/SOXL returns. Shadow only."""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EDGE=ROOT/"data"/"history"/"directional-edge.json"
DAILY=ROOT/"data"/"history"/"resilience-daily.json"
SOXL=ROOT/"data"/"history"/"soxl-daily.json"
OUT=ROOT/"data"/"history"/"directional-edge-backtest.json"
H=[1,3,5,10]
def finite(x):return isinstance(x,(int,float)) and math.isfinite(x)
def mean(a):return sum(a)/len(a) if a else None
def corr(p):
    if len(p)<3:return None
    xs=[x for x,y in p];ys=[y for x,y in p];xm=mean(xs);ym=mean(ys)
    num=sum((x-xm)*(y-ym) for x,y in p);den=math.sqrt(sum((x-xm)**2 for x in xs)*sum((y-ym)**2 for y in ys))
    return round(num/den,4) if den else None
def summary(rows,key):
    a=[r[key] for r in rows if finite(r.get(key))]
    return {"n":len(a),"meanPct":round(mean(a),3) if a else None,"positivePct":round(100*sum(x>0 for x in a)/len(a),1) if a else None}
def group(rows):return {asset:{str(h):summary(rows,f"{asset}Fwd{h}dPct") for h in H} for asset in ("sox","soxl")}
def main():
    edge=json.loads(EDGE.read_text()).get("records") or {}
    daily=json.loads(DAILY.read_text()).get("records") or {}
    sd=json.loads(SOXL.read_text());soxl={x["date"]:x["close"] for x in sd.get("bars",[]) if finite(x.get("close"))}
    dates=sorted(daily);pos={d:i for i,d in enumerate(dates)};rows=[]
    for d,v in sorted(edge.items()):
        if d not in pos or not finite(v.get("score")):continue
        i=pos[d];s0=((daily[d].get("market") or {}).get("SOX") or {}).get("close");l0=soxl.get(d)
        if not finite(s0):continue
        r={"date":d,"score":v["score"],"label":v["label"]}
        for h in H:
            if i+h>=len(dates):continue
            e=dates[i+h];sh=((daily[e].get("market") or {}).get("SOX") or {}).get("close");lh=soxl.get(e)
            if finite(sh):r[f"soxFwd{h}dPct"]=100*(sh/s0-1)
            if finite(l0) and finite(lh):r[f"soxlFwd{h}dPct"]=100*(lh/l0-1)
        rows.append(r)
    correlations={a:{str(h):corr([(r["score"],r[f"{a}Fwd{h}dPct"]) for r in rows if finite(r.get(f"{a}Fwd{h}dPct"))]) for h in H} for a in ("sox","soxl")}
    buckets={"<30":[r for r in rows if r["score"]<30],"30-44.9":[r for r in rows if 30<=r["score"]<45],
             "45-59.9":[r for r in rows if 45<=r["score"]<60],"60-74.9":[r for r in rows if 60<=r["score"]<75],
             "75+":[r for r in rows if r["score"]>=75]}
    payload={"schemaVersion":1,"validationVersion":"directional-edge-backtest-1.0",
      "status":"retrospective shadow validation; no production score changes",
      "timing":"Signal at completed T close; forward returns start at T+1.",
      "signalSpan":{"start":rows[0]["date"] if rows else None,"end":rows[-1]["date"] if rows else None,"signals":len(rows)},
      "scoreReturnCorrelation":correlations,"byScoreBucket":{k:group(v) for k,v in buckets.items()},
      "records":rows}
    OUT.write_text(json.dumps(payload,indent=2)+"\n")
    print(json.dumps({k:v for k,v in payload.items() if k!="records"},indent=2))
if __name__=="__main__":main()
