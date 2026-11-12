#!/usr/bin/env python3
"""Incremental, confirmed-only next-day NVDA WaveTrend research refresh.

Reuse stored, fully-warmed 4H/8H OHLCV candles; retrieve the recent historical
5-minute bars available under Massive's delayed subscription. No current-day
provider requests, no provisional bars and no dashboard scoring changes.
"""
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.research_nvda_wavetrend import load_extended_bars, aggregate, wavetrend, crossover_records

NY=ZoneInfo("America/New_York")
SOURCE=Path("data/research/nvda-wavetrend.json")
REPORT=Path("audit-output/nvda-wavetrend-refresh.json")


def refresh(document, bars, checked_at, symbol="NVDA"):
    if document.get("symbol") != symbol or document.get("fetchErrors"):
        raise ValueError("Cannot incrementally refresh invalid " + symbol + " research source")
    if document.get("timeframes",{}).keys() != {"4h","8h"}:
        raise ValueError("Missing 4H or 8H historical series")
    result=json.loads(json.dumps(document))
    new_days={bar["dateET"] for bar in bars}
    if not new_days:
        return result,False
    stats={}
    for hours in (4,8):
        key=str(hours)+"h"
        old=result["timeframes"][key]
        existing=old.get("candles") or []
        if len(existing)<100:
            raise ValueError("Too few saved warm-up candles for "+key)
        incoming=aggregate(bars,hours)
        by_date={}
        for candle in incoming:
            day=candle["startET"][:10]
            by_date[day]=by_date.get(day,0)+1
            # Reject source with missing 5m intervals for a trading session.
            if candle["underlying5mBars"] != hours*12:
                raise ValueError("Incomplete "+key+" candle "+candle["startET"])
        # No silent partial-session updates or phantom complete bars.
        for day in new_days:
            if by_date.get(day)!=16//hours:
                raise ValueError("Incomplete "+key+" session "+day+
                                 ": got "+str(by_date.get(day,0))+" bars")
        merged={row["startET"]:row for row in existing}
        for candle in incoming:
            merged[candle["startET"]]=candle
        ordered=[merged[t] for t in sorted(merged)]
        rows=wavetrend(ordered)
        crosses=crossover_records(rows)
        old.update(candleCount=len(rows),firstStartET=rows[0]["startET"],
                   lastEndET=rows[-1]["endET"],latest=rows[-1],
                   recentCrosses=crosses[-20:],last20Candles=rows[-20:],
                   crossCount=len(crosses),crosses=crosses,candles=rows)
        stats[key]={"previous":existing[-1]["endET"],
                    "latest":rows[-1]["endET"],"candles":len(rows)}
    # Advance only on genuinely new completed candles. Re-check overlapping
    # provider values, but never republish unchanged history on every run.
    advanced=any(stats[k]["latest"]>stats[k]["previous"] for k in stats)
    if advanced:
        result["generatedET"]=checked_at.isoformat()
        result["historicalDataEndET"]=max(row["timestampET"] for row in bars)
        result["incrementalRefresh"]={"checkedAtET":checked_at.isoformat(),
            "source5mBarCount":len(bars),
            "datesET":sorted(new_days),"timeframes":stats,
            "sourceAccess":"historical_only"}
    return result,advanced


def main():
    now=dt.datetime.now(NY)
    key=os.getenv("MASSIVE_API_KEY","").strip()
    if not key: raise RuntimeError("MASSIVE_API_KEY unavailable")
    original=json.loads(SOURCE.read_text())
    if original.get("timeframes",{}).get("4h",{}).get("candles") is None:
        raise ValueError("Full-year research archive not initialized")
    # A few historical trading dates support holidays and missed scheduled runs.
    last=dt.datetime.fromisoformat(original["timeframes"]["4h"]["latest"]["endET"]).date()
    span=max(3,min(20,(now.date()-last).days+3))
    bars,errors=load_extended_bars(span,now.date(),key)
    if errors:
        raise RuntimeError("Provider historical fetch incomplete: "+str(errors))
    candidate,advanced=refresh(original,bars,now)
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps({"checkedAtET":now.isoformat(),"advanced":advanced,
                      "previousEndET":original["timeframes"]["4h"]["latest"]["endET"],
                      "newEndET":candidate["timeframes"]["4h"]["latest"]["endET"],
                      "historicalBarsFetched":len(bars),"fetchErrors":errors},indent=2)+"\n")
    if advanced:
        SOURCE.write_text(json.dumps(candidate,indent=2)+"\n")
        print("Advanced NVDA WT to",candidate["timeframes"]["4h"]["latest"]["endET"])
    else:
        print("No newer complete historical NVDA WT session. Preserving existing data.")


if __name__=="__main__":
    main()
