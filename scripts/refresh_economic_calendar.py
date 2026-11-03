#!/usr/bin/env python3
"""Refresh NasDecode's two-week US economic calendar from NasCal's official-source feed.

NasCal is read-only; this script changes only NasDecode. No consensus figures are inferred.
"""
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = os.environ.get(
    "NAS_CAL_SOURCE_URL",
    "https://raw.githubusercontent.com/repural/NasCal/main/data/calendar-live.json"
)
SELECTED_TYPES = {"Macro", "Rates", "Inflation", "Fed", "Politics"}
SOURCE = ROOT / "data/economic-calendar.json"
PUBLIC = ROOT / "public/data/economic-calendar.json"


def build(feed, start):
    end = start + dt.timedelta(days=13)
    events = []
    for e in feed.get("events", []):
        if e.get("type") not in SELECTED_TYPES:
            continue
        date = str(e.get("date", ""))
        if not (start.isoformat() <= date <= end.isoformat()):
            continue
        label = e.get("timeLabel", "")
        m = re.search(r"(?:^| · )(\d{1,2}:\d{2}) ET", label)
        title = e.get("event", "")
        period = re.search(r"\b(October|September|November|December|January|February|March|April|May|June|July|August|Q[1-4])\b", title, re.I)
        events.append({
            "id": e.get("id"), "date": date,
            "timeET": m.group(1) if m else None,
            "timeLabel": label, "report": title,
            "period": period.group(1) if period else None,
            "actual": None, "forecast": None, "previous": None,
            "category": e.get("type"), "importance": e.get("importance", "High"),
            "sourceUrl": e.get("sourceUrl"), "sourceTitle": (e.get("sources") or [{}])[0].get("title", "Official release schedule"),
            "status": e.get("status", "scheduled")
        })
    events.sort(key=lambda x: (x["date"], x["timeET"] or "99:99", x["report"]))
    return {
        "schemaVersion": 1,
        "updatedAt": feed.get("updatedAt"),
        "asOf": start.isoformat(), "windowDays": 14,
        "windowStart": start.isoformat(), "windowEnd": end.isoformat(),
        "source": "NasCal official-source event feed (read-only); actual/consensus not inferred",
        "coverage": "Selected major economic releases and policy events; not a complete commercial calendar",
        "events": events,
    }


def main():
    with urllib.request.urlopen(urllib.request.Request(UPSTREAM, headers={"User-Agent": "NasDecode-Calendar/1.0"}), timeout=25) as response:
        feed = json.load(response)
    if feed.get("schemaVersion") != 1 or not isinstance(feed.get("events"), list):
        raise ValueError("Invalid upstream calendar feed")
    start = dt.datetime.now(ZoneInfo("America/New_York")).date()
    out = build(feed, start)
    if not out["events"]:
        raise ValueError("No events for requested period: fail closed, preserve last good snapshot")
    for path in (SOURCE, PUBLIC):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Published {len(out['events'])} events for {out['windowStart']}–{out['windowEnd']}")


if __name__ == "__main__":
    main()
