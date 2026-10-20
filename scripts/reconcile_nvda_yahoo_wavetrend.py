#!/usr/bin/env python3
"""Reconcile saved Yahoo WaveTrend shadow observations against Massive history.

No network calls, no Yahoo requests, no public publication or score changes.
A comparison is recorded only when an exact matching Massive candle exists.
"""
import datetime as dt
import argparse
import json
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
MASSIVE = Path("data/research/nvda-wavetrend.json")
SHADOW = Path("data/research/nvda-wavetrend-yahoo-shadow.json")
METRICS = ("open", "high", "low", "close", "wt1", "wt2")


def reconcile(shadow, massive, now=None):
    now = now or dt.datetime.now(NY)
    if massive.get("symbol") not in ("NVDA", "SOXL") or massive.get("fetchErrors"):
        raise ValueError("Invalid Massive historical archive")
    if shadow.get("symbol") != massive["symbol"] or not shadow.get("researchOnly") or shadow.get("publicationAllowed") is not False:
        raise ValueError("Invalid or non-research Yahoo shadow archive")
    # Preserve timeframes, original observations and research provenance exactly.
    shadow = json.loads(json.dumps(shadow))
    report = {}
    for tf in ("4h", "8h"):
        canonical = {c["startET"]: c for c in massive["timeframes"][tf]["candles"]}
        ledger = shadow.get("observations", {}).get(tf, {})
        samples = []
        for start, yahoo in sorted(ledger.items()):
            baseline = canonical.get(start)
            if baseline is None:
                continue
            item = {"startET": start}
            for metric in METRICS:
                left, right = yahoo.get(metric), baseline.get(metric)
                if left is None or right is None:
                    continue
                item[metric + "Delta"] = round(float(left)-float(right), 6)
                if metric in ("open", "high", "low", "close") and right:
                    item[metric + "DiffPct"] = round(100*(float(left)/float(right)-1), 5)
            item["yahooCross"] = yahoo.get("cross")
            item["massiveCross"] = baseline.get("cross")
            item["crossMatches"] = item["yahooCross"] == item["massiveCross"]
            samples.append(item)
        report[tf] = {
            "matchedCandles": len(samples),
            "crossDisagreements": sum(not x["crossMatches"] for x in samples),
            "samples": samples[-30:],
            "unmatchedYahooCandles": len(ledger) - len(samples),
        }
    shadow["reconciliation"] = report
    shadow["reconciliationCheckedAtET"] = now.isoformat()
    shadow["reconciliationMassiveGeneratedET"] = massive.get("generatedET")
    return shadow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', choices=('NVDA', 'SOXL'), default='NVDA')
    symbol = parser.parse_args().symbol.lower()
    shadow_path = Path('data/research/' + symbol + '-wavetrend-yahoo-shadow.json')
    massive_path = Path('data/research/' + symbol + '-wavetrend.json')
    if not shadow_path.exists():
        print("No Yahoo shadow observations yet; skipping reconciliation")
        return
    massive = json.loads(massive_path.read_text())
    shadow = json.loads(shadow_path.read_text())
    output = reconcile(shadow, massive)
    shadow_path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"checkedAtET": output["reconciliationCheckedAtET"],
                      "massiveGeneratedET": output["reconciliationMassiveGeneratedET"],
                      "timeframes": {k: {"matchedCandles": v["matchedCandles"],
                                         "crossDisagreements": v["crossDisagreements"],
                                         "unmatchedYahooCandles": v["unmatchedYahooCandles"]}
                                     for k, v in output["reconciliation"].items()}}, indent=2))


if __name__ == "__main__":
    main()
