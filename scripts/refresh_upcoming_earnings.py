#!/usr/bin/env python3
"""Maintain the next-14-day earnings calendar for the NasDecode universe.

Primary source: Nasdaq's public earnings-calendar endpoint. Only SOX constituents and
NasDecode mega-caps are retained. Existing manually/officially verified rows are kept
inside the window if Nasdaq is temporarily unavailable.
"""
import datetime as dt
import json, urllib.request, urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UNIVERSE=ROOT/"data"/"catalyst-universe.json"
OUT=ROOT/"data"/"upcoming-earnings.json"
NASDAQ="https://api.nasdaq.com/api/calendar/earnings"

def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def fetch_day(day):
    url=NASDAQ+"?"+urllib.parse.urlencode({"date":day.isoformat()})
    req=urllib.request.Request(url,headers={
        "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/134 Safari/537.36",
        "Accept":"application/json, text/plain, */*",
        "Origin":"https://www.nasdaq.com","Referer":"https://www.nasdaq.com/"
    })
    with urllib.request.urlopen(req,timeout=20) as r:
        payload=json.load(r)
    return ((payload.get("data") or {}).get("rows") or [])

def normalize_session(x):
    s=str(x or "").lower()
    if "before" in s or "pre" in s: return "before_open"
    if "after" in s or "post" in s: return "after_close"
    return "unknown"

def main():
    today=dt.datetime.now(dt.timezone.utc).date()
    end=today+dt.timedelta(days=14)
    u=load(UNIVERSE,{})
    sox=set(u.get("components",[])); mega=set(u.get("megaCaps",[]))
    wanted=sox|mega
    existing=load(OUT,{"events":[]})
    if existing.get("asOfDate")==today.isoformat() and int(existing.get("fetchSuccessfulDays",0) or 0)>=15:
        print("upcoming earnings already refreshed successfully today")
        return
    retained={}
    for e in existing.get("events",[]):
        try: d=dt.date.fromisoformat(e.get("date",""))
        except ValueError: continue
        if today<=d<=end and e.get("ticker") in wanted:
            retained[(e["ticker"],e["date"])]=e

    fetched={}; success_days=0
    for i in range(15):
        day=today+dt.timedelta(days=i)
        try:
            rows=fetch_day(day); success_days+=1
        except Exception as exc:
            print("Nasdaq earnings calendar unavailable",day,repr(exc)); continue
        for row in rows:
            ticker=str(row.get("symbol") or "").strip().upper()
            if ticker not in wanted: continue
            fetched[(ticker,day.isoformat())]={
                "ticker":ticker,
                "company":str(row.get("name") or ticker).strip(),
                "date":day.isoformat(),
                "session":normalize_session(row.get("time")),
                "scope":"sox" if ticker in sox else "mega_cap",
                "status":"scheduled",
                "source":"Nasdaq earnings calendar",
                "sourceUrl":"https://www.nasdaq.com/market-activity/earnings",
                "epsForecast":row.get("epsForecast"),
                "fiscalQuarterEnding":row.get("fiscalQuarterEnding")
            }

    # Nasdaq rows supersede retained rows for the same ticker/date. Retained rows protect
    # confirmed events when the public endpoint is temporarily incomplete.
    # Company-IR-confirmed retained rows are authoritative over generic calendar rows.
    fetched.update(retained)
    events=sorted(fetched.values(),key=lambda e:(e["date"],e["ticker"]))
    out={
        "schemaVersion":1,
        "windowDays":14,
        "asOfDate":today.isoformat(),
        "windowEnd":end.isoformat(),
        "source":"Nasdaq public earnings calendar; confirmed company IR rows may be retained as fallback",
        "fetchSuccessfulDays":success_days,
        "universe":{"soxComponents":sorted(sox),"megaCaps":sorted(mega)},
        "events":events
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"upcoming earnings: {len(events)} SOX/mega-cap events through {end}; {success_days}/15 Nasdaq dates fetched")

if __name__=="__main__":
    main()
