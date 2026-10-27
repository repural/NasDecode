#!/usr/bin/env python3
"""Shadow-only Yahoo 5-minute to Massive historical 4H/8H WaveTrend overlay.

Never writes canonical Massive history, website data, or scores. Yahoo completed
candles must pass strict timestamp coverage and end-of-bar validation.
"""
import datetime as dt
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.probe_yahoo_intraday import NY, get_yahoo, parse_rows
from scripts.research_nvda_wavetrend import wavetrend, crossover_records

BASELINE = Path("data/research/nvda-wavetrend.json")
OUTPUT = Path("data/research/nvda-wavetrend-yahoo-shadow.json")
# Do not accept a just-closed candle until the final 5m bar is safely finalized.
SETTLE_MINUTES = 5
HOURS = (4, 8)


def developing_yahoo_candle(rows, hours, now):
    """Current bucket only; elapsed slots must be contiguous, never gap-filled."""
    now = now.astimezone(NY)
    if now.weekday() >= 5 or not 4 <= now.hour < 20:
        return None
    start = dt.datetime.combine(now.date(), dt.time(4 + (now.hour - 4)//hours*hours), NY)
    end = start + dt.timedelta(hours=hours)
    slots = {}
    for bar in rows:
        stamp = dt.datetime.fromisoformat(bar['timeET'])
        if stamp.tzinfo is None or not start <= stamp <= now or stamp >= end:
            continue
        if stamp.minute % 5 or stamp.second or stamp.microsecond:
            return None
        values = [bar.get(k) for k in ('open', 'high', 'low', 'close')]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in values):
            return None
        o, h, l, c = values
        if not l <= min(o, c) <= max(o, c) <= h:
            return None
        slots[stamp] = bar
    if not slots:
        return None
    latest = max(slots)
    expected = [start + dt.timedelta(minutes=5*i) for i in range(int((latest-start).total_seconds()/300)+1)]
    if any(t not in slots for t in expected):
        return None
    as_of = min(now, latest + dt.timedelta(minutes=5))
    if now - as_of > dt.timedelta(minutes=15):
        return None
    bars = [slots[t] for t in expected]
    return {'startET': start.isoformat(), 'endET': end.isoformat(),
            'asOfET': as_of.isoformat(), 'lastSourceBarET': latest.isoformat(),
            'checkedAtET': now.isoformat(), 'underlying5mBars': len(bars),
            'open': bars[0]['open'], 'high': max(b['high'] for b in bars),
            'low': min(b['low'] for b in bars), 'close': bars[-1]['close'],
            'provider': 'Yahoo developing', 'isConfirmed': False}


def confirmed_yahoo_candles(rows, hours, now):
    """Return complete 5m-grid candles only; never synthesize missing intervals."""
    buckets = defaultdict(dict)
    for bar in rows:
        timestamp = dt.datetime.fromisoformat(bar["timeET"])
        if timestamp.minute % 5 or timestamp.second:
            continue
        start_hour = 4 + (timestamp.hour - 4) // hours * hours
        start = dt.datetime.combine(timestamp.date(), dt.time(start_hour), NY)
        if not (start <= timestamp < start + dt.timedelta(hours=hours)):
            continue
        buckets[start.isoformat()][timestamp.isoformat()] = bar
    confirmed, rejected = [], []
    for key, slots in sorted(buckets.items()):
        start = dt.datetime.fromisoformat(key)
        end = start + dt.timedelta(hours=hours)
        if end + dt.timedelta(minutes=SETTLE_MINUTES) > now:
            rejected.append({"startET": key, "reason": "not_yet_confirmed", "available5m": len(slots)})
            continue
        expected = [(start + dt.timedelta(minutes=5*i)).isoformat() for i in range(hours*12)]
        missing = [x for x in expected if x not in slots]
        if missing:
            rejected.append({"startET": key, "reason": "missing_5m_intervals",
                             "available5m": len(slots), "missingCount": len(missing),
                             "firstMissingET": missing[0]})
            continue
        candles = [slots[x] for x in expected]
        confirmed.append({"startET": key, "endET": end.isoformat(),
                          "open": candles[0]["open"], "high": max(b["high"] for b in candles),
                          "low": min(b["low"] for b in candles),
                          "close": candles[-1]["close"],
                          "underlying5mBars": len(candles), "provider": "Yahoo unofficial 5m"})
    return confirmed, rejected


def build_shadow(baseline, rows, now):
    symbol = baseline.get("symbol")
    if symbol not in ("NVDA", "SOXL") or baseline.get("fetchErrors"):
        raise ValueError("Massive archive missing or invalid")
    report = {"schemaVersion": 1, "symbol": symbol, "checkedAtET": now.isoformat(),
              "researchOnly": True, "publicationAllowed": False,
              "canonicalArchiveModified": False, "provider": "Yahoo unofficial chart API",
              "baseline": "Massive adjusted historical 4H/8H",
              "policy": "append Yahoo only after last Massive candle; strict 5m completeness; no gap fill",
              "validationStatus": "shadow_unverified", "timeframes": {}}
    for hours in HOURS:
        tf = str(hours) + "h"
        historical = baseline["timeframes"][tf]["candles"]
        if len(historical) < 100 or not historical[-1].get("isWarm"):
            raise ValueError("Insufficient Massive warm-up history for " + tf)
        accepted, rejected = confirmed_yahoo_candles(rows, hours, now)
        historical_by_start = {c["startET"]: c for c in historical}
        overlaps = []
        for c in accepted:
            old = historical_by_start.get(c["startET"])
            if old:
                overlaps.append({"startET": c["startET"], "closeDiffPct":
                                 round(100*(c["close"]/old["close"]-1), 5),
                                 "highDiffPct": round(100*(c["high"]/old["high"]-1), 5),
                                 "lowDiffPct": round(100*(c["low"]/old["low"]-1), 5)})
        last_historical_end = dt.datetime.fromisoformat(historical[-1]["endET"])
        newer = [c for c in accepted if dt.datetime.fromisoformat(c["startET"]) >= last_historical_end]
        # Adjacent 4H/8H series must not skip candles after the historical boundary.
        sequential = []
        next_start = last_historical_end
        for candle in newer:
            start = dt.datetime.fromisoformat(candle["startET"])
            # Across trading sessions, jump from 20:00 ET to next 04:00 ET only.
            if start != next_start:
                next_day = (next_start + dt.timedelta(days=1)).date()
                while next_day.weekday() >= 5:
                    next_day += dt.timedelta(days=1)
                expected_next = dt.datetime.combine(next_day, dt.time(4), NY)
                if start != expected_next:
                    rejected.append({"startET": candle["startET"], "reason": "gap_since_baseline",
                                     "expectedStartET": next_start.isoformat(),
                                     "nextTradingSessionET": expected_next.isoformat()})
                    break
            sequential.append(candle)
            next_start = dt.datetime.fromisoformat(candle["endET"])
        combined = wavetrend(historical + sequential)
        latest = combined[-1]
        last_crosses = crossover_records(combined)
        report["timeframes"][tf] = {
            "developingCandle": developing_yahoo_candle(rows, hours, now),
            "massiveLastEndET": historical[-1]["endET"],
            "shadowLastEndET": latest["endET"],
            "newYahooCandles": len(sequential),
            "rejectedYahooCandles": rejected[-20:],
            "overlappingMassiveCandles": len(overlaps),
            "overlapSamples": overlaps[-8:],
            "latest": {k: latest.get(k) for k in ("startET", "endET", "open", "high", "low",
                                                 "close", "wt1", "wt2", "cross", "isWarm")},
            "lastConfirmedCross": last_crosses[-1] if last_crosses else None,
            "yahooCandles": [{k: c.get(k) for k in ("startET", "endET", "open", "high", "low", "close",
                                                   "wt1", "wt2", "cross")}
                             for c in combined[-len(sequential):]] if sequential else [],
        }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', choices=('NVDA', 'SOXL'), default='NVDA')
    symbol = parser.parse_args().symbol
    baseline_path = Path('data/research/' + symbol.lower() + '-wavetrend.json')
    output_path = Path('data/research/' + symbol.lower() + '-wavetrend-yahoo-shadow.json')
    now = dt.datetime.now(NY)
    baseline = json.loads(baseline_path.read_text())
    result, errors = get_yahoo(symbol)
    if result is None:
        report = {"symbol": symbol, "checkedAtET": now.isoformat(), "status": "yahoo_fetch_failed",
                  "researchOnly": True, "publicationAllowed": False, "errors": errors}
    else:
        bars, malformed = parse_rows(result)
        report = build_shadow(baseline, bars, now)
        report["status"] = "ok"
        report["retrievedYahoo5m"] = len(bars)
        report["malformedYahoo5m"] = malformed
        report["fetchErrors"] = errors
    # Retain prior shadow observations for next-day Massive reconciliation.
    # Never overwrite a previously captured Yahoo value for the same startET.
    previous = json.loads(output_path.read_text()) if output_path.exists() else {}
    saved = previous.get("observations", {})
    for tf, data in report.get("timeframes", {}).items():
        ledger = saved.setdefault(tf, {})
        for candle in data.get("yahooCandles", []):
            ledger.setdefault(candle["startET"], candle)
    archive = baseline.get("timeframes", {})
    reconciled = {}
    for tf, ledger in saved.items():
        authoritative = {c["startET"]: c for c in archive.get(tf, {}).get("candles", [])}
        reconciled[tf] = []
        for start, observation in sorted(ledger.items()):
            canonical = authoritative.get(start)
            if not canonical:
                continue
            compare = {"startET": start}
            for metric in ("open", "high", "low", "close", "wt1", "wt2"):
                source = observation.get(metric)
                target = canonical.get(metric)
                if source is not None and target is not None:
                    compare[metric + "Delta"] = round(source - target, 6)
                    if metric in ("open", "high", "low", "close") and target:
                        compare[metric + "DiffPct"] = round(100 * (source / target - 1), 5)
            compare["yahooCross"] = observation.get("cross")
            compare["massiveCross"] = canonical.get("cross")
            compare["crossMatches"] = observation.get("cross") == canonical.get("cross")
            reconciled[tf].append(compare)
        # Keep a bounded 30-calendar-day research record.
        threshold = (now.date() - dt.timedelta(days=30)).isoformat()
        saved[tf] = {k: v for k, v in ledger.items() if k[:10] >= threshold}
    report["observations"] = saved
    report["reconciliation"] = {tf: {"matchedCandles": len(items),
                                    "crossDisagreements": sum(not x["crossMatches"] for x in items),
                                    "samples": items[-24:]}
                                for tf, items in reconciled.items()}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"],
                      "checkedAtET": report["checkedAtET"],
                      "timeframes": {k: {"newYahooCandles": v["newYahooCandles"],
                                         "latest": v["latest"],
                                         "rejected": len(v["rejectedYahooCandles"])}
                                     for k, v in report.get("timeframes", {}).items()}}, indent=2))


if __name__ == "__main__":
    main()
