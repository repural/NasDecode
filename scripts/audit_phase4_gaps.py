#!/usr/bin/env python3
"""Read-only Phase 4 audit: find missing sessions and price-bar dates; never invent backfills."""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")
STAGES = ("premarket", "early_market", "mid_market", "near_close")

def load(path):
    return json.loads((ROOT/path).read_text(encoding="utf-8"))

def audit(today=None):
    today = today or dt.datetime.now(NY).date()
    source = load("data/research/session-briefs.json")["sessions"]
    public = load("public/data/session-research.json")["sessions"]
    # Audit past sessions only. Today's future checkpoints are not missing.
    past = sorted(d for d in source if d < today.isoformat())
    session_gaps = {d: [stage for stage in STAGES if stage not in source[d] or
                     source[d][stage].get("publicationStatus") != "published"] for d in past}
    session_gaps = {d: gaps for d, gaps in session_gaps.items() if gaps}
    publication_diff = [d for d in sorted(set(source)|set(public))
                        if source.get(d) != public.get(d)]

    bars = {}
    for file in sorted((ROOT/"data/history").glob("*-daily.json")):
        try:
            obj = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(obj.get("bars"), list) or not obj.get("ticker"):
            continue
        days = [b.get("date") for b in obj["bars"] if isinstance(b,dict) and isinstance(b.get("date"),str)]
        bars[obj["ticker"]] = {"file": str(file.relative_to(ROOT)), "dates": set(days),
                               "duplicateDates": len(days)-len(set(days)),
                               "recordCount": len(days), "first": min(days) if days else None,
                               "last": max(days) if days else None}
    reference = bars.get("QQQ", {}).get("dates", set())
    price_gaps = []
    for ticker, b in sorted(bars.items()):
        # Compare only dates after first available observation; listings and vendor coverage vary.
        relevant = {day for day in reference if b["first"] and b["first"] <= day <= (b["last"] or "")}
        missing = sorted(relevant-b["dates"])
        if missing or b["duplicateDates"]:
            price_gaps.append({"ticker":ticker, "missingVsQQQ":missing,
                               "duplicateDates":b["duplicateDates"]})
    truncated = [{"ticker":ticker, "first":b["first"], "last":b["last"],
                  "sessions":b["recordCount"]} for ticker,b in sorted(bars.items())
                 if b["first"] and reference and b["first"] > min(reference)]
    events = load("data/history/market-watch-events.json").get("events",[])
    result = {
        "schemaVersion":1, "auditedUTC":dt.datetime.now(dt.timezone.utc).isoformat(),
        "asOfTradingDate":today.isoformat(), "status":"read_only",
        "research": {"archivedDays":len(source),"missingPastCheckpoints":session_gaps,
                     "sourceVsPublishedMismatchedDates":publication_diff,
                     "limitation":"Only dates present in the archive are checked; missing entire trading dates require an exchange calendar."},
        "dailyBars":{"reference":"QQQ", "referenceSessions":len(reference),
                     "trackedSymbols":len(bars),"missingWithinCoveredDateRanges":price_gaps,
                     "shorterHistoryCandidates":truncated,
                     "limitation":"QQQ is a trading-date proxy, not an official exchange calendar; dates outside a symbol's known range are not classified as missing."},
        "marketWatch":{"storedEvents":len(events),
                       "limitation":"Event-count completeness cannot be established without independent time-stamped source coverage."},
        "backfillPolicy":"Price bars: recover from provider with provenance. Session research: retrospective only, no invented checkpoint quotes. Market events: source-verified, dated.",
    }
    return result

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="audit-output/phase4-gaps.json")
    args=parser.parse_args()
    doc=audit()
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"checkpointGaps":doc["research"]["missingPastCheckpoints"],
                      "priceGapSymbols":len(doc["dailyBars"]["missingWithinCoveredDateRanges"]),
                      "trackedSymbols":doc["dailyBars"]["trackedSymbols"],
                      "publicationMismatches":doc["research"]["sourceVsPublishedMismatchedDates"]}))

if __name__=="__main__":
    main()
