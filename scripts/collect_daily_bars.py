"""Incremental adjusted daily OHLCV/VWAP archive for semiconductor research.

Run: python -m scripts.collect_daily_bars [--days 730] [--tickers NVDA,AMD]
Uses Massive as primary source; does not fabricate missing observations.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.refresh import massive_daily_bars

ROOT=Path(__file__).resolve().parents[1]
HISTORY=ROOT/"data/history"
MEMBERSHIP=ROOT/"data/sox_avwap_membership.json"
MANIFEST=HISTORY/"daily-bars-coverage.json"
# Historical membership isn't verified as current; do not silently include delisted names.
OBSOLETE={"QRVO","SWKS"}
REQUIRED=("open","high","low","close","volume","vwap")
INDICATORS=("sma20","sma50")
ETFS=("SOXL","SOXX","SMH","QQQ")

def add_sma(bars):
    """Persist adjusted-close SMAs; never shorten a window to skip missing closes."""
    for i, bar in enumerate(bars):
        for window in (20,50):
            sample=bars[max(0,i-window+1):i+1]
            prices=[b.get("close") for b in sample]
            value=sum(prices)/window if len(prices)==window and all(
                isinstance(x,(float,int)) and x>0 for x in prices) else None
            bar["sma"+str(window)]=round(value,6) if value is not None else None
    return bars


def normalize(raw):
    try:
        day=dt.datetime.fromtimestamp(float(raw["t"])/1000,dt.timezone.utc).date().isoformat()
    except (KeyError,ValueError,TypeError,OverflowError):
        return None
    def number(field):
        v=raw.get(field)
        try:
            z=float(v)
            return z if z==z and abs(z)!=float("inf") else None
        except (ValueError,TypeError):
            return None
    return {"date":day,"open":number("o"),"high":number("h"),
            "low":number("l"),"close":number("c"),
            "volume":number("v"),"vwap":number("vw")}

def read(path,default):
    try:
        with path.open(encoding="utf-8") as f: return json.load(f)
    except (OSError,ValueError): return default

def collect(ticker,days,now):
    path=HISTORY/(ticker.lower()+"-daily.json")
    existing=read(path,{"bars":[]})
    previous={bar["date"]:bar for bar in existing.get("bars",[]) if isinstance(bar,dict) and bar.get("date")}
    raw=massive_daily_bars(ticker,days=days)
    received=0
    for item in raw:
        bar=normalize(item)
        if bar is None: continue
        previous[bar["date"]]={**previous.get(bar["date"],{}),**{k:v for k,v in bar.items() if v is not None or previous.get(bar["date"],{}).get(k) is None}}
        received+=1
    bars=add_sma([previous[k] for k in sorted(previous)])
    # Never delete existing data on provider failure or overwrite non-null fields with missing observations.
    if not raw:
        return {"ticker":ticker,"status":"provider_unavailable","storedSessions":len(bars),
                "firstDate":bars[0]["date"] if bars else None,
                "lastDate":bars[-1]["date"] if bars else None,
                "missingFields":sum(sum(b.get(k) is None for k in REQUIRED) for b in bars),
                "sma20Coverage":sum(b.get("sma20") is not None for b in bars),
                "sma50Coverage":sum(b.get("sma50") is not None for b in bars)}
    document={"schemaVersion":3,"ticker":ticker,"source":"Massive adjusted daily aggregates",
              "adjusted":True,"updatedET":now.isoformat(),"bars":bars}
    path.write_text(json.dumps(document,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"ticker":ticker,"status":"collected","receivedSessions":received,
            "storedSessions":len(bars),"firstDate":bars[0]["date"] if bars else None,
            "lastDate":bars[-1]["date"] if bars else None,
            "missingFields":sum(sum(b.get(k) is None for k in REQUIRED) for b in bars)}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--days",type=int,default=14,
                        help="Calendar-day request window; defaults to incremental, first run backfills 730 days")
    parser.add_argument("--tickers",default="",help="Comma-separated symbols for targeted repair")
    args=parser.parse_args()
    if not os.getenv("MASSIVE_API_KEY"):
        raise SystemExit("MASSIVE_API_KEY unavailable; refusing to publish empty collection")
    cfg=read(MEMBERSHIP,{})
    selected=[t.strip().upper() for t in args.tickers.split(",") if t.strip()] if args.tickers else [
        t for t in cfg.get("constituents",[]) if t not in OBSOLETE]
    selected=list(dict.fromkeys(["NVDA",*ETFS]+selected))
    HISTORY.mkdir(parents=True,exist_ok=True)
    now=dt.datetime.now(ZoneInfo("America/New_York"))
    results={}
    for t in selected:
        path=HISTORY/(t.lower()+"-daily.json")
        days=max(args.days,730) if not path.exists() else args.days
        print("Collecting",t,"calendar days",days,flush=True)
        try: results[t]=collect(t,days,now)
        except Exception as exc:
            print("Source failure",t,repr(exc),flush=True)
            results[t]={"ticker":t,"status":"provider_error","detail":str(exc)[:180]}
    manifest={"schemaVersion":1,"asOfET":now.isoformat(),
              "universeType":"historical_SOX_snapshot_research_not_verified_current",
              "membershipAsOf":cfg.get("membership",{}).get("asOf"),
              "excludedObsoleteTickers":sorted(OBSOLETE),
              "primarySource":"Massive adjusted daily aggregates",
              "fields":["date",*REQUIRED,*INDICATORS],"tickers":results}
    MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("Daily bar coverage:",len(results),"symbols; unavailable:",
          [k for k,v in results.items() if v["status"]!="collected"],flush=True)

if __name__=="__main__":
    main()
