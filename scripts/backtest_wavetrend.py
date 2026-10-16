#!/usr/bin/env python3
"""Research-only $10,000 WT crossover simulation using completed extended-hours bars.

Baseline is last 2025 completed candle close, since 2026-01-01 is a US
market holiday. Every confirmed cross is executed at NEXT available candle
open, while holding NVDA/SOXL or cash. No leverage, short sales, financing,
dividends, taxes, commissions or slippage unless friction specified.
Does not assume intrabar fill at signal price.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

START_DATE="2026-01-01"
INITIAL=10000.0


def simulate(candles, start_date=START_DATE, friction=0.0):
    if not 0 <= friction < 1:
        raise ValueError("friction must be nonnegative and less than 1")
    start=next((i for i,b in enumerate(candles) if b["startET"][:10] >= start_date),None)
    if start is None or start == 0:
        raise ValueError("Missing tradeable start or previous completed candle")
    base=candles[start-1]
    initial_price=base["close"]
    shares=INITIAL/initial_price
    cash=0.0
    trades=[]
    for i in range(start,len(candles)-1):
        signal=candles[i].get("cross")
        if signal not in ("bearish","bullish"):
            continue
        nxt=candles[i+1]
        # Never execute before a bar closes; next bar open is earliest eligible.
        if dt.datetime.fromisoformat(nxt["startET"]) < dt.datetime.fromisoformat(candles[i]["endET"]):
            raise ValueError("Next candle open precedes confirmation timestamp")
        price=nxt["open"]
        if price<=0:
            raise ValueError("Nonpositive next candle open")
        if signal=="bearish" and shares>0:
            cash=shares*price*(1-friction)
            shares=0.0
            action="SELL"
        elif signal=="bullish" and cash>0:
            shares=cash*(1-friction)/price
            cash=0.0
            action="BUY"
        else:
            continue
        trades.append({"action":action,"crossoverCandleStartET":candles[i]["startET"],
                       "confirmedAtET":candles[i]["endET"],"executedAtET":nxt["startET"],
                       "executionPrice":round(price,6),
                       "portfolioValueAfterExecution":round(cash+shares*price,2)})
    final_price=candles[-1]["close"]
    value=cash+shares*final_price
    buy_hold=INITIAL*final_price/initial_price
    return {"startDateRequested":start_date,"referenceDateET":base["endET"],
            "referencePrice":initial_price,"initialInvestment":INITIAL,
            "lastCandleCloseET":candles[-1]["endET"],"lastPrice":final_price,
            "costPerTransactionPct":round(friction*100,4),
            "finalValue":round(value,2),"profit":round(value-INITIAL,2),
            "returnPct":round((value/INITIAL-1)*100,2),
            "buyAndHoldValue":round(buy_hold,2),
            "buyAndHoldReturnPct":round((buy_hold/INITIAL-1)*100,2),
            "finalPosition":"cash" if shares==0 else "shares",
            "numberOfExecutions":len(trades),
            "buys":sum(t["action"]=="BUY" for t in trades),
            "sells":sum(t["action"]=="SELL" for t in trades),
            "executions":trades}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="data/research/soxl-wavetrend.json")
    ap.add_argument("--output",default="data/research/soxl-wavetrend-backtest.json")
    a=ap.parse_args()
    source=json.loads(Path(a.input).read_text())
    if source.get("fetchErrors"):
        raise ValueError("Incomplete provider data")
    out={"schemaVersion":1,"symbol":source["symbol"],
         "sourceResearchGeneratedET":source["generatedET"],
         "historicalDataEndET":source["historicalDataEndET"],
         "researchOnly":True,"validationStatus":source["validationStatus"],
         "assumptions":"Fully invested at prior completed year-end candle close; execute cross at next extended-hours candle open; invest all cash on buys and sell all shares on reds; fractional shares allowed.",
         "limitations":"No independent TradingView numeric verification; historical adjusted extended-hours next-bar fills are idealized. Does not account for spread, price impact, corporate action adjustment differences, dividends or tax.",
         "timeframes":{}}
    for timeframe in ("4h","8h"):
        candles=source["timeframes"][timeframe]["candles"]
        out["timeframes"][timeframe]={
            "zeroCosts":simulate(candles,friction=0),
            "cost10bps":simulate(candles,friction=.001),
            "cost25bps":simulate(candles,friction=.0025)}
    output=Path(a.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(out,indent=2)+"\n")
    for tf,v in out["timeframes"].items():
        print(tf,json.dumps({k:{"value":x["finalValue"],"returnPct":x["returnPct"],
                                    "transactions":x["numberOfExecutions"],"buyHold":x["buyAndHoldValue"]}
                               for k,x in v.items()}))


if __name__=="__main__":
    main()
