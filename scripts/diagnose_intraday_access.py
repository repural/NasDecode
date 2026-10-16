"""Compare Massive five-minute historical vs current-session entitlement.

Reads the GitHub Actions secret at runtime; never prints a key, response body, or URL.
"""
import datetime as dt
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

NY=ZoneInfo("America/New_York")
SYMBOLS=("NVDA","SOXL")

def probe(symbol,date,key):
    url=f"https://api.massive.com/v2/aggs/ticker/{symbol}/range/5/minute/{date}/{date}?adjusted=true&sort=asc&limit=5000"
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"User-Agent":"NasDecode/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            payload=json.load(response)
            return {"httpStatus":response.status,"providerStatus":payload.get("status"),
                    "count":len(payload.get("results") or []),
                    "requestDate":date}
    except urllib.error.HTTPError as exc:
        return {"httpStatus":exc.code,"providerStatus":"http_error","count":None,"requestDate":date}
    except (OSError,ValueError) as exc:
        return {"httpStatus":None,"providerStatus":"network_or_parse_error","count":None,"requestDate":date}

def compare(now=None,request=None):
    now=now or dt.datetime.now(NY)
    key=os.environ.get("MASSIVE_API_KEY","").strip()
    # Previous trading day and an older trading day, avoiding weekends.
    previous=now.date()-dt.timedelta(days=1)
    while previous.weekday()>=5:previous-=dt.timedelta(days=1)
    older=previous-dt.timedelta(days=5)
    while older.weekday()>=5:older-=dt.timedelta(days=1)
    days={"olderTradingDay":older.isoformat(),"previousTradingDay":previous.isoformat(),
          "currentSession":now.date().isoformat()}
    out={"asOfET":now.isoformat(),"dates":days,"results":{}}
    if not key:
        out["status"]="missing_api_key"
        return out
    request=request or probe
    for symbol in SYMBOLS:
        out["results"][symbol]={label:request(symbol,day,key) for label,day in days.items()}
    out["status"]="completed"
    return out

def main():
    out=compare()
    path=Path("data/research/intraday-access-diagnostic.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,indent=2)+"\n")
    print("Massive 5-minute access comparison (no credentials or response bodies):")
    print(json.dumps(out,indent=2))

if __name__=="__main__":
    main()
