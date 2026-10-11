#!/usr/bin/env python3
"""Research-only semiconductor constituent breadth backfill (NOT verified SOX membership).
Fetches dated closes for a fixed 30-stock liquid semiconductor proxy and five-stock comparator.
Historical SOX membership must be independently verified before labeling this SOX-wide breadth.
"""
import datetime,json,math,os,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
R=Path(__file__).resolve().parents[1]
OUT=R/"data/history/phase3-constituent-breadth.json"
UNIVERSE="AMD ADI AMAT ARM ASML ALAB AVGO COHR CRDO ENTG GFS INTC KLAC LRCX MTSI MRVL MCHP MU MPWR NVMI NVDA NXPI ON QRVO QCOM RMBS SWKS TSM TER TXN".split()
BASKET="NVDA AMD AVGO TSM MU".split()
START="2024-12-01";END=datetime.date.today().isoformat()
def fetch(ticker,key):
 url="https://api.massive.com/v2/aggs/ticker/"+urllib.parse.quote(ticker,safe="")+"/range/1/day/"+START+"/"+END+"?adjusted=true&sort=asc&limit=50000"
 for attempt in range(5):
  try:
   req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"User-Agent":"NasDecode/phase3-research"})
   with urllib.request.urlopen(req,timeout=60) as resp:payload=json.load(resp)
   if payload.get("status")=="ERROR":raise RuntimeError(str(payload.get("error",payload)))
   return {datetime.datetime.fromtimestamp(x["t"]/1000,datetime.timezone.utc).date().isoformat():float(x["c"]) for x in payload.get("results",[]) if isinstance(x.get("c"),(int,float))}
  except urllib.error.HTTPError as e:
   if e.code!=429 or attempt==4:raise
   time.sleep(30*(attempt+1))
 return {}
def main():
 key=os.environ.get("MASSIVE_API_KEY","").strip()
 if not key:raise RuntimeError("MASSIVE_API_KEY required; refusing to invent historical prices")
 series={}
 for ticker in UNIVERSE:
  series[ticker]=fetch(ticker,key)
  print(ticker,len(series[ticker]),flush=True)
  time.sleep(float(os.environ.get("MASSIVE_REQUEST_INTERVAL_SECONDS","15")))
 dates=sorted(set().union(*(set(x) for x in series.values())))
 records=[]
 for i,d in enumerate(dates):
  if i==0:continue
  prev=dates[i-1]
  returns={s:100*(series[s][d]/series[s][prev]-1) for s in UNIVERSE if d in series[s] and prev in series[s] and series[s][prev]>0}
  def breadth(stocks):
   valid=[returns[s] for s in stocks if s in returns]
   return 100*sum(x>0 for x in valid)/len(valid) if len(valid)==len(stocks) else None
  missing=[s for s in UNIVERSE if s not in returns]
  # A missing ticker invalidates full-universe breadth, rather than silently changing denominator.
  ranked=sorted(returns.items(),key=lambda kv:kv[1],reverse=True)
  records.append({"date":d,"proxyPositiveBreadthPct":breadth(UNIVERSE),"fiveStockPositiveBreadthPct":breadth(BASKET),"observedCount":len(returns),"missingSymbols":missing,"expectedCount":len(UNIVERSE),"topFiveAverageReturnPct":sum(v for _,v in ranked[:5])/5 if len(ranked)==len(UNIVERSE) else None,"allConstituentAverageReturnPct":sum(returns.values())/len(UNIVERSE) if len(returns)==len(UNIVERSE) else None,"topFiveContributionShare":None,"verifiedSoxBreadthPct":None})
 result={"schemaVersion":1,"status":"research_only","universeType":"fixed_30_stock_liquid_semiconductor_proxy_NOT_historical_SOX_membership","universeSource":"scripts/refresh.py SEMI_BREADTH; membership not independently verified","universe":UNIVERSE,"fiveStockBasket":BASKET,"historicalMembershipVerified":False,"priceSource":"Massive adjusted daily aggregates","missingSymbolDiagnostics":"Per-symbol missing returns identify missing current or previous daily close; source does not distinguish no trading from provider gap.","priceWindow":{"start":START,"end":END},"method":"Daily positive close-to-close return; require all 30 constituents observed on current and preceding trading date.","records":records,"limitations":["Current fixed universe creates survivorship and historical membership bias.","Do not call proxy breadth SOX constituent breadth or use for historical causal inference.","Concentration by market-cap weight unavailable; top-five contribution share null.","Absent adjusted prices remain missing, never zero-filled.","Date alignment assumes a shared US equity trading calendar."]}
 OUT.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"sessions":len(records),"fullCoverage":sum(r["proxyPositiveBreadthPct"] is not None for r in records)}))
if __name__=="__main__":main()
