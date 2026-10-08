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
 report={"schemaVersion":1,"status":"not_verified","products":{}}
 for name,term in [("wti","CL"),("brent","BZ")]:
  status,payload=query("/futures/v1/products",{"product_code":term,"limit":100})
  raw=payload.get("results",[]) if isinstance(payload,dict) else []
  items=raw if isinstance(raw,list) else raw.get("products",[]) if isinstance(raw,dict) else []
  print(name,"response keys",list(payload) if isinstance(payload,dict) else [],"result type",type(raw).__name__)
  report["products"][name]={"httpStatus":status,"candidates":[{"product_code":x.get("product_code"),"name":x.get("name"),"exchange":x.get("exchange_code") or x.get("trading_venue")} for x in items],"error":payload.get("error") if isinstance(payload,dict) else None}
  print(name,"HTTP",status,"candidates",len(items))
 report["status"]="discovery_complete" if all(x["httpStatus"]==200 for x in report["products"].values()) else "access_or_api_error"
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
