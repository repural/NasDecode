#!/usr/bin/env python3
"""Read-only index quote comparison: Yahoo unofficial chart vs CNBC public quote endpoint.
Does not replace any production feed or publish prices to public dashboard.
"""
import datetime as dt
import json
import math
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from zoneinfo import ZoneInfo

NY=ZoneInfo("America/New_York")
OUT=Path("data/research/index-provider-probe.json")
SYMBOLS={"nasdaq":{"yahoo":"%5EIXIC","cnbc":".IXIC"},"sp500":{"yahoo":"%5EGSPC","cnbc":".SPX"}}

def fetch_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (NasDecodeResearchProbe/1.0)",
      "Accept":"application/json","Referer":"https://www.cnbc.com/"})
    with urllib.request.urlopen(req,timeout=25) as resp:
        return json.load(resp)

def yahoo(symbol):
    errs=[]
    qs=urllib.parse.urlencode({"range":"5d","interval":"5m","includePrePost":"false"})
    for host in ("query1.finance.yahoo.com","query2.finance.yahoo.com"):
        try:
            doc=fetch_json(f"https://{host}/v8/finance/chart/{symbol}?{qs}")
            ch=doc.get("chart") or {}
            if ch.get("error"): raise ValueError(str(ch["error"]))
            result=(ch.get("result") or [None])[0]
            if not result: raise ValueError("No chart results")
            timestamps=result.get("timestamp") or []
            closes=(((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
            valid=[]
            for t,price in zip(timestamps,closes):
                if price is not None and math.isfinite(float(price)) and float(price)>0:
                    valid.append((int(t),float(price)))
            meta=result.get("meta") or {}
            if not valid: raise ValueError("No valid timestamped prices")
            t,p=valid[-1]
            prior=meta.get("chartPreviousClose") or meta.get("previousClose")
            return {"status":"ok","price":round(p,4),"quoteUTC":dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat(),
              "bars":len(valid),"previousClose":prior,"sourceHost":host,
              "exchangeTimezone":meta.get("exchangeTimezoneName"),
              "marketState":meta.get("marketState"),
              "regularMarketTime":meta.get("regularMarketTime"),
              "errors":errs}
        except (OSError,ValueError,KeyError,IndexError,TypeError) as e:
            errs.append({"host":host,"error":type(e).__name__,"message":str(e)[:150]})
    return {"status":"failed","errors":errs}

def cnbc():
    symbols="|".join(x["cnbc"] for x in SYMBOLS.values())
    params={"symbols":symbols,"requestMethod":"itv","noform":"1",
      "partnerId":"2","fund":"1","exthrs":"1","output":"json","events":"1"}
    url="https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?"+urllib.parse.urlencode(params,safe="|@.")
    doc=fetch_json(url)
    quotes=(doc.get("FormattedQuoteResult") or {}).get("FormattedQuote",[])
    if isinstance(quotes,dict):quotes=[quotes]
    return {x.get("symbol"):x for x in quotes if x.get("symbol")}

def parse_cnbc(q):
    if not q:return {"status":"missing"}
    try:
        price=float(str(q.get("last")).replace(",",""))
        if not math.isfinite(price) or price<=0:raise ValueError("Invalid price")
        return {"status":"ok","price":price,"quoteTimeRaw":q.get("last_timedate") or q.get("last_time"),
                "lastTime":q.get("last_time"),"lastTimeDate":q.get("last_timedate"),
                "previousClose":q.get("previous_day_closing"),
                "code":q.get("code")}
    except (ValueError,TypeError):
        return {"status":"bad_quote","rawTime":q.get("last_timedate") or q.get("last_time")}

def main():
    now=dt.datetime.now(dt.timezone.utc)
    report={"schemaVersion":1,"checkedAtUTC":now.isoformat(),"purpose":"read_only_research",
            "productionFeedChanged":False,"sources":{"yahoo":"Unofficial Yahoo chart endpoint",
            "cnbc":"CNBC public quotes"},"symbols":{}}
    try: quotes=cnbc();cnbc_error=None
    except Exception as e:quotes={};cnbc_error=type(e).__name__+": "+str(e)[:160]
    for name,pair in SYMBOLS.items():
        y=yahoo(pair["yahoo"]);c=parse_cnbc(quotes.get(pair["cnbc"]))
        record={"yahoo":y,"cnbc":c}
        if cnbc_error:record["cnbcError"]=cnbc_error
        if y.get("status")=="ok":
            record["yahooAgeMinutes"]=round((now-dt.datetime.fromisoformat(y["quoteUTC"])).total_seconds()/60,1)
        if y.get("status")=="ok" and c.get("status")=="ok":
            record["rawPriceDiffPct"]=round(100*(y["price"]/c["price"]-1),4)
            record["comparableAtMatchingTimestamp"]=False
            record["note"]="Prices may represent different timestamps; raw difference is not a reconciliation."
        report["symbols"][name]=record
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
