"""Lightweight display-only Nasdaq and S&P index/futures quote collector."""
import datetime as dt, json, math, os, pathlib, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
OUT=pathlib.Path("public/data/live-indices.json")
NY=ZoneInfo("America/New_York")
SYMS={"nasdaq":{"future":"NQ=F","cash":"^IXIC"},"sp500":{"future":"ES=F","cash":"^GSPC"}}
def fetch(symbol):
    errors=[]
    for host in ("query1.finance.yahoo.com","query2.finance.yahoo.com"):
        try:
            symbol_path=urllib.parse.quote(symbol,safe="")
            url=f"https://{host}/v8/finance/chart/{symbol_path}?interval=5m&range=2d"
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (NasDecodeMarketQuotes/1.0)","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=15) as r:doc=json.load(r)
            result=(doc.get("chart",{}).get("result") or [None])[0]
            if not result:raise ValueError("missing chart result")
            stamps=result.get("timestamp") or []
            quotes=((result.get("indicators") or {}).get("quote") or [{}])[0]
            valid=[(int(t),float(c)) for t,c in zip(stamps,quotes.get("close") or []) if c is not None and math.isfinite(float(c)) and float(c)>0]
            if not valid:raise ValueError("no timestamped prices")
            stamp,price=valid[-1]
            meta=result.get("meta") or {}
            prev=meta.get("chartPreviousClose") or meta.get("previousClose")
            try:prev=float(prev);prev=prev if math.isfinite(prev) and prev>0 else None
            except (ValueError,TypeError):prev=None
            return {"status":"ok","symbol":symbol,"price":round(price,4),"changePct":round(100*(price/prev-1),3) if prev else None,
                    "referenceClose":prev,"quoteTime":dt.datetime.fromtimestamp(stamp,dt.timezone.utc).isoformat(),
                    "source":"Yahoo Finance (unofficial, potentially delayed)"}
        except (OSError,ValueError,TypeError,IndexError,KeyError) as e:
            errors.append(type(e).__name__+":"+str(e)[:90])
    return {"status":"unavailable","symbol":symbol,"errors":errors}
def main():
    now=dt.datetime.now(dt.timezone.utc)
    local=now.astimezone(NY)
    regular=local.weekday()<5 and dt.time(9,30)<=local.time()<dt.time(16)
    mode="cash" if regular else "future"
    quotes={}
    for name,pair in SYMS.items():
        symbol=pair[mode]
        entry=fetch(symbol)
        if entry["status"]=="ok":
            age=(now-dt.datetime.fromisoformat(entry["quoteTime"])).total_seconds()
            # Futures weekend/halts are shown as stale, never as a live price.
            if age < -120 or age > 1200:entry["status"]="stale"
        entry["instrument"]="Nasdaq Composite" if name=="nasdaq" and regular else "Nasdaq-100 Futures" if name=="nasdaq" else "S&P 500 Index" if regular else "S&P 500 Futures"
        quotes[name]=entry
    report={"schemaVersion":1,"mode":mode,"collectedAt":now.isoformat(),"quotes":quotes}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUT.with_suffix(".json.tmp");tmp.write_text(json.dumps(report,indent=2)+"\n");os.replace(tmp,OUT)
    print(json.dumps(report))
if __name__=="__main__":main()
