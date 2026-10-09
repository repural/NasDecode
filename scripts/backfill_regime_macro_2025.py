#!/usr/bin/env python3
"""Separate 2024-12 through 2025 macro backfill; never alters frozen v3."""
import csv,datetime,io,json,os,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/history/regime-macro-2025.json"
SYMBOLS={"us10y":"DGS10","us2y":"DGS2","vxn":"CBOE:VXN","vix":"VIXCLS","brent":"DCOILBRENTEU","wti":"DCOILWTICO"}
START="2024-12-01";END="2025-12-31"
def fetch(symbol,key):
 url=f"https://api.massive.com/v2/aggs/ticker/{urllib.parse.quote(symbol,safe='')}/range/1/day/{START}/{END}?adjusted=true&sort=asc&limit=50000"
 req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"User-Agent":"NasDecode/1.0"})
 for n in range(6):
  try:
   with urllib.request.urlopen(req,timeout=60) as r: payload=json.load(r)
   return {datetime.datetime.fromtimestamp(x["t"]/1000,datetime.timezone.utc).date().isoformat():float(x["c"]) for x in payload.get("results") or []}
  except urllib.error.HTTPError as e:
   if e.code in (400,403,404):return {}
   if e.code!=429 or n==5:raise
   time.sleep(30*(n+1))
def fetch_fred_spot(series_id):
 """FRED-hosted EIA daily physical spot benchmarks, USD/barrel; not futures."""
 url="https://fred.stlouisfed.org/graph/fredgraph.csv?"+urllib.parse.urlencode({"id":series_id,"cosd":START,"coed":END})
 req=urllib.request.Request(url,headers={"User-Agent":"NasDecode research contact via GitHub"})
 with urllib.request.urlopen(req,timeout=60) as response:
  raw=response.read().decode("utf-8-sig")
 reader=csv.DictReader(io.StringIO(raw))
 if not reader.fieldnames or series_id not in reader.fieldnames:raise ValueError("Unexpected FRED CSV columns")
 values={}
 for row in reader:
  day=row.get("observation_date") or row.get("DATE")
  price=row.get(series_id)
  if not day or not price or price==".":continue
  v=float(price)
  bounds=(0,15) if series_id in ("DGS10","DGS2") else (5,150) if series_id=="VIXCLS" else (30,200)
  if not (bounds[0]<=v<=bounds[1]):raise ValueError(f"Suspicious {series_id} value {v} on {day}")
  values[day]=v
 if len(values)<180:raise ValueError(f"Insufficient {series_id} coverage: {len(values)}")
 return values

def fetch_cboe_vxn():
 """Official Cboe daily historical closing index values; no forward filling."""
 url="https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv"
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 NasDecode research"})
 with urllib.request.urlopen(req,timeout=60) as response:
  raw=response.read().decode("utf-8-sig")
 reader=csv.DictReader(io.StringIO(raw))
 values={}
 for row in reader:
  normalized={k.strip().lower().replace(" ","_"):v for k,v in row.items() if k}
  day=normalized.get("date") or normalized.get("trade_date")
  val=normalized.get("close") or normalized.get("close/last") or normalized.get("closing_value")
  if not day or not val:continue
  try:
   d=datetime.datetime.strptime(day.strip(),"%m/%d/%Y").date().isoformat() if "/" in day else datetime.date.fromisoformat(day.strip()).isoformat()
   price=float(val.replace(",",""))
  except (ValueError,TypeError):continue
  if START<=d<=END and 5<=price<=150:values[d]=price
 if len(values)<180:raise ValueError("Insufficient Cboe VXN historical observations: "+str(len(values)))
 return values

def main():
 series={};source_status={}
 for name,identifier in SYMBOLS.items():
  source=("Cboe official VXN daily history" if name=="vxn" else "FRED:"+identifier)
  try:
   values=fetch_cboe_vxn() if name=="vxn" else fetch_fred_spot(identifier)
   if not values:raise ValueError("No observations returned")
   series[name]=values
   source_status[name]={"status":"verified_source","source":source,"observations":len(values)}
  except (ValueError,KeyError,TimeoutError,urllib.error.URLError,urllib.error.HTTPError) as exc:
   series[name]={}
   source_status[name]={"status":"unavailable","source":source,"observations":0,"reason":str(exc)[:180]}
  print(name,source_status[name],flush=True)
 payload={"schemaVersion":1,"version":"regime-macro-backfill-1.1","start":START,"end":END,
 "source":"FRED official yields/VIX/EIA physical oil spot and Cboe official VXN historical close",
 "availability":"historical completed daily close; not verified for intraday availability",
 "tickers":{k:("CBOE:VXN" if k=="vxn" else "FRED:"+v) for k,v in SYMBOLS.items()},
 "oilInstrumentType":"EIA physical spot benchmark, not rolling futures",
 "oilContractRoll":"not applicable to spot benchmark",
 "series":series,"sourceStatus":source_status,
 "missingPolicy":"Missing symbols/dates remain absent; no forward fill or proxy substitution."}
 OUT.write_text(json.dumps(payload,indent=2)+"\\n")
if __name__=="__main__":main()
