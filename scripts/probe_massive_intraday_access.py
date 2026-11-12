#!/usr/bin/env python3
"""Read-only Massive 5-minute aggregate entitlement probe for NasDecode WT research.

One dated query each for older historical, previous weekday, and current NY day.
Never logs credentials or raw provider response bodies and never changes market data.
"""
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
OUT = Path("audit-output/massive-intraday-access.json")
BASE = "https://api.massive.com/v2/aggs/ticker/"


def previous_weekday(day):
    day -= dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def check(ticker, day, key, label):
    stamp = day.isoformat()
    url = BASE + urllib.parse.quote(ticker, safe="") + "/range/5/minute/" + stamp + "/" + stamp + "?adjusted=true&sort=asc&limit=5000"
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + key,
        "User-Agent": "NasDecode-Intraday-Access-Probe/1.0",
        "Accept": "application/json",
    })
    record = {"label": label, "ticker": ticker, "sessionDateET": stamp, "barSizeMinutes": 5}
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            doc = json.load(response)
            record["httpStatus"] = response.status
            record["providerStatus"] = doc.get("status")
            bars = doc.get("results") or []
            record["barCount"] = len(bars)
            record["resultsCount"] = doc.get("resultsCount")
            if bars:
                times = sorted(int(x["t"]) for x in bars if x.get("t") is not None)
                if times:
                    record["firstBarET"] = dt.datetime.fromtimestamp(times[0] / 1000, dt.timezone.utc).astimezone(NY).isoformat()
                    record["lastBarET"] = dt.datetime.fromtimestamp(times[-1] / 1000, dt.timezone.utc).astimezone(NY).isoformat()
                    record["extendedHoursBarCount"] = sum(
                        dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).astimezone(NY).time() <
                        dt.time(9, 30) or
                        dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).astimezone(NY).time() >=
                        dt.time(16, 0) for t in times
                    )
            record["access"] = "bars_received" if bars else "no_bars"
    except urllib.error.HTTPError as exc:
        record.update(httpStatus=exc.code, access="denied_or_unavailable" if exc.code in (401, 403) else "http_error")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        record.update(access="connection_or_parse_error", errorType=type(exc).__name__)
    return record


def main():
    now = dt.datetime.now(NY)
    today = now.date()
    old = previous_weekday(today - dt.timedelta(days=20))
    previous = previous_weekday(today)
    result = {
        "schemaVersion": 1,
        "checkedAtET": now.isoformat(),
        "purpose": "Determine Massive access to historical, previous-session, and current 5-minute NVDA bars",
        "probes": [],
        "notes": [
            "HTTP 403 may indicate plan entitlement or a data-access restriction; it does not determine the exact subscription.",
            "Prior weekday is a weekday approximation and may be a market holiday.",
            "No bars during closed hours may be normal. Successful response does not establish realtime entitlement.",
            "Bar timestamps mark provider aggregates, not TradingView 4H/8H candle alignment."
        ]
    }
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    for label,day in (("historical_approx_3_weeks", old), ("previous_weekday", previous), ("current_session", today)):
        if not key:
            result["probes"].append({"label":label,"sessionDateET":day.isoformat(),"access":"missing_api_key"})
        else:
            result["probes"].append(check("NVDA", day, key, label))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
