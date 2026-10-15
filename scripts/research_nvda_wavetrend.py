#!/usr/bin/env python3
"""Research-only LazyBear WaveTrend (WT Cross LB) on NVDA 4H/8H extended-hours bars.

Uses Massive 5-minute adjusted NVDA aggregates, excludes current ET trading date
because this API key has returned 403 for same-day access. Nothing in this file
drives NasDecode scoring. Session bars 04:00-20:00 ET (America/New_York).
TradingView candle alignment / indicator equivalence remain UNVERIFIED.
"""
import argparse
import datetime as dt
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
OUT = Path("data/research/nvda-wavetrend.json")
BASE = "https://api.massive.com/v2/aggs/ticker/NVDA/range/5/minute/"
LAST_FETCH = 0.0
CHANNEL = 10
AVERAGE = 21
SIGNAL = 4
MIN_HISTORY = 100


def ema(series, length):
    """Pine-style EMA seeded by first defined observation, skipping na."""
    alpha = 2 / (length + 1)
    out = []
    prev = None
    for value in series:
        if value is not None and math.isfinite(value):
            prev = value if prev is None else alpha * value + (1 - alpha) * prev
        out.append(prev)
    return out


def sma(series, length):
    out = []
    for i in range(len(series)):
        window = series[max(0, i-length+1):i+1]
        out.append(sum(window)/length if len(window)==length and all(v is not None for v in window) else None)
    return out


def wavetrend(candles):
    ap = [(c["high"]+c["low"]+c["close"])/3 for c in candles]
    esa = ema(ap, CHANNEL)
    dev = ema([abs(p-e) if e is not None else None for p,e in zip(ap, esa)], CHANNEL)
    ci = [(p-e)/(0.015*d) if e is not None and d is not None and d>0 else None
          for p,e,d in zip(ap,esa,dev)]
    wt1 = ema(ci, AVERAGE)
    wt2 = sma(wt1, SIGNAL)
    rows = []
    for i,c in enumerate(candles):
        a,b=wt1[i],wt2[i]
        olda,oldb=(wt1[i-1],wt2[i-1]) if i else (None,None)
        cross = None
        if (i >= MIN_HISTORY and all(v is not None for v in (a,b,olda,oldb))):
            if olda <= oldb and a > b: cross = "bullish"
            elif olda >= oldb and a < b: cross = "bearish"
        rows.append({**c, "wt1":round(a,6) if a is not None else None,
                     "wt2":round(b,6) if b is not None else None,
                     "cross":cross, "isWarm": i>=MIN_HISTORY})
    return rows


def fetch_bars(start, end, key):
    """Fetch all pages for a dated range with plan-aware throttling and no truncation."""
    global LAST_FETCH
    url=BASE + start.isoformat()+"/"+end.isoformat()+"?adjusted=true&sort=asc&limit=5000"
    rows=[]
    seen=set()
    for page in range(30):
        if url in seen: return [],"repeated_pagination_url"
        seen.add(url)
        wait = max(0, 12.5-(time.monotonic()-LAST_FETCH)) if LAST_FETCH else 0
        if wait: time.sleep(wait)
        request=urllib.request.Request(url,headers={
            "Authorization":"Bearer "+key,
            "User-Agent":"NasDecode-WaveTrend-Research/1.0"
        })
        payload=None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request,timeout=45) as resp:
                    payload=json.load(resp)
                LAST_FETCH=time.monotonic()
                break
            except urllib.error.HTTPError as exc:
                LAST_FETCH=time.monotonic()
                if exc.code!=429 or attempt==3: return [],"http_"+str(exc.code)
                delay=(15,30,60)[attempt]
                print("rate-limited; waiting",delay,"seconds",flush=True)
                time.sleep(delay)
            except (OSError,ValueError) as exc:
                return [],type(exc).__name__
        if payload is None:return [],"provider_no_response"
        if payload.get("status") not in ("OK","DELAYED"):
            return [],"provider_status_"+str(payload.get("status"))
        rows.extend(payload.get("results") or [])
        next_url=payload.get("next_url")
        if not next_url: return rows,"ok"
        # The provider's next_url may omit the API key; use the Authorization header.
        if urllib.parse.urlsplit(next_url).hostname!="api.massive.com":
            return [],"invalid_pagination_domain"
        url=next_url
    return [],"too_many_pages"


def load_extended_bars(days, today, key):
    start=today-dt.timedelta(days=days)
    end=today-dt.timedelta(days=1)  # no current-session entitlement
    all_raw=[]
    errors=[]
    cursor=start
    while cursor<=end:
        chunk_end=min(cursor+dt.timedelta(days=19),end)
        raw,status=fetch_bars(cursor,chunk_end,key)
        print(cursor,chunk_end,status,len(raw),flush=True)
        if status!="ok": errors.append({"from":cursor.isoformat(),"to":chunk_end.isoformat(),"status":status})
        all_raw.extend(raw)
        cursor=chunk_end+dt.timedelta(days=1)
    bars={}
    for raw in all_raw:
        try:
            ts=dt.datetime.fromtimestamp(raw["t"]/1000,dt.timezone.utc).astimezone(NY)
            if ts.date()>=today or ts.weekday()>=5 or not dt.time(4)<=ts.time()<dt.time(20): continue
            fields={"open":float(raw["o"]),"high":float(raw["h"]),"low":float(raw["l"]),"close":float(raw["c"])}
            if not all(math.isfinite(v) and v>0 for v in fields.values()):continue
            bars[ts.isoformat()]={"timestampET":ts.isoformat(),"dateET":ts.date().isoformat(),"hourET":ts.hour,**fields}
        except (KeyError,ValueError,TypeError,OverflowError): continue
    return list(sorted(bars.values(),key=lambda b:b["timestampET"])),errors


def aggregate(bars, hours):
    groups=defaultdict(list)
    for bar in bars:
        hour=bar["hourET"]
        slot=4+((hour-4)//hours)*hours
        groups[(bar["dateET"],slot)].append(bar)
    out=[]
    for (date,hour),items in sorted(groups.items()):
        items.sort(key=lambda x:x["timestampET"])
        # Only emit complete historical timeframe buckets, never a developing candle.
        # Missing five-minute bars can be normal on low liquidity; an ending bar is
        # required so stale/unfinished session slots cannot masquerade as completed.
        if items[-1]["hourET"]!=hour+hours-1 or int(items[-1]["timestampET"][14:16])!=55:
            continue
        start=dt.datetime.combine(dt.date.fromisoformat(date),dt.time(hour),NY)
        out.append({"startET":start.isoformat(),
                    "endET":(start+dt.timedelta(hours=hours)).isoformat(),
                    "open":items[0]["open"],"high":max(x["high"] for x in items),
                    "low":min(x["low"] for x in items),"close":items[-1]["close"],
                    "underlying5mBars":len(items)})
    return out


def build(days=145, now=None):
    now=now or dt.datetime.now(NY)
    key=os.environ.get("MASSIVE_API_KEY","").strip()
    if not key: raise RuntimeError("MASSIVE_API_KEY missing; no fabricated signals")
    bars,errors=load_extended_bars(days,now.date(),key)
    output={"schemaVersion":1,"symbol":"NVDA","source":"Massive adjusted 5-minute stock aggregates",
            "generatedET":now.isoformat(),"researchOnly":True,"scoringImpact":"none",
            "validationStatus":"not_yet_compared_to_TradingView",
            "session":"04:00-20:00 America/New_York incl extended-hours",
            "boundaryAssumption":"4H blocks 04,08,12,16 ET; 8H blocks 04,12 ET; verify against TradingView",
            "method":"LazyBear WT Cross LB: AP=HLC3; ESA=EMA(AP,10); D=EMA(abs(AP-ESA),10); CI=(AP-ESA)/(0.015*D); WT1=EMA(CI,21); WT2=SMA(WT1,4)",
            "historicalDataEndET":max((b["timestampET"] for b in bars),default=None),
            "underlying5mCount":len(bars),"fetchErrors":errors,"timeframes":{}}
    for hours in (4,8):
        candles=aggregate(bars,hours)
        rows=wavetrend(candles)
        crosses=[{"endET":x["endET"],"direction":x["cross"],"wt1":x["wt1"],"wt2":x["wt2"]}
                 for x in rows if x["cross"]]
        output["timeframes"][str(hours)+"h"]={
            "candleCount":len(candles),"warmupCandles":MIN_HISTORY,
            "firstStartET":candles[0]["startET"] if candles else None,
            "lastEndET":candles[-1]["endET"] if candles else None,
            "latest":rows[-1] if rows and rows[-1]["isWarm"] else None,
            "recentCrosses":crosses[-20:],
            "last20Candles":rows[-20:]}
    return output


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--days",type=int,default=145)
    p.add_argument("--output",default=str(OUT))
    args=p.parse_args()
    document=build(args.days)
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(document,indent=2)+"\n")
    print(json.dumps({k:{"candles":v["candleCount"],"crosses":len(v["recentCrosses"]),
                          "lastEndET":v["lastEndET"],"latest":v["latest"]}
                      for k,v in document["timeframes"].items()},indent=2))
    if document["fetchErrors"]:
        raise SystemExit("Incomplete provider coverage; refusing to publish as validated research")
    if any(v["latest"] is None for v in document["timeframes"].values()):
        raise SystemExit("Insufficient warm-up candles; refusing to publish")


if __name__=="__main__":
    main()
