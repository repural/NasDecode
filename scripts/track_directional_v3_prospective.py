#!/usr/bin/env python3
"""Prospective shadow tracker for frozen Directional Engine v3.0.

Classifications are copied once from the frozen engine and never recomputed here.
Forward outcomes are filled only after later completed sessions exist. This file is
not a backtest and must never be backfilled before PROSPECTIVE_START.
"""
import json, math
from pathlib import Path

R=Path(__file__).resolve().parents[1]
ENGINE=R/"data/history/directional-engine-v3.json"
HISTORY=R/"data/history/resilience-daily.json"
OUT=R/"data/history/directional-engine-v3-prospective.json"
DASH=R/"data/dashboard.json"
PROSPECTIVE_START="2026-10-07"
HORIZONS=(1,3,5,10)

def finite(x): return isinstance(x,(int,float)) and math.isfinite(x)
def pct(a,b): return round(100*(a/b-1),4) if finite(a) and finite(b) and b else None

def main():
    eng=json.loads(ENGINE.read_text())
    hist=json.loads(HISTORY.read_text())
    records=hist.get("records") or {}
    dates=sorted(records)
    positions={d:i for i,d in enumerate(dates)}
    engine_rows={x["date"]:x for x in eng.get("records",[])}

    if OUT.exists():
        doc=json.loads(OUT.read_text())
    else:
        doc={
          "schemaVersion":1,
          "trackerVersion":"directional-v3-prospective-1.0",
          "engineVersion":eng.get("engineVersion"),
          "specSha256":(eng.get("frozenProtocol") or {}).get("specSha256"),
          "prospectiveStart":PROSPECTIVE_START,
          "status":"prospective shadow tracking; classifications immutable once recorded; no production score consumes this output",
          "records":[]
        }

    tracked={x["date"]:x for x in doc.get("records",[])}
    # Record every newly completed eligible session exactly once. Never backfill
    # dates before the declared prospective start.
    for d in dates:
        if d < PROSPECTIVE_START or d in tracked or d not in engine_rows:
            continue
        row=engine_rows[d]
        tracked[d]={
          "date":d,
          "setup":row["setup"],
          "recordedInputs":row.get("inputs"),
          "engineVersion":eng.get("engineVersion"),
          "specSha256":(eng.get("frozenProtocol") or {}).get("specSha256"),
          "outcomes":{"SOX":{},"SOXL":{}}
        }

    # Outcomes are observation-only and do not alter the frozen classification.
    for d,row in tracked.items():
        i=positions.get(d)
        if i is None: continue
        for symbol in ("SOX","SOXL"):
            base=((records[d].get("market") or {}).get(symbol) or {}).get("close")
            out=row.setdefault("outcomes",{}).setdefault(symbol,{})
            for h in HORIZONS:
                key=f"T+{h}"
                if key in out: continue
                j=i+h
                if j>=len(dates): continue
                fd=dates[j]
                close=((records[fd].get("market") or {}).get(symbol) or {}).get("close")
                value=pct(close,base)
                if value is not None:
                    out[key]={"date":fd,"returnPct":value}

    doc["records"]=[tracked[d] for d in sorted(tracked)]
    doc["latestTracked"]=doc["records"][-1] if doc["records"] else None
    OUT.write_text(json.dumps(doc,indent=2)+"\n")

    # Publish the current frozen setup as a shadow dashboard factor. It does not
    # participate in any Nasdaq, Opportunity, Consolidation or SOXL Entry score.
    if DASH.exists() and eng.get("latest"):
        dash=json.loads(DASH.read_text())
        latest=eng["latest"]; setup=latest["setup"]
        labels={
          "washout_rebound":"Washout / Rebound",
          "uptrend_pullback":"Uptrend Pullback",
          "continuation":"Continuation",
          "neutral_other":"Neutral / Other"
        }
        meanings={
          "washout_rebound":"Frozen v3 detects a washed-out semiconductor state. Historical/pseudo-OOS validation was strongest at T+1 to T+5; prospective validation is now running.",
          "uptrend_pullback":"Frozen v3 detects a pullback inside an established semiconductor uptrend. Promising historically, but the locked holdout sample was small.",
          "continuation":"Frozen v3 detects established semiconductor momentum. Holdout testing did not validate this state as a forward entry signal; treat it as regime context only.",
          "neutral_other":"Frozen v3 finds no qualifying pullback, washout or continuation setup."
        }
        row={
          "factor":"Directional Setup · v3 shadow",
          "latest":labels.get(setup,setup),
          "direction":"Shadow / prospective validation",
          "signal":"mixed",
          "freshness":f"Completed-session classifier · {latest['date']}",
          "source":"Frozen Directional Engine v3.0",
          "explanation":meanings.get(setup,"Frozen v3 setup classifier."),
          "currentImpact":"Shadow",
          "trend":"Validation only",
          "signalLabel":"🧪 Shadow",
          "scorecard":{"value":labels.get(setup,setup),"arrow":"","change":"does not affect scores"},
          "directionalSetup":{"engineVersion":eng.get("engineVersion"),"specSha256":(eng.get("frozenProtocol") or {}).get("specSha256"),"setup":setup,"date":latest["date"],"inputs":latest.get("inputs") or {},"prospectiveStart":PROSPECTIVE_START}
        }
        rows=dash.setdefault("rows",[])
        rows[:]=[x for x in rows if x.get("factor")!="Directional Setup · v3 shadow"]
        rows.append(row)
        DASH.write_text(json.dumps(dash,indent=2,ensure_ascii=False)+"\n")

    print(json.dumps({"prospectiveStart":PROSPECTIVE_START,"tracked":len(tracked),
                      "latestTracked":doc.get("latestTracked"),"dashboardSetup":(eng.get("latest") or {}).get("setup")},indent=2))

if __name__=="__main__": main()
