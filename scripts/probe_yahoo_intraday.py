#!/usr/bin/env python3
"""Read-only Yahoo intraday coverage probe. Does not publish prices or modify WaveTrend."""
import datetime as dt
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
SYMBOLS = ("NVDA", "SOXL")
OUT = Path("data/research/yahoo-intraday-probe.json")
ARCHIVE = Path("data/research/nvda-wavetrend.json")


def get_yahoo(symbol):
    qs = urllib.parse.urlencode({"interval": "5m", "range": "5d", "includePrePost": "true"})
    errors = []
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = f"https://{host}/v8/finance/chart/{symbol}?{qs}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; NasDecodeResearchProbe/1.0)",
            "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                doc = json.load(response)
            chart = doc.get("chart") or {}
            if chart.get("error"):
                raise ValueError(str(chart["error"]))
            result = (chart.get("result") or [None])[0]
            if not result:
                raise ValueError("empty chart result")
            return result, errors
        except (OSError, ValueError, KeyError) as exc:
            errors.append({"host": host, "type": type(exc).__name__, "message": str(exc)[:160]})
            time.sleep(1)
    return None, errors


def parse_rows(result):
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    rows = {}
    malformed = 0
    for i, stamp in enumerate(timestamps):
        try:
            t = dt.datetime.fromtimestamp(int(stamp), dt.timezone.utc).astimezone(NY)
            if not (dt.time(4) <= t.time() < dt.time(20)):
                continue
            o, h, l, c = (float(quote[k][i]) for k in ("open", "high", "low", "close"))
            if not all(math.isfinite(x) and x > 0 for x in (o, h, l, c)) or h < max(o, c) or l > min(o, c):
                malformed += 1
                continue
            if t.minute % 5:
                malformed += 1
                continue
            rows[t.isoformat()] = {"timeET": t.isoformat(), "dateET": t.date().isoformat(),
                                   "hourET": t.hour, "open": o, "high": h, "low": l, "close": c}
        except (ValueError, TypeError, KeyError, IndexError, OverflowError):
            malformed += 1
    return sorted(rows.values(), key=lambda row: row["timeET"]), malformed


def sessions(rows, now):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["dateET"]].append(row)
    report = []
    for day, bars in sorted(grouped.items()):
        seen = {r["timeET"][11:16] for r in bars}
        # Full 4:00-20:00 ET is 192 five-minute slots, not necessarily all traded.
        expected = {(dt.datetime(2000, 1, 1, 4, 0) + dt.timedelta(minutes=5*i)).strftime("%H:%M")
                    for i in range(192)}
        last = bars[-1]["timeET"]
        report.append({"dateET": day, "bars": len(bars), "coveragePct": round(100*len(seen)/192, 2),
                       "missingSlots": len(expected-seen), "firstBarET": bars[0]["timeET"],
                       "lastBarET": last, "fullSessionComplete": len(expected-seen) == 0,
                       "sessionEnded": now.date() > dt.date.fromisoformat(day) or now.time() >= dt.time(20)})
    return report


def compare_massive(rows):
    if not ARCHIVE.exists():
        return {"status": "archive_missing"}
    doc = json.loads(ARCHIVE.read_text())
    massive = {r["startET"]: r for r in doc.get("timeframes", {}).get("4h", {}).get("candles", [])}
    buckets = defaultdict(list)
    for r in rows:
        slot = 4 + ((r["hourET"] - 4)//4)*4
        buckets[(r["dateET"], slot)].append(r)
    comparisons = []
    for (day, hour), bars in sorted(buckets.items()):
        if len(bars) != 48:
            continue
        first = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hour), NY).isoformat()
        other = massive.get(first)
        if not other:
            continue
        bars.sort(key=lambda x: x["timeET"])
        y = {"open": bars[0]["open"], "high": max(b["high"] for b in bars),
             "low": min(b["low"] for b in bars), "close": bars[-1]["close"]}
        diff_pct = {key: round(100*(y[key]/other[key]-1), 4) for key in y}
        comparisons.append({"startET": first, "yahoo": {k: round(v, 4) for k, v in y.items()},
                            "massive": {k: other[k] for k in y},
                            "diffPct": diff_pct,
                            "maxAbsDiffPct": round(max(abs(v) for v in diff_pct.values()), 4)})
    return {"status": "compared" if comparisons else "no_complete_overlapping_candles",
            "compared4h": len(comparisons), "samples": comparisons[-12:]}


def main():
    now = dt.datetime.now(NY)
    report = {"schemaVersion": 1, "checkedAtET": now.isoformat(),
              "purpose": "research_only_no_publication", "provider": "Yahoo unofficial chart endpoint",
              "symbols": {}}
    for symbol in SYMBOLS:
        raw, errors = get_yahoo(symbol)
        if raw is None:
            report["symbols"][symbol] = {"status": "fetch_failed", "errors": errors}
            continue
        rows, malformed = parse_rows(raw)
        lag_min = round((now - dt.datetime.fromisoformat(rows[-1]["timeET"])).total_seconds()/60, 1) if rows else None
        entry = {"status": "ok" if rows else "no_valid_bars", "bars": len(rows),
                 "malformedBars": malformed, "latestBarET": rows[-1]["timeET"] if rows else None,
                 "latestBarLagMinutes": lag_min, "sessions": sessions(rows, now),
                 "errors": errors, "meta": {key: raw.get("meta", {}).get(key) for key in
                     ("currency", "exchangeName", "instrumentType", "dataGranularity")}}
        if symbol == "NVDA":
            entry["massiveOverlap"] = compare_massive(rows)
        report["symbols"][symbol] = entry
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    # Probe records failures as data; reports do not imply that the feed is suitable.
    if any(v.get("status") != "ok" for v in report["symbols"].values()):
        print("WARNING: at least one symbol lacks valid Yahoo bars")

if __name__ == "__main__":
    main()
