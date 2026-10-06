#!/usr/bin/env python3
"""NasDecode Directional Regimes v2 — continuation and reversal separated.

Shadow research only. Uses completed-close T data. It deliberately does not combine
continuation and reversal into one bullish score.
"""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DAILY=ROOT/"data"/"history"/"resilience-daily.json"
OUT=ROOT/"data"/"history"/"directional-regimes-v2.json"
def finite(x): return isinstance(x,(int,float)) and math.isfinite(x)
def clamp(x): return max(0,min(100,x))
def mean(a): return sum(a)/len(a) if a else None
def lerp(x,p):
    p=sorted(p)
    if x<=p[0][0]:return p[0][1]
    if x>=p[-1][0]:return p[-1][1]
    for (x0,y0),(x1,y1) in zip(p,p[1:]):
        if x<=x1:return y0+(y1-y0)*(x-x0)/(x1-x0)
def ret(a,i,h):
    if i<h or not finite(a[i]) or not finite(a[i-h]) or not a[i-h]:return None
    return 100*(a[i]/a[i-h]-1)
def wavg(parts):
    z=[(v,w) for v,w in parts if finite(v)]
    return sum(v*w for v,w in z)/sum(w for v,w in z) if z else None
def hi(x,pts): return lerp(x,pts) if finite(x) else None
def main():
    doc=json.loads(DAILY.read_text()); rec=doc.get("records") or {}; dates=sorted(rec)
    sox=[((rec[d].get("market") or {}).get("SOX") or {}).get("close") for d in dates]
    qqq=[((rec[d].get("market") or {}).get("QQQ") or {}).get("close") for d in dates]
    out={}
    for i,d in enumerate(dates):
        if i<10:continue
        sr={h:ret(sox,i,h) for h in (1,3,5,10)}; qr={h:ret(qqq,i,h) for h in (1,3,5,10)}
        rs={h:(sr[h]-qr[h] if finite(sr[h]) and finite(qr[h]) else None) for h in sr}
        tail=dates[max(0,i-4):i+1]
        pb=[(rec[x].get("derived") or {}).get("basketPositiveBreadthPct") for x in tail]
        ob=[(rec[x].get("derived") or {}).get("basketOutperformQqqPct") for x in tail]
        pb=[x for x in pb if finite(x)]; ob=[x for x in ob if finite(x)]
        pb5=mean(pb); ob5=mean(ob)
        today=(rec[d].get("derived") or {})
        pbt=today.get("basketPositiveBreadthPct"); obt=today.get("basketOutperformQqqPct")

        # CONTINUATION: established medium trend + relative leadership + participation,
        # with recent action confirming rather than merely being extended.
        trend=wavg([(hi(sr[5],[(-4,0),(-1,20),(0,40),(2,65),(4,85),(7,100)]),.55),
                    (hi(sr[10],[(-5,0),(-1,20),(0,40),(3,65),(6,85),(10,100)]),.45)])
        rel=wavg([(hi(rs[5],[(-3,0),(-1,20),(0,45),(1,65),(2.5,85),(5,100)]),.55),
                  (hi(rs[10],[(-4,0),(-1,20),(0,45),(1.5,65),(3,85),(6,100)]),.45)])
        participation=wavg([(hi(pb5,[(20,0),(40,25),(50,45),(60,65),(80,90),(100,100)]),.45),
                            (hi(ob5,[(20,0),(40,25),(50,45),(60,65),(80,90),(100,100)]),.55)])
        confirm=wavg([(hi(sr[1],[(-3,0),(-1,20),(0,50),(1,70),(2.5,90),(5,100)]),.30),
                      (hi(rs[1],[(-2,0),(-.5,25),(0,50),(.5,70),(1.5,90),(3,100)]),.30),
                      (hi(pbt,[(20,0),(40,25),(50,45),(60,65),(80,90),(100,100)]),.20),
                      (hi(obt,[(20,0),(40,25),(50,45),(60,65),(80,90),(100,100)]),.20)])
        cont=clamp(wavg([(trend,.35),(rel,.30),(participation,.20),(confirm,.15)]))

        # REVERSAL: first establish genuine prior weakness, then require evidence of a turn.
        weakness=wavg([(hi(-sr[5],[(-2,0),(0,10),(2,40),(4,70),(7,95),(10,100)]),.55),
                       (hi(-sr[10],[(-3,0),(0,10),(3,40),(6,70),(10,95),(15,100)]),.45)])
        relweak=wavg([(hi(-rs[5],[(-2,0),(0,10),(1,35),(2.5,70),(5,100)]),.60),
                      (hi(-rs[10],[(-3,0),(0,10),(1.5,35),(3,70),(6,100)]),.40)])
        turn=wavg([(hi(sr[1],[(-3,0),(-1,15),(0,40),(.5,60),(1.5,80),(3,100)]),.25),
                   (hi(sr[3],[(-5,0),(-2,15),(0,40),(1,60),(3,85),(6,100)]),.20),
                   (hi(rs[1],[(-2,0),(-.5,20),(0,45),(.5,65),(1.5,90),(3,100)]),.20),
                   (hi(rs[3],[(-3,0),(-1,20),(0,45),(1,70),(2.5,90),(5,100)]),.15),
                   (hi(pbt,[(0,0),(20,15),(40,35),(50,50),(60,70),(80,90),(100,100)]),.10),
                   (hi(obt,[(0,0),(20,15),(40,35),(50,50),(60,70),(80,90),(100,100)]),.10)])
        # Gate: a rebound cannot be a reversal setup without prior weakness; a washout
        # cannot be a reversal setup without a turn. Geometric mean penalizes either missing leg.
        baseweak=wavg([(weakness,.65),(relweak,.35)])
        rev=math.sqrt(max(0,baseweak)*max(0,turn)) if finite(baseweak) and finite(turn) else None

        if not finite(cont) or not finite(rev):continue
        dominant="Continuation" if cont>=rev and cont>=60 else ("Reversal" if rev>cont and rev>=60 else "No strong setup")
        out[d]={"date":d,"continuationScore":round(cont,1),"reversalScore":round(rev,1),"dominantSetup":dominant,
          "continuation":{"trend":round(trend,1),"relativeLeadership":round(rel,1),"participation":round(participation,1),"recentConfirmation":round(confirm,1)},
          "reversal":{"priorWeakness":round(baseweak,1),"turnEvidence":round(turn,1)},
          "raw":{"soxReturnsPct":{str(k):round(v,4) for k,v in sr.items()},"relativeVsQqqPctPoints":{str(k):round(v,4) for k,v in rs.items()},
                 "breadth5d":{"positivePct":round(pb5,1),"outperformQqqPct":round(ob5,1)},"breadthToday":{"positivePct":pbt,"outperformQqqPct":obt}}}
    latest=out[max(out)] if out else None
    payload={"schemaVersion":1,"engineVersion":"directional-regimes-v2.0",
      "status":"shadow / validation only; no production NasDecode score consumes this output",
      "purpose":"Separate trend-continuation and washout-reversal hypotheses instead of forcing both into one Directional Edge number.",
      "timing":"Completed close T only.",
      "rules":{"continuation":"35% established SOX trend + 30% relative leadership + 20% 5D participation + 15% recent confirmation.",
               "reversal":"Geometric gate between prior weakness (65% absolute / 35% relative weakness) and current turn evidence. Both legs must be present.",
               "separation":"Scores are independent hypotheses. Do not add them together."},
      "latest":latest,"records":out}
    OUT.write_text(json.dumps(payload,indent=2)+"\n")
    print("v2 sessions",len(out),"latest",latest)
if __name__=="__main__":main()
