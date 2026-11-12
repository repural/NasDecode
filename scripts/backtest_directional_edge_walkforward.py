#!/usr/bin/env python3
"""Strict expanding-window validation for Directional Edge research.

For every test date T:
- Features use only information available at completed close T.
- Training labels are admitted only when their full forward horizon has matured before T.
- Component mappings are learned from the expanding historical training set, never from T or later.
- v1.1's hand-tuned U-shaped regime_quality curve is NOT used.

This is research/shadow validation only.
"""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EDGE=ROOT/"data"/"history"/"directional-edge.json"
DAILY=ROOT/"data"/"history"/"resilience-daily.json"
SOXL=ROOT/"data"/"history"/"soxl-daily.json"
OUT=ROOT/"data"/"history"/"directional-edge-walkforward.json"
HORIZONS=(1,3,5,10)
COMPONENTS=("absoluteMomentum","relativeMomentum","breadthPersistence")
WEIGHTS={"absoluteMomentum":.45,"relativeMomentum":.35,"breadthPersistence":.20}
MIN_TRAIN=60
BINS=5

def finite(x): return isinstance(x,(int,float)) and math.isfinite(x)
def mean(a): return sum(a)/len(a) if a else None
def corr(p):
    if len(p)<3:return None
    xm=mean([x for x,y in p]); ym=mean([y for x,y in p])
    num=sum((x-xm)*(y-ym) for x,y in p)
    den=math.sqrt(sum((x-xm)**2 for x,y in p)*sum((y-ym)**2 for x,y in p))
    return round(num/den,4) if den else None
def clamp(x,lo=0,hi=100): return max(lo,min(hi,x))
def percentile_rank(values,x):
    if not values:return 50.0
    below=sum(v<x for v in values); equal=sum(v==x for v in values)
    return 100*(below+.5*equal)/len(values)
def learned_quality(train,component,x):
    pairs=[(r["components"].get(component),r.get("target5d")) for r in train]
    pairs=[p for p in pairs if finite(p[0]) and finite(p[1])]
    if len(pairs)<MIN_TRAIN:return None
    pairs.sort(key=lambda p:p[0])
    chunks=[]
    n=len(pairs)
    for b in range(BINS):
        lo=b*n//BINS; hi=(b+1)*n//BINS
        part=pairs[lo:hi]
        if part:
            chunks.append({"x":mean([a for a,y in part]),"y":mean([y for a,y in part])})
    if len(chunks)<2:return None
    ys=[z["y"] for z in chunks]
    # Convert learned forward-return expectation into a stable 0..100 rank.
    # This learns non-monotonic continuation/reversal shapes without hard-coding them.
    ranked=[]
    for z in chunks:
        ranked.append((z["x"],percentile_rank(ys,z["y"])))
    ranked.sort()
    if x<=ranked[0][0]:return ranked[0][1]
    if x>=ranked[-1][0]:return ranked[-1][1]
    for (x0,y0),(x1,y1) in zip(ranked,ranked[1:]):
        if x<=x1:
            return y0 if x1==x0 else y0+(y1-y0)*(x-x0)/(x1-x0)
def label(s):
    if s>=75:return "Strong Bullish"
    if s>=60:return "Bullish"
    if s>=45:return "Neutral"
    if s>=30:return "Bearish"
    return "Strong Bearish"
def summary(rows,key):
    a=[r[key] for r in rows if finite(r.get(key))]
    return {"n":len(a),"meanPct":round(mean(a),3) if a else None,
            "positivePct":round(100*sum(x>0 for x in a)/len(a),1) if a else None}
def group(rows):
    return {asset:{str(h):summary(rows,f"{asset}Fwd{h}dPct") for h in HORIZONS} for asset in ("sox","soxl")}

def main():
    edge=json.loads(EDGE.read_text()).get("records") or {}
    daily=json.loads(DAILY.read_text()).get("records") or {}
    sd=json.loads(SOXL.read_text()); soxl={x["date"]:x["close"] for x in sd.get("bars",[]) if finite(x.get("close"))}
    dates=sorted(daily); pos={d:i for i,d in enumerate(dates)}
    base=[]
    for d,v in sorted(edge.items()):
        if d not in pos:continue
        i=pos[d]; s0=((daily[d].get("market") or {}).get("SOX") or {}).get("close"); l0=soxl.get(d)
        comps=v.get("components") or {}
        if not finite(s0) or not all(finite(comps.get(c)) for c in COMPONENTS):continue
        r={"date":d,"index":i,"components":{c:comps[c] for c in COMPONENTS}}
        for h in HORIZONS:
            if i+h>=len(dates):continue
            e=dates[i+h]; sh=((daily[e].get("market") or {}).get("SOX") or {}).get("close"); lh=soxl.get(e)
            if finite(sh):r[f"soxFwd{h}dPct"]=100*(sh/s0-1)
            if finite(l0) and finite(lh):r[f"soxlFwd{h}dPct"]=100*(lh/l0-1)
        # Primary learning target: 5-session SOX return. It balances direction with usable entry horizon.
        r["target5d"]=r.get("soxFwd5dPct")
        base.append(r)

    rows=[]
    for cur in base:
        # Strict maturity: a 5D label from prior signal j is trainable only after j+5 < current index.
        train=[r for r in base if r["index"]+5 < cur["index"] and finite(r.get("target5d"))]
        if len(train)<MIN_TRAIN:continue
        qualities={c:learned_quality(train,c,cur["components"][c]) for c in COMPONENTS}
        if not all(finite(qualities[c]) for c in COMPONENTS):continue
        score=sum(qualities[c]*WEIGHTS[c] for c in COMPONENTS)
        out={"date":cur["date"],"score":round(clamp(score),1),"label":label(score),
             "trainingSignals":len(train),"components":cur["components"],
             "learnedQuality":{c:round(qualities[c],1) for c in COMPONENTS}}
        for h in HORIZONS:
            for a in ("sox","soxl"):
                k=f"{a}Fwd{h}dPct"
                if finite(cur.get(k)):out[k]=cur[k]
        rows.append(out)

    correlations={a:{str(h):corr([(r["score"],r[f"{a}Fwd{h}dPct"]) for r in rows if finite(r.get(f"{a}Fwd{h}dPct"))])
                     for h in HORIZONS} for a in ("sox","soxl")}
    buckets={"<30":[r for r in rows if r["score"]<30],
             "30-44.9":[r for r in rows if 30<=r["score"]<45],
             "45-59.9":[r for r in rows if 45<=r["score"]<60],
             "60-74.9":[r for r in rows if 60<=r["score"]<75],
             "75+":[r for r in rows if r["score"]>=75]}
    payload={"schemaVersion":1,"validationVersion":"directional-edge-walkforward-1.0",
      "status":"strict expanding-window shadow validation; no production score changes",
      "method":{
        "features":"Raw Directional Edge components observed at completed close T.",
        "learningTarget":"SOX forward 5-session return.",
        "trainingRule":"For each T, only earlier observations whose T+5 outcome had fully matured before T are eligible.",
        "mapping":"Each component is split into five equal-count training bins; historical mean 5D returns are converted to within-training percentile quality and linearly interpolated. No v1.1 hand-tuned U-curve is used.",
        "minimumTrainingSignals":MIN_TRAIN,
        "weights":"45% absolute momentum, 35% relative momentum, 20% breadth persistence."
      },
      "signalSpan":{"start":rows[0]["date"] if rows else None,"end":rows[-1]["date"] if rows else None,"signals":len(rows)},
      "scoreReturnCorrelation":correlations,
      "byScoreBucket":{k:group(v) for k,v in buckets.items()},
      "records":rows}
    OUT.write_text(json.dumps(payload,indent=2)+"\n")
    print(json.dumps({k:v for k,v in payload.items() if k!="records"},indent=2))
if __name__=="__main__":main()
