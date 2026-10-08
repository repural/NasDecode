#!/usr/bin/env python3
"""Separate 2024-12 through 2025 macro backfill; never alters frozen v3."""
import csv,datetime,io,json,os,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/history/regime-macro-2025.json"
SYMBOLS={"us10y":"I:US10Y","us2y":"I:US2Y","vxn":"I:VXN","vix":"I:VIX","brent":None,"wti":None}
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
  if not (30<=v<=200):raise ValueError(f"Suspicious {series_id} price {v} on {day}")
  values[day]=v
 if len(values)<180:raise ValueError(f"Insufficient {series_id} spot coverage: {len(values)}")
 return values

def main():
 key=os.environ["MASSIVE_API_KEY"];series={}
 for name,ticker in SYMBOLS.items():
  series[name]=fetch(ticker,key) if ticker else fetch_fred_spot({"brent":"DCOILBRENTE","wti":"DCOILWTICO"}[name])
  print(name,len(series[name]),flush=True)
  time.sleep(16)
 payload={"schemaVersion":1,"version":"regime-macro-backfill-1.0","start":START,"end":END,
 "source":"Massive aggregates for non-oil; FRED-hosted EIA daily spot oil benchmarks DCOILBRENTE/DCOILWTICO","availability":"historical completed daily close; not verified for intraday availability",
 "tickers":{**SYMBOLS,"brent":"FRED:DCOILBRENTE","wti":"FRED:DCOILWTICO"},"oilInstrumentType":"EIA physical spot benchmark, not rolling futures","oilContractRoll":"not applicable to spot benchmark","series":series,"missingPolicy":"Missing symbols/dates remain absent; do not substitute another instrument silently."}
 OUT.write_text(json.dumps(payload,indent=2)+"\n")
if __name__=="__main__":main()
