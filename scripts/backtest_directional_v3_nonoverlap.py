#!/usr/bin/env python3
"""Research-only, non-overlapping directional-v3 event backtest.

Signal: completed close T. Entry: next session (T+1) SOXL open.
Exit: fifth subsequent session (T+5) SOXL close, with no early exits.
Study each setup with its own T+5 cooldown, and a separate global single-book test.
This is not a tradable signal: no slippage, fees, stop, borrow, or financing.
Do not alter the frozen classifier or use this holdout to retune it.
"""
import json, math
from pathlib import Path

R=Path(__file__).resolve().parents[1]
ENGINE=R/"data/history/directional-engine-v3.json"
HISTORY=R/"data/history/resilience-daily.json"
OUT=R/"data/history/directional-v3-nonoverlap-backtest.json"
START="2026-07-01"
HOLD=5
SETUPS=("washout_rebound","uptrend_pullback","continuation","neutral_other")

def finite(v):
    return isinstance(v,(int,float)) and math.isfinite(v)

def price(records,date,field):
    return ((records[date].get("market") or {}).get("SOXL") or {}).get(field)

def trade(dates,records,i,setup):
    if i+HOLD>=len(dates):
        return None,"not_mature"
    first=dates[i+1]
    last=dates[i+HOLD]
    entry=price(records,first,"open")
    exit_=price(records,last,"close")
    if not finite(entry) or entry<=0 or not finite(exit_) or exit_<=0:
        return None,"missing_entry_or_exit"
    lows=[price(records,d,"low") for d in dates[i+1:i+HOLD+1]]
    valid_lows=[v for v in lows if finite(v) and v>0]
    drawdown=round(100*(min(valid_lows)/entry-1),4) if len(valid_lows)==HOLD else None
    ret=round(100*(exit_/entry-1),4)
    return {"signalDate":dates[i],"setup":setup,"entryDate":first,"exitDate":last,
            "entryOpen":entry,"exitClose":exit_,"returnPct":ret,
            "maxIntratradeDrawdownPct":min(drawdown,0) if drawdown is not None else None},None

def summarize(rows):
    returns=[r["returnPct"] for r in rows]
    drawdowns=[r["maxIntratradeDrawdownPct"] for r in rows if r["maxIntratradeDrawdownPct"] is not None]
    n=len(returns)
    return {"n":n,"meanPct":round(sum(returns)/n,3) if n else None,
            "medianPct":round(sorted(returns)[n//2] if n%2 else
                (sorted(returns)[n//2-1]+sorted(returns)[n//2])/2,3) if n else None,
            "positivePct":round(100*sum(x>0 for x in returns)/n,1) if n else None,
            "drawdownObserved":len(drawdowns),
            "meanMaxDrawdownPct":round(sum(drawdowns)/len(drawdowns),3) if drawdowns else None,
            "worstDrawdownPct":min(drawdowns) if drawdowns else None}

def analyze(engine,history):
    rec=history["records"]
    dates=sorted(rec)
    positions={d:i for i,d in enumerate(dates)}
    signals={r["date"]:r["setup"] for r in engine["records"] if r["date"]>=START}
    # Run separate independent event studies for each setup, plus a single-book
    # portfolio test. Otherwise a neutral-day trade can suppress a Washout signal.
    taken=[]
    per_setup={k:[] for k in SETUPS}
    skipped={"not_mature":0,"missing_entry_or_exit":0,"overlap":0}
    setup_skipped={k:{"overlap":0,"not_mature":0,"missing_entry_or_exit":0} for k in SETUPS}
    blocked_until=-1
    blocked_by_setup={k:-1 for k in SETUPS}
    for day,setup in sorted(signals.items()):
        i=positions.get(day)
        if i is None: continue
        # The category-specific event stream ignores only earlier signals
        # from the SAME setup; it is not a portfolio with simultaneous trades.
        if i<=blocked_by_setup[setup]:
            setup_skipped[setup]["overlap"]+=1
        else:
            item,reason=trade(dates,rec,i,setup)
            if reason:
                setup_skipped[setup][reason]+=1
            else:
                per_setup[setup].append(item)
                blocked_by_setup[setup]=i+HOLD
        if i<=blocked_until:
            skipped["overlap"]+=1
            continue
        item,reason=trade(dates,rec,i,setup)
        if reason:
            skipped[reason]+=1
            continue
        taken.append(item)
        blocked_until=i+HOLD
    return {"schemaVersion":2,"method":"next_session_open_to_T_plus_5_close_non_overlapping",
            "engineVersion":engine.get("engineVersion"),
            "specSha256":(engine.get("frozenProtocol") or {}).get("specSha256"),
            "holdoutStart":START,
            "through":dates[-1] if dates else None,
            "assumptions":["Completed T-close signal; enter T+1 SOXL open; exit T+5 SOXL close.",
                "SetupResults: five-session lock per category (independent setup studies).",
                "Overall/trades: one global five-session lock across all setup types (single-book study).",
                "Different category-specific event streams may overlap each other; never add their trade counts as a portfolio.",
                "No stop loss, take profit, transaction costs, slippage or financing.",
                "Intratrade drawdown uses recorded daily lows, only when all five lows are present.",
                "Chronological holdout with retrospectively measured exits, not prospective execution evidence.",
                "Missing entry or exit price excludes that signal without assuming a price."],
            "skippedSignals":skipped,
            "setupSkippedSignals":setup_skipped,
            "overall":summarize(taken),
            "setupResults":{k:summarize(per_setup[k]) for k in SETUPS},
            "trades":taken,
            "setupTrades":per_setup}

def main():
    result=analyze(json.loads(ENGINE.read_text()),json.loads(HISTORY.read_text()))
    OUT.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"overall":result["overall"],"setups":result["setupResults"],
                      "skipped":result["skippedSignals"],"through":result["through"]},indent=2))
if __name__=="__main__":
    main()
