#!/usr/bin/env python3
"""Read-only entitlement and instrument discovery; no prices are published."""
import json,os,urllib.parse,urllib.request,urllib.error
from pathlib import Path
BASE="https://api.massive.com"
OUT=Path(__file__).resolve().parents[1]/"data/history/massive-oil-futures-probe.json"
def query(path,params):
 url=BASE+path+"?"+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers={"Authorization":"Bearer "+os.environ["MASSIVE_API_KEY"],"User-Agent":"NasDecode/1.0"})
 try:
  with urllib.request.urlopen(req,timeout=35) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:
  return e.code,{"error":e.reason,"body":e.read(500).decode("utf-8","replace")}
def main():
 report={"schemaVersion":2,"status":"unverified","products":{}}
 for name,code in [("wti","CL"),("brent","BZ")]:
  status,payload=query("/futures/v1/products",{"product_code":code,"limit":100})
  rows=payload.get("results",[]) if isinstance(payload,dict) else []
  matches=[x for x in rows if x.get("product_code")==code]
  info={"productQueryHttp":status,"returned":len(rows),"exactMatches":matches[:3],
        "firstReturnedCodes":[x.get("product_code") for x in rows[:8]]}
  print(name,"product",status,"returned",len(rows),"exact",len(matches),"first",info["firstReturnedCodes"],flush=True)
  if matches:
   cs,cp=query("/futures/v1/contracts",{"product_code":code,"date":"2026-09-15","active":"true","limit":100})
   contracts=[x for x in cp.get("results",[]) if x.get("product_code")==code] if isinstance(cp,dict) else []
   info["contractsHttp"]=cs
   info["contracts"]=[{"ticker":x.get("ticker"),"name":x.get("name"),"last_trade_date":x.get("last_trade_date"),"trading_venue":x.get("trading_venue")} for x in contracts[:12]]
   print(name,"contracts",cs,len(contracts),"tickers",[x.get("ticker") for x in contracts[:8]],flush=True)
   if contracts:
    ticker=next((x["ticker"] for x in contracts if x.get("ticker") and x.get("last_trade_date","")>="2026-09-15"),None)
    if ticker:
     hs,hp=query("/futures/v1/aggs/"+urllib.parse.quote(ticker,safe=""),{"resolution":"1session","window_start":"2026-09-01","window_end":"2026-09-15","limit":30})
     bars=hp.get("results",[]) if isinstance(hp,dict) else []
     info["historicalProbe"]={"ticker":ticker,"http":hs,"barCount":len(bars),"sample":bars[-2:],"error":hp.get("error") if isinstance(hp,dict) else None}
     print(name,"historical",ticker,hs,"bars",len(bars),"sample",json.dumps(bars[-1:])[:500],flush=True)
  report["products"][name]=info
 report["status"]="validated" if all(v.get("historicalProbe",{}).get("barCount",0)>0 for v in report["products"].values()) else "incomplete"
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(report,indent=2)+"\\n")
if __name__=="__main__":main()
