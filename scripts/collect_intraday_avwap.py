"""Research-only intraday AVWAP setup snapshots for NVDA and SOXL.

Requires Massive intraday aggregate access. Publishes null/unavailable rather than
substituting delayed CNBC quotes or claiming a confirmed intraday signal.
"""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
NY=ZoneInfo("America/New_York")
SYMBOLS=("NVDA","SOXL")
OUT=ROOT/"data/research/intraday-avwap.json"
PUBLIC=ROOT/"public/data/intraday-avwap.json"
HISTORY=ROOT/"data/history"
LAST_REQUEST=0.0

def fetch_intraday(ticker, day):
    global LAST_REQUEST
    key=os.environ.get("MASSIVE_API_KEY","").strip()
    if not key: return None,"missing_api_key"
    wait=12.5-(time.monotonic()-LAST_REQUEST)
    if LAST_REQUEST and wait>0: time.sleep(wait)
    url=(f"https://api.massive.com/v2/aggs/ticker/{urllib.parse.quote(ticker)}/range/5/minute/"
         f"{day}/{day}?adjusted=true&sort=asc&limit=5000")
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"User-Agent":"NasDecode/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=25) as response: payload=json.load(response)
        LAST_REQUEST=time.monotonic()
    except urllib.error.HTTPError as ex:
        LAST_REQUEST=time.monotonic()
        return None,f"http_{ex.code}"
    except (OSError,ValueError):
        LAST_REQUEST=time.monotonic()
        return None,"network_or_parse_error"
    if payload.get("status") not in ("OK","DELAYED"): return None,"provider_unavailable"
    bars=[]
    for raw in payload.get("results",[]):
        try:
            stamp=dt.datetime.fromtimestamp(float(raw["t"])/1000,dt.timezone.utc).astimezone(NY)
            # Avoid premarket and extended-hours bars in the first implementation.
            if stamp.date().isoformat()!=day or not (dt.time(9,30)<=stamp.time()<dt.time(16)):continue
            if not all(raw.get(k) is not None for k in ("o","h","l","c","v","vw")):continue
            if float(raw["v"])<=0:continue
            bars.append({"timestampET":stamp.isoformat(),"open":float(raw["o"]),"high":float(raw["h"]),
                         "low":float(raw["l"]),"close":float(raw["c"]),"volume":float(raw["v"]),
                         "vwap":float(raw["vw"])})
        except (ValueError,TypeError,OverflowError,KeyError): continue
    bars.sort(key=lambda b:b["timestampET"])
    return bars,("ok" if bars else "no_regular_session_bars")

def read_history(ticker):
    try:
        doc=json.loads((HISTORY/f"{ticker.lower()}-daily.json").read_text())
        return doc.get("bars",[])
    except (ValueError,OSError):
        return []

def historical_anchors(bars,day):
    old=[b for b in bars if b.get("date","")<day and
         all(b.get(k) is not None for k in ("high","low","vwap","volume")) and b["volume"]>0]
    window=old[-63:]
    if len(window)<45:return {},{}
    indices={"highestHigh":max(range(len(window)),key=lambda i:window[i]["high"]),
             "lowestLow":min(range(len(window)),key=lambda i:window[i]["low"])}
    totals={}
    anchors={}
    for label,index in indices.items():
        seq=window[index:]
        weighted=sum(b["vwap"]*b["volume"] for b in seq)
        volume=sum(b["volume"] for b in seq)
        totals[label]={"weighted":weighted,"volume":volume,"date":seq[0]["date"]}
        anchors[label]={"anchorDate":seq[0]["date"],"priorCloseAvwap":round(weighted/volume,4)}
    return anchors,totals

def evaluate(bars,totals):
    """Bar-close reaction heuristic. 5-minute bars cannot prove tick-level order."""
    if not bars or not totals:return {"status":"unavailable","signals":[]}
    cumulative_weight=0.0;cumulative_volume=0.0
    history={}
    for label in totals:history[label]=[]
    for bar in bars:
        cumulative_weight+=bar["vwap"]*bar["volume"]
        cumulative_volume+=bar["volume"]
        for name,acc in totals.items():
            value=(acc["weighted"]+cumulative_weight)/(acc["volume"]+cumulative_volume)
            history[name].append(value)
    last=bars[-1]
    signals=[]
    for name,values in history.items():
        level=values[-1]
        touch_indices=[i for i,b in enumerate(bars) if b["low"]<=values[i]<=b["high"]]
        confirmed=(len(touch_indices)>0 and
                   any(i>touch_indices[-1] and bars[i]["close"]>values[i]
                       for i in range(touch_indices[-1]+1,len(bars))))
        failed=bool(touch_indices) and last["close"]<level
        proximity=abs(last["close"]/level-1)*100<=1.5
        phase=("failed_touch" if failed else "bounce_follow_through_5m" if confirmed
               else "touch_detected" if touch_indices else "approaching" if proximity else "no_setup")
        signals.append({"anchor":name,"phase":phase,"avwap":round(level,4),
                        "priceDistancePct":round((last["close"]/level-1)*100,3),
                        "touchBars":len(touch_indices)})
    previous_high=max(b["high"] for b in bars[:-1]) if len(bars)>1 else None
    breakout=previous_high is not None and last["close"]>previous_high
    return {"status":"developing_intraday","signals":signals,
            "momentumBreakout5m":breakout,
            "lastBarTimestampET":last["timestampET"],"barsObserved":len(bars),
            "limitations":"5-minute aggregates; signals not tick-level or order-flow confirmed"}

def run(now=None):
    now=now or dt.datetime.now(NY)
    day=now.date().isoformat()
    doc={"schemaVersion":1,"asOfET":now.isoformat(),"sessionDate":day,
         "timeframe":"5-minute regular session","researchOnly":True,"scoringImpact":"none","tickers":{}}
    for ticker in SYMBOLS:
        history=read_history(ticker)
        anchors,totals=historical_anchors(history,day)
        observations,state=fetch_intraday(ticker,day)
        if observations is None or not observations:
            doc["tickers"][ticker]={"status":state,"anchors":anchors,"intraday":None}
            continue
        doc["tickers"][ticker]={"status":state,"anchors":anchors,
                               "intraday":evaluate(observations,totals)}
    for path in (OUT,PUBLIC):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(doc,indent=2)+"\n")
    return doc

if __name__=="__main__":
    result=run()
    print("Intraday AVWAP statuses",[(k,v["status"]) for k,v in result["tickers"].items()])
