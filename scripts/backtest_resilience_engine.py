#!/usr/bin/env python3
"""Backtest Phase 3 Resilience states against forward SOX and SOXL returns.

Strict signal timing:
- Signal is the completed close of date T.
- Forward return T+N = close(T+N trading session) / close(T) - 1.
- No same-day return is counted as future performance.

This is validation only; it does not alter any production score.
"""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/"data"/"history"/"resilience-engine.json"
DAILY=ROOT/"data"/"history"/"resilience-daily.json"
SOXL=ROOT/"data"/"history"/"soxl-daily.json"
OUT=ROOT/"data"/"history"/"resilience-backtest.json"
HORIZONS=[1,3,5,10]

def finite(x): return isinstance(x,(int,float)) and math.isfinite(x)
def mean(a): return sum(a)/len(a) if a else None
def median(a):
    if not a:return None
    s=sorted(a); n=len(s); return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
def pct(a,p):
    if not a:return None
    s=sorted(a); pos=(len(s)-1)*p; lo=int(pos); hi=min(lo+1,len(s)-1); w=pos-lo
    return s[lo]*(1-w)+s[hi]*w
def rnd(x,n=3): return round(x,n) if finite(x) else None

def summarize(rows,key):
    vals=[r[key] for r in rows if finite(r.get(key))]
    if not vals:return {"n":0}
    return {"n":len(vals),"meanPct":rnd(mean(vals)),"medianPct":rnd(median(vals)),
            "positivePct":rnd(100*sum(v>0 for v in vals)/len(vals),1),
            "p25Pct":rnd(pct(vals,.25)),"p75Pct":rnd(pct(vals,.75))}

def group_summary(rows):
    out={}
    for asset in ["sox","soxl"]:
        out[asset]={str(h):summarize(rows,f"{asset}Fwd{h}dPct") for h in HORIZONS}
    return out

def main():
    eng=json.loads(ENGINE.read_text(encoding="utf-8"))
    daily=json.loads(DAILY.read_text(encoding="utf-8")).get("records") or {}
    soxl_doc=json.loads(SOXL.read_text(encoding="utf-8"))
    soxl={b["date"]:b["close"] for b in soxl_doc.get("bars",[]) if finite(b.get("close"))}
    records=eng.get("records") or {}
    signal_dates=[d for d,v in sorted(records.items()) if finite(v.get("score")) and d in daily]
    # Use canonical SOX sessions. Forward endpoints must exist for both SOX and SOXL for fair asset comparison.
    all_sessions=sorted(daily)
    pos={d:i for i,d in enumerate(all_sessions)}
    rows=[]
    for d in signal_dates:
        i=pos[d]; sox0=((daily[d].get("market") or {}).get("SOX") or {}).get("close"); soxl0=soxl.get(d)
        if not finite(sox0): continue
        v=records[d]
        row={"date":d,"score":v["score"],"label":v["label"],"breakdown":(v.get("breakdown") or {}).get("state"),
             "residualStrength":(v.get("components") or {}).get("residualStrength"),
             "confirmation":(v.get("components") or {}).get("internalConfirmation"),
             "phase2ResidualPct":(v.get("phase2") or {}).get("residualPct")}
        for h in HORIZONS:
            if i+h>=len(all_sessions): continue
            ed=all_sessions[i+h]
            soxh=((daily[ed].get("market") or {}).get("SOX") or {}).get("close")
            soxlh=soxl.get(ed)
            if finite(soxh): row[f"soxFwd{h}dPct"]=100*(soxh/sox0-1)
            if finite(soxl0) and finite(soxlh): row[f"soxlFwd{h}dPct"]=100*(soxlh/soxl0-1)
        rows.append(row)

    labels=["Broken","Weak","Weakening","Neutral","Positive","Strong","Exceptional"]
    by_label={lab:group_summary([r for r in rows if r["label"]==lab]) for lab in labels}
    by_breakdown={state:group_summary([r for r in rows if r["breakdown"]==state])
                  for state in ["None","Warning","Breakdown"]}
    buckets={
        "<35":[r for r in rows if r["score"]<35],
        "35-54.9":[r for r in rows if 35<=r["score"]<55],
        "55-64.9":[r for r in rows if 55<=r["score"]<65],
        "65-79.9":[r for r in rows if 65<=r["score"]<80],
        "80+":[r for r in rows if r["score"]>=80],
    }
    by_score_bucket={k:group_summary(v) for k,v in buckets.items()}

    # Continuous association: Pearson score vs forward return. This tests monotonic usefulness.
    correlations={}
    for asset in ["sox","soxl"]:
        correlations[asset]={}
        for h in HORIZONS:
            key=f"{asset}Fwd{h}dPct"; pairs=[(r["score"],r[key]) for r in rows if finite(r.get(key))]
            if len(pairs)<3: correlations[asset][str(h)]=None; continue
            xs=[a for a,b in pairs]; ys=[b for a,b in pairs]; xm=mean(xs); ym=mean(ys)
            num=sum((a-xm)*(b-ym) for a,b in pairs)
            den=math.sqrt(sum((a-xm)**2 for a in xs)*sum((b-ym)**2 for b in ys))
            correlations[asset][str(h)]=rnd(num/den,4) if den else None

    # Incremental test: within same-day SOX direction buckets, compare high vs low resilience.
    # This is a simple guard against mistaking today's SOX strength for resilience information.
    incremental={}
    for regime,fn in {
        "SOX up on signal day":lambda r:(daily[r["date"]].get("derived") or {}).get("soxReturn1dPct",0)>0,
        "SOX down on signal day":lambda r:(daily[r["date"]].get("derived") or {}).get("soxReturn1dPct",0)<=0
    }.items():
        subset=[r for r in rows if fn(r)]
        incremental[regime]={
            "highResilience65+":group_summary([r for r in subset if r["score"]>=65]),
            "lowResilienceBelow45":group_summary([r for r in subset if r["score"]<45])
        }

    payload={
        "schemaVersion":1,"validationVersion":"resilience-backtest-1.0",
        "status":"retrospective validation; no production score changes",
        "timing":"Signal at T close; forward returns begin after T and use T+1/T+3/T+5/T+10 session closes.",
        "signalSpan":{"start":rows[0]["date"] if rows else None,"end":rows[-1]["date"] if rows else None,
                      "signals":len(rows)},
        "caveats":[
            "Phase 3 formula was designed while this historical period was visible, so results are not a pristine unseen-sample test.",
            "Forward-return observations overlap for multi-day horizons; naive significance tests would overstate confidence.",
            "SOXL is leveraged/path-dependent; its returns are validation targets, not a linear proxy for SOX."
        ],
        "scoreReturnCorrelation":correlations,
        "byScoreLabel":by_label,"byScoreBucket":by_score_bucket,
        "byBreakdownState":by_breakdown,"incrementalVsSignalDayDirection":incremental,
        "records":rows
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in payload.items() if k not in ("records","byScoreLabel","incrementalVsSignalDayDirection")},indent=2))
    print("65+ SOX",group_summary([r for r in rows if r["score"]>=65])["sox"])
    print("<45 SOX",group_summary([r for r in rows if r["score"]<45])["sox"])

if __name__=="__main__":
    main()
