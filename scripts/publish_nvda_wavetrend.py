#!/usr/bin/env python3
"""Publish only presentation-ready, research-only NVDA WaveTrend observations."""
import json
from pathlib import Path

SOURCE=Path("data/research/nvda-wavetrend.json")
TARGET=Path("public/data/nvda-wavetrend.json")

def publish(src=SOURCE,dst=TARGET):
    original=json.loads(src.read_text())
    if original.get("symbol")!="NVDA" or original.get("fetchErrors"):
        raise ValueError("NVDA WaveTrend source unavailable or incomplete")
    result={"schemaVersion":1,"symbol":"NVDA","generatedET":original.get("generatedET"),
            "historicalDataEndET":original.get("historicalDataEndET"),
            "researchOnly":True,"validationStatus":original.get("validationStatus"),
            "boundaryAssumption":original.get("boundaryAssumption"),"timeframes":{}}
    for tf in ("4h","8h"):
        item=original["timeframes"][tf]
        candles=item["candles"]
        if len(candles)<48 or not all(b.get("isWarm") for b in candles[-48:]):
            raise ValueError(f"Insufficient confirmed {tf} candles")
        # Price/cross observations are copied, never recalculated in the browser.
        result["timeframes"][tf]={"candleCount":item["candleCount"],
            "latest":item["latest"],
            "lastCross":item["crosses"][-1] if item.get("crosses") else None,
            "candles":candles[-48:]}
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,separators=(",",":"))+"\n")
    return result

if __name__=="__main__":
    x=publish()
    print("Published NVDA WT 4H/8H, 48 completed candles each; source:",x["historicalDataEndET"])
