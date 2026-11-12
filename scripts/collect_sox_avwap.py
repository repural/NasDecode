"""Collect SOX earnings AVWAP independently of the time-critical market refresh."""
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.refresh import massive_daily_bars
from scripts.sox_earnings_avwap import compute, aggregate

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"data/sox_avwap_membership.json"
LATEST=ROOT/"data/sox_avwap_latest.json"
HISTORY=ROOT/"data/history/sox-avwap-daily.json"

def main():
    cfg=json.loads(CFG.read_text())
    day=dt.datetime.now(ZoneInfo("America/New_York")).date()
    details={}
    for ticker in cfg["constituents"]:
        a=cfg["anchors"].get(ticker,{})
        if a.get("verification") not in ("verified","legacy_watchlist_pending_revalidation"):
            details[ticker]={"status":"unverified_anchor"}
            continue
        try:
            date=dt.date.fromisoformat(a["earningsDate"])
            if date>day or (day-date).days>130:
                details[ticker]={"status":"outdated_anchor","earningsDate":a["earningsDate"]}
                continue
            bars=massive_daily_bars(ticker,days=180)
            details[ticker]=compute(bars,a["earningsDate"],a["releaseSession"],asof=day)
            details[ticker]["anchorVerification"]=a.get("verification")
        except Exception as exc:
            print(ticker,"data error",repr(exc))
            details[ticker]={"status":"provider_error"}
    aggreg=aggregate(details,cfg["constituents"],cfg["basket"])
    result={"schemaVersion":1,"asOf":day.isoformat(),"membership":cfg["membership"],
            "indicators":aggreg,"constituents":details,
            "scoringImpact":"none",
            "interpretation":"Research only; legacy basket anchors awaiting updated independent release validation."}
    LATEST.write_text(json.dumps(result,indent=2)+"\n")
    HISTORY.parent.mkdir(parents=True,exist_ok=True)
    hist=json.loads(HISTORY.read_text()) if HISTORY.exists() else {"schemaVersion":1,"records":{}}
    hist.setdefault("records",{})[day.isoformat()]=result
    HISTORY.write_text(json.dumps(hist,indent=2)+"\n")
    print("SOX AVWAP",day,"coverage",aggreg["sox"]["covered"],"/",aggreg["sox"]["universe"],
          "basket",aggreg["originalBasket"]["covered"],"/",aggreg["originalBasket"]["universe"])

if __name__=="__main__": main()
