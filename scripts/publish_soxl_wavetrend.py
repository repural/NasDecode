"""Publish confirmed SOXL WT observations, interpretation and comparable simulations."""
import json
from pathlib import Path
import sys
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.wavetrend_presentation import presentation

SOURCE = Path("data/research/soxl-wavetrend.json")
BACKTEST = Path("data/research/soxl-wavetrend-backtest.json")
TARGET = Path("public/data/soxl-wavetrend.json")


def interpretation(source):
    four = source["timeframes"]["4h"]["latest"]
    eight = source["timeframes"]["8h"]["latest"]
    bullish4 = four["wt1"] > four["wt2"]
    bullish8 = eight["wt1"] > eight["wt2"]
    if bullish4 == bullish8:
        text = "Both timeframes are " + ("bullish" if bullish4 else "bearish") + " (WT1 " + ("above" if bullish4 else "below") + " WT2). "
    else:
        text = ("4H is bullish while 8H remains bearish: an early recovery attempt. " if bullish4
                else "4H is bearish while 8H remains bullish: near-term momentum is weakening. ")
    crosses = source["timeframes"]["4h"].get("crosses", [])
    if len(crosses) >= 2 and crosses[-1]["direction"] == "bearish" and crosses[-2]["direction"] == "bullish":
        start = next((i for i, c in enumerate(source["timeframes"]["4h"]["candles"])
                      if c["endET"] == crosses[-2]["endET"]), -100)
        end = next((i for i, c in enumerate(source["timeframes"]["4h"]["candles"])
                    if c["endET"] == crosses[-1]["endET"]), 100)
        if end - start <= 4:
            text += "The latest 4H green crossover reversed to red within one extended trading session. "
    if four["wt1"] < -53:
        text += "4H WT1 is below the -53 oversold guide; an oversold reading alone does not confirm a reversal. "
    if not bullish4:
        text += "A completed 4H green crossover would be an early recovery signal; 8H confirmation would strengthen alignment."
    else:
        text += "Watch whether the completed 4H bullish crossover holds on subsequent candles."
    return text


def publish(src=SOURCE, backtest=BACKTEST, dst=TARGET):
    source = json.loads(src.read_text())
    report = json.loads(backtest.read_text())
    if source.get("symbol") != "SOXL" or source.get("fetchErrors"):
        raise ValueError("SOXL WT source unavailable or incomplete")
    if (report.get("symbol") != "SOXL" or report.get("sourceResearchGeneratedET") != source["generatedET"]
            or report.get("historicalDataEndET") != source["historicalDataEndET"]):
        raise ValueError("SOXL backtest does not match research snapshot")
    source = presentation(source)
    result = {k: source[k] for k in ("symbol", "generatedET", "historicalDataEndET", "validationStatus", "boundaryAssumption")}
    result.update(schemaVersion=1, researchOnly=True, timeframes={})
    for key in ('collectionCheckedAtET', 'collectionStatus', 'massiveHistoricalEndET',
                'displaySource', 'displayThroughET', 'reconciliation'):
        result[key] = source.get(key)
    for tf in ("4h", "8h"):
        series = source["timeframes"][tf]
        candles = series["candles"]
        if len(candles) < 100 or not all(c.get("isWarm") for c in candles[-48:]):
            raise ValueError("Insufficient confirmed " + tf + " history")
        result["timeframes"][tf] = {"candleCount": len(candles), "latest": candles[-1],
            "lastCross": series["crosses"][-1] if series.get("crosses") else None, "candles": candles[-48:],
            "developing": series.get("developing")}
    result["interpretation"] = interpretation(source)
    result["backtest"] = {"startDate": "2026-01-01", "assumptions": report["assumptions"],
        "limitations": report["limitations"], "timeframes": {}}
    for tf, cases in report["timeframes"].items():
        result["backtest"]["timeframes"][tf] = {
            case: {k: v for k, v in values.items() if k != "executions"} for case, values in cases.items()}
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    return result


if __name__ == "__main__":
    result = publish()
    print("Published SOXL WT analysis through", result["historicalDataEndET"])
