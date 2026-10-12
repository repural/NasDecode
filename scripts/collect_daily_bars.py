"""Incremental adjusted daily OHLCV/VWAP archive for semiconductor research.

Run: python -m scripts.collect_daily_bars [--days 730] [--tickers NVDA,AMD]
Uses Massive as primary source; does not fabricate missing observations.
"""
import argparse
import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
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
    """Calculate comparison-only adjusted-close SMAs; not used for persistence."""
    for i, bar in enumerate(bars):
        for window in (20,50):
            sample=bars[max(0,i-window+1):i+1]
            prices=[b.get("close") for b in sample]
            value=sum(prices)/window if len(prices)==window and all(
                isinstance(x,(float,int)) and x>0 for x in prices) else None
            bar["sma"+str(window)]=round(value,6) if value is not None else None
    return bars



_SMA_LAST_CALL=0.0

def massive_sma(ticker,window,first_date,last_date):
    """Get provider-calculated daily adjusted SMA values; no local substitute on failure."""
    global _SMA_LAST_CALL
    key=os.environ.get("MASSIVE_API_KEY","").strip()
    if not key: return None
    params={"timespan":"day","adjusted":"true","window":window,"series_type":"close",
            "order":"asc","limit":5000,"timestamp.gte":first_date,"timestamp.lte":last_date}
    url="https://api.massive.com/v1/indicators/sma/"+urllib.parse.quote(ticker)+"?"+urllib.parse.urlencode(params)
    values={}
    for page in range(4):
        for attempt,wait_seconds in enumerate((0,15,30,60)):
            wait=12.5-(time.monotonic()-_SMA_LAST_CALL)
            if _SMA_LAST_CALL and wait>0: time.sleep(wait)
            req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"User-Agent":"NasDecode/1.0"})
            try:
                with urllib.request.urlopen(req,timeout=30) as response: payload=json.load(response)
                _SMA_LAST_CALL=time.monotonic()
                if payload.get("status") not in ("OK","DELAYED"):
                    print("SMA provider status",ticker,window,payload.get("status"),flush=True)
                    return None
                break
            except urllib.error.HTTPError as exc:
                _SMA_LAST_CALL=time.monotonic()
                if exc.code!=429 or attempt==3:
                    print("SMA HTTP error",ticker,window,exc.code,flush=True)
                    return None
                try: retry=float(exc.headers.get("Retry-After",wait_seconds or 15))
                except (ValueError,TypeError): retry=wait_seconds or 15
                time.sleep(max(1,retry))
            except (OSError,ValueError) as exc:
                print("SMA network error",ticker,window,repr(exc),flush=True)
                return None
        for item in payload.get("results",{}).get("values",[]):
            try:
                day=dt.datetime.fromtimestamp(float(item["timestamp"])/1000,dt.timezone.utc).date().isoformat()
                value=float(item["value"])
                if value>0 and value==value and abs(value)!=float("inf"): values[day]=round(value,6)
            except (KeyError,TypeError,ValueError,OverflowError): continue
        next_url=payload.get("next_url")
        if not next_url: return values
        if urllib.parse.urlsplit(next_url).hostname!="api.massive.com": return None
        url=next_url
    return None

def merge_provider_sma(bars,observations,window):
    """Retain archived provider values; do not invent values from local closes."""
    field="sma"+str(window)
    for bar in bars:
        if observations is not None and bar["date"] in observations:
            bar[field]=observations[bar["date"]]
            bar[field+"Source"]="Massive"
        else:
            bar.setdefault(field,None)
    return bars

def validate_sma(bars):
    """Compare stored provider values to local close-based estimates for diagnostics only."""
    local=add_sma([{"date":b["date"],"close":b.get("close")} for b in bars])
    result={}
    for window in (20,50):
        key="sma"+str(window)
        pairs=[(b.get(key),x.get(key)) for b,x in zip(bars,local)
               if b.get(key) is not None and x.get(key) is not None]
        discrepancies=sum(abs(a-b)/b>0.002 for a,b in pairs if b)
        result[key]={"providerCoverage":sum(b.get(key) is not None for b in bars),
                     "comparisonCount":len(pairs),"differencesAbove0_2Pct":discrepancies}
    return result

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
    bars=[previous[k] for k in sorted(previous)]
    observations={}
    if bars:
        for window in (20,50):
            obs=massive_sma(ticker,window,bars[0]["date"],bars[-1]["date"])
            merge_provider_sma(bars,obs,window)
            observations[window]="available" if obs is not None else "unavailable"
    # Keep the archive and provider SMA results even if daily aggregates are temporarily unavailable.
    if not bars:
        return {"ticker":ticker,"status":"provider_unavailable","storedSessions":0,
                "smaProvider":observations}
    document={"schemaVersion":3,"ticker":ticker,"source":"Massive adjusted daily aggregates",
              "adjusted":True,"updatedET":now.isoformat(),
              "smaSource":"Massive indicators/sma (adjusted close)", "bars":bars}
    path.write_text(json.dumps(document,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"ticker":ticker,"status":"collected" if raw else "bars_unavailable_sma_checked","receivedSessions":received,
            "storedSessions":len(bars),"firstDate":bars[0]["date"] if bars else None,
            "lastDate":bars[-1]["date"] if bars else None,
            "missingFields":sum(sum(b.get(k) is None for k in REQUIRED) for b in bars),
            "smaProvider":observations,"smaValidation":validate_sma(bars)}

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
    selected=list(dict.fromkeys((["NVDA",*ETFS]+selected) if not args.tickers else selected))
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
