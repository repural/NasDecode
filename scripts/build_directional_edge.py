#!/usr/bin/env python3
"""NasDecode Directional Edge Engine v1 — shadow / validation only.

Purpose: estimate forward semiconductor momentum separately from structural Resilience.
Signal uses only information available at completed close T. No future returns are inputs.
"""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DAILY=ROOT/"data"/"history"/"resilience-daily.json"
OUT=ROOT/"data"/"history"/"directional-edge.json"
HORIZONS={1:.15,3:.25,5:.35,10:.25}

def finite(x): return isinstance(x,(int,float)) and math.isfinite(x)
def clamp(x,lo=0,hi=100): return max(lo,min(hi,x))
def mean(a): return sum(a)/len(a) if a else None
def lerp(x,pts):
    pts=sorted(pts)
    if x<=pts[0][0]: return pts[0][1]
    if x>=pts[-1][0]: return pts[-1][1]
    for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
        if x<=x1: return y0+(y1-y0)*(x-x0)/(x1-x0)
def weighted(parts):
    good=[(v,w) for v,w in parts if finite(v)]
    if not good:return None
    sw=sum(w for _,w in good)
    return sum(v*w for v,w in good)/sw if sw else None
def ret(closes,i,h):
    if i-h<0 or not finite(closes[i]) or not finite(closes[i-h]) or closes[i-h]==0:return None
    return 100*(closes[i]/closes[i-h]-1)
def mom_score(v):
    if not finite(v):return None
    return round(lerp(v,[(-8,0),(-4,15),(-2,30),(0,50),(2,65),(4,80),(8,100)]),1)
def rs_score(v):
    if not finite(v):return None
    return round(lerp(v,[(-5,0),(-2.5,20),(-1,35),(0,50),(1,65),(2.5,82),(5,100)]),1)
def breadth_score(v):
    if not finite(v):return None
    return round(lerp(v,[(0,0),(20,20),(40,40),(50,50),(60,65),(80,85),(100,100)]),1)
def label(s):
    if s>=75:return "Strong Bullish"
    if s>=60:return "Bullish"
    if s>=45:return "Neutral"
    if s>=30:return "Bearish"
    return "Strong Bearish"

def main():
    doc=json.loads(DAILY.read_text(encoding="utf-8")); rec=doc.get("records") or {}
    dates=sorted(rec)
    sox=[((rec[d].get("market") or {}).get("SOX") or {}).get("close") for d in dates]
    qqq=[((rec[d].get("market") or {}).get("QQQ") or {}).get("close") for d in dates]
    out={}
    for i,d in enumerate(dates):
        if i<10:continue
        abs_h={}; rel_h={}
        for h,w in HORIZONS.items():
            sr=ret(sox,i,h); qr=ret(qqq,i,h)
            abs_h[str(h)]={"returnPct":round(sr,4) if finite(sr) else None,"score":mom_score(sr)}
            rel=(sr-qr) if finite(sr) and finite(qr) else None
            rel_h[str(h)]={"relativePctPoints":round(rel,4) if finite(rel) else None,"score":rs_score(rel)}
        trend=weighted([(abs_h[str(h)]["score"],w) for h,w in HORIZONS.items()])
        relative=weighted([(rel_h[str(h)]["score"],w) for h,w in HORIZONS.items()])
        # Persistent internals: average latest 5 observed breadth readings, all point-in-time.
        tail=dates[max(0,i-4):i+1]
        pos=[(rec[x].get("derived") or {}).get("basketPositiveBreadthPct") for x in tail]
        oq=[(rec[x].get("derived") or {}).get("basketOutperformQqqPct") for x in tail]
        pos=[x for x in pos if finite(x)]; oq=[x for x in oq if finite(x)]
        pos_avg=mean(pos); oq_avg=mean(oq)
        internals=weighted([(breadth_score(pos_avg),.45),(breadth_score(oq_avg),.55)])
        # v1.1: continuation/reversal regime. Validation showed a U-shaped relationship:
        # washed-out momentum often mean-reverted, while strong trend also continued.
        def regime_quality(s):
            if not finite(s): return None
            return round(lerp(s,[(0,85),(20,80),(30,55),(40,35),(50,45),(60,55),(75,70),(90,85),(100,90)]),1)
        trend_q=regime_quality(trend)
        relative_q=regime_quality(relative)
        breadth_q=regime_quality(internals)
        score=weighted([(trend_q,.45),(relative_q,.35),(breadth_q,.20)])
        if not all(finite(x) for x in (trend,relative,internals,score)):continue
        score=round(score,1)
        out[d]={"date":d,"score":score,"label":label(score),
          "components":{"absoluteMomentum":round(trend,1),"relativeMomentum":round(relative,1),"breadthPersistence":round(internals,1),"absoluteSetupQuality":trend_q,"relativeSetupQuality":relative_q,"breadthSetupQuality":breadth_q},
          "weights":{"absoluteMomentum":45,"relativeMomentum":35,"breadthPersistence":20},
          "absoluteHorizons":abs_h,"relativeHorizons":rel_h,
          "breadth":{"sessions":len(tail),"positiveBreadthAvgPct":round(pos_avg,1) if finite(pos_avg) else None,
                     "outperformQqqAvgPct":round(oq_avg,1) if finite(oq_avg) else None}}
    latest=out[max(out)] if out else None
    payload={"schemaVersion":1,"engineVersion":"directional-edge-1.1",
      "status":"shadow / validation only; no production NasDecode score consumes this output",
      "purpose":"Forward-direction continuation/reversal setup signal. Separate from Resilience (structural durability), Hype (event/narrative pressure), and SOXL Entry Quality (instrument timing).",
      "timing":"Completed close T only; all momentum horizons and breadth observations end at T.",
      "architecture":{"score":"45% absolute SOX setup quality + 35% SOX-vs-QQQ relative setup quality + 20% breadth setup quality. Setup quality is U-shaped: washed-out extremes can imply reversal while strong extremes can imply continuation; mid-weak states score lowest.",
        "horizons":"1D 15% + 3D 25% + 5D 35% + 10D 25%",
        "macro":"Not scored here. Rates/VXN/oil belong to the separate environment/resilience layer.",
        "hype":"Not scored here until prospective Hype history is sufficient."},
      "latest":latest,"records":out}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Directional Edge sessions",len(out),"latest",latest and (latest["date"],latest["score"],latest["label"]))
if __name__=="__main__": main()
