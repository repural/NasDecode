#!/usr/bin/env python3
"""Read-only entitlement and instrument discovery; no prices are published."""
import json,os,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
BASE="https://api.massive.com"
OUT=Path(__file__).resolve().parents[1]/"data/history/massive-oil-futures-probe.json"
LAST_CALL=0
def query(path,params):
 global LAST_CALL
 url=BASE+path+"?"+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers={"Authorization":"Bearer "+os.environ["MASSIVE_API_KEY"],"User-Agent":"NasDecode/1.0"})
 for attempt in range(4):
  wait=max(0,16-(time.monotonic()-LAST_CALL))
  if wait:time.sleep(wait)
  LAST_CALL=time.monotonic()
  try:
   with urllib.request.urlopen(req,timeout=45) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:
   if e.code==429 and attempt<3:
    retry=e.headers.get("Retry-After")
    try:delay=min(180,max(16,float(retry)))
    except (TypeError,ValueError):delay=30*(attempt+1)
    print("rate limited",path,"retry in",delay,"seconds",flush=True)
    time.sleep(delay)
    continue
   return e.code,{"error":e.reason,"body":e.read(500).decode("utf-8","replace")}
 return 429,{"error":"retry exhausted"}
def main():
 import re
 report={"schemaVersion":3,"status":"incomplete","products":{}}
 for name,code in [("wti","CL"),("brent","BZ")]:
  ps,pp=query("/futures/v1/products",{"product_code":code,"limit":10})
  products=[x for x in pp.get("results",[]) if x.get("product_code")==code] if isinstance(pp,dict) else []
  info={"productHttp":ps,"productMatches":len(products),"productSample":products[:1],"outrightCandidates":[]}
  print(name,"product",ps,"matches",len(products),flush=True)
  # Query exact dated outright tickers directly, never take the first spread contract.
  for month in ("X6","Z6"):
   ticker=code+month
   cs,cp=query("/futures/v1/contracts",{"ticker":ticker,"limit":10})
   candidates=cp.get("results",[]) if isinstance(cp,dict) else []
   exact=[x for x in candidates if x.get("ticker")==ticker and re.fullmatch(re.escape(code)+r"[FGHJKMNQUVXZ][0-9]{1,2}",x.get("ticker",""))]
   item={"ticker":ticker,"contractHttp":cs,"exactMatches":len(exact),"contractMetadata":exact[:1]}
   if exact:
    hs,hp=query("/futures/v1/aggs/"+urllib.parse.quote(ticker,safe=""),{"resolution":"1day","window_start":"2026-09-01","window_end":"2026-09-30","limit":100})
    bars=hp.get("results",[]) if isinstance(hp,dict) else []
    clean=[b for b in bars if b.get("ticker")==ticker and 30<=float(b.get("settlement_price") or b.get("close") or 0)<=200]
    item["historical"]={"http":hs,"bars":len(bars),"plausibleBars":len(clean),"first":clean[:1],"last":clean[-1:],"responseKeys":list(hp) if isinstance(hp,dict) else [],"nextUrlPresent":bool(hp.get("next_url")) if isinstance(hp,dict) else False}
    print(name,ticker,"bars",len(bars),"plausible",len(clean),"http",hs,flush=True)
   else:
    print(name,ticker,"exact contracts",0,"http",cs,"keys",list(cp) if isinstance(cp,dict) else [],flush=True)
   info["outrightCandidates"].append(item)
  report["products"][name]=info
 report["status"]="validated" if all(any(x.get("historical",{}).get("plausibleBars",0)>=5 for x in v["outrightCandidates"]) for v in report["products"].values()) else "incomplete"
 print("FINAL STATUS",report["status"],flush=True)
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(report,indent=2)+"\\n")
if __name__=="__main__":main()
