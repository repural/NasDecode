#!/usr/bin/env python3
"""NasDecode two-week economic + technology earnings calendar.

Read NasCal's official-source feed without modifying NasCal. Enrich with a dated,
publicly-observed MarketWatch factual snapshot and NasDecode's own earnings feed.
MarketWatch is not scraped automatically; the snapshot must be refreshed manually
or replaced by an appropriately licensed data feed. Never manufacture consensus.
"""
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = os.environ.get("NAS_CAL_SOURCE_URL",
    "https://raw.githubusercontent.com/repural/NasCal/main/data/calendar-live.json")
CATEGORIES = {"Macro", "Rates", "Inflation", "Fed", "Politics"}
SOURCE = ROOT / "data/economic-calendar.json"
PUBLIC = ROOT / "public/data/economic-calendar.json"
MARKETWATCH = ROOT / "data/marketwatch-calendar-snapshot.json"
EARNINGS = ROOT / "data/upcoming-earnings.json"


def fingerprint(title):
    t = title.lower()
    if "jolts" in t or "job openings" in t: return "jolts"
    if "adp" in t: return "adp"
    if "ism" in t and "services" in t: return "ism-services"
    if "services" in t and "pmi" in t: return "services-pmi"
    if "jobless claims" in t: return "claims"
    if "productivity" in t: return "productivity"
    if "employment report" in t: return "employment"
    if "michigan" in t and ("sentiment" in t or "survey" in t): return "michigan"
    if "cpi" in t and "core" in t and ("m/m" in t or "m-o-m" in t): return "cpi-core-mm"
    if "cpi" in t and "y/y" in t: return "cpi-yy"
    if "cpi" in t: return "cpi-mm"
    if "ppi" in t and "core" in t: return "ppi-core-mm"
    if "ppi" in t and "y/y" in t: return "ppi-yy"
    if "ppi" in t: return "ppi-mm"
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def official_event(e):
    label = e.get("timeLabel", "")
    m = re.search(r"(?:^| · )(\d{1,2}:\d{2}) ET", label)
    title = e.get("event", "")
    period = re.search(r"\b(October|September|November|December|January|February|March|April|May|June|July|August|Q[1-4])\b", title, re.I)
    return {
        "id": e.get("id"), "date": str(e.get("date", "")),
        "timeET": m.group(1) if m else None,
        "timeLabel": label, "report": title,
        "period": period.group(1) if period else None,
        "actual": None, "forecast": None, "previous": None,
        "category": e.get("type"), "importance": e.get("importance", "High"),
        "sourceUrl": e.get("sourceUrl"),
        "sourceTitle": (e.get("sources") or [{}])[0].get("title", "Official release schedule"),
        "status": e.get("status", "scheduled"), "dataOrigin": "NasCal official-source research"
    }


def earnings_event(e):
    when = {"before_open": "Before open", "after_close": "After close",
            "during_market": "During session"}.get(e.get("session"), "Time TBD")
    ticker = e.get("ticker", "")
    return {
        "id": "earnings-" + str(e.get("date", "")) + "-" + ticker,
        "date": str(e.get("date", "")), "timeET": None,
        "timeLabel": when + " ET",
        "report": str(e.get("company") or ticker) + " (" + ticker + ") earnings",
        "period": e.get("fiscalQuarterEnding"),
        "actual": None, "forecast": e.get("epsForecast"), "previous": None,
        "forecastType": "EPS estimate", "category": "Earnings",
        "importance": "Critical" if ticker in {"NVDA","AMD","AVGO","QCOM","ARM","META","GOOGL","AMZN","MSFT","AAPL","TSLA","MU"} else "High",
        "sourceUrl": e.get("sourceUrl"), "sourceTitle": e.get("source", "Nasdaq earnings calendar"),
        "status": e.get("status", "scheduled"), "dataOrigin": "NasDecode earnings feed"
    }


def build(feed, start, snapshot, earnings):
    end = start + dt.timedelta(days=13)
    lo, hi = start.isoformat(), end.isoformat()
    events = []
    for e in snapshot.get("events", []):
        if lo <= str(e.get("date", "")) <= hi:
            item = dict(e)
            item["status"] = "scheduled"
            item["dataOrigin"] = "MarketWatch dated factual snapshot"
            events.append(item)
    seen = {(e["date"], fingerprint(e["report"])) for e in events}
    for e in feed.get("events", []):
        if e.get("type") not in CATEGORIES:
            continue
        item = official_event(e)
        if not lo <= item["date"] <= hi:
            continue
        key = item["date"], fingerprint(item["report"])
        if key in seen:
            continue
        seen.add(key)
        events.append(item)
    for e in earnings.get("events", []):
        if lo <= str(e.get("date", "")) <= hi:
            events.append(earnings_event(e))
    events.sort(key=lambda x: (x["date"], x["timeET"] or "99:99", x["report"]))
    return {
        "schemaVersion": 2, "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "asOf": lo, "windowDays": 14, "windowStart": lo, "windowEnd": hi,
        "source": "NasCal official-source events; MarketWatch dated factual snapshot; NasDecode Nasdaq earnings feed",
        "coverage": "Economic, monetary-policy and related technology-company earnings events; MarketWatch fields are only as current as snapshot date",
        "marketwatchObservedAt": snapshot.get("observedAt"),
        "events": events
    }


def main():
    with urllib.request.urlopen(urllib.request.Request(UPSTREAM, headers={
            "User-Agent": "NasDecode-Economic-Calendar/1.0"}), timeout=25) as res:
        feed = json.load(res)
    if feed.get("schemaVersion") != 1 or not isinstance(feed.get("events"), list):
        raise ValueError("Invalid upstream NasCal feed")
    snapshot = json.loads(MARKETWATCH.read_text(encoding="utf-8"))
    earnings = json.loads(EARNINGS.read_text(encoding="utf-8"))
    start = dt.datetime.now(ZoneInfo("America/New_York")).date()
    out = build(feed, start, snapshot, earnings)
    if not out["events"]:
        raise ValueError("Calendar empty; preserve last good publication")
    # Keep the prior publication timestamp if the substantive dataset is identical.
    # Otherwise every 15-minute check would generate a meaningless commit/deploy.
    if SOURCE.exists():
        try:
            prior = json.loads(SOURCE.read_text(encoding="utf-8"))
            before = {k: v for k, v in prior.items() if k != "updatedAt"}
            after = {k: v for k, v in out.items() if k != "updatedAt"}
            if before == after:
                out["updatedAt"] = prior.get("updatedAt", out["updatedAt"])
        except (OSError, ValueError, TypeError):
            pass
    serialized = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    for path in (SOURCE, PUBLIC):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized, encoding="utf-8")
    print(f"Published {len(out['events'])} calendar entries, {out['windowStart']} to {out['windowEnd']}")


if __name__ == "__main__":
    main()
