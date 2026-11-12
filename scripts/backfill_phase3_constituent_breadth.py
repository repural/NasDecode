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
SOX_2026_SEPT="AMD ADI AMAT ARM ASML ALAB AVGO COHR CRDO ENTG GFS INTC KLAC LRCX LSCC MTSI MRVL MCHP MU MPWR NVDA NXPI ON Q QCOM SITM TSM TER TXN TSEM".split()
SOX_EFFECTIVE="2026-09-21"
SOX_SOURCE="https://beta.indexes.nasdaqomx.com/Index/Weighting/SOX"
SOX_CHANGE_SOURCE="https://etfindexlab.com/phlx-semiconductor-index-rebalance-sox-2026-09-24/"
def official_sox_symbols(date):
 return SOX_2026_SEPT if date>=SOX_EFFECTIVE else None
CORPORATE_ACTIONS={"QRVO":{"lastTradingDate":"2026-10-02","haltDate":"2026-10-05","reason":"Merger into Skyworks Solutions (SWKS)","sourceUrl":"https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2026-702","filingUrl":"https://ir.qorvo.com/static-files/97184275-c23b-40b6-8c00-fab7ad1c2258"}}
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
 for ticker in list(dict.fromkeys(UNIVERSE+SOX_2026_SEPT)):
  series[ticker]=fetch(ticker,key)
  print(ticker,len(series[ticker]),flush=True)
  time.sleep(float(os.environ.get("MASSIVE_REQUEST_INTERVAL_SECONDS","15")))
 dates=sorted(set().union(*(set(x) for x in series.values())))
 records=[]
 for i,d in enumerate(dates):
  if i==0:continue
  prev=dates[i-1]
  active=UNIVERSE
  sox=official_sox_symbols(d)
  # Calculate returns for the current 30-stock basket on every historical date, not only after the reconstitution.
  needed=list(dict.fromkeys(active+SOX_2026_SEPT))
  returns={s:100*(series[s][d]/series[s][prev]-1) for s in needed if d in series[s] and prev in series[s] and series[s][prev]>0}
  def breadth(stocks):
   valid=[returns[s] for s in stocks if s in returns]
   return 100*sum(x>0 for x in valid)/len(valid) if len(valid)==len(stocks) else None
  current_sox_missing=[s for s in SOX_2026_SEPT if s not in returns]
  current_sox_valid=[returns[s] for s in SOX_2026_SEPT if s in returns]
  missing=[s for s in active if s not in returns]
  # A missing ticker invalidates full-universe breadth, rather than silently changing denominator.
  ranked=sorted(((s,returns[s]) for s in active if s in returns),key=lambda kv:kv[1],reverse=True)
  records.append({"date":d,"activeUniverse":active,"soxUniverse":sox,"soxBreadthStatus":("published_snapshot_effective_2026_09_21" if sox else "historical_membership_unverified"),"soxPositiveBreadthPct":breadth(sox) if sox else None,"currentConstituentSoxBreadthPct":breadth(SOX_2026_SEPT),"currentConstituentSoxObservedBreadthPct":(100*sum(v>0 for v in current_sox_valid)/len(current_sox_valid) if current_sox_valid else None),"currentConstituentSoxCoveragePct":100*len(current_sox_valid)/len(SOX_2026_SEPT),"currentConstituentSoxObservedCount":30-len(current_sox_missing),"currentConstituentSoxMissingSymbols":current_sox_missing,"soxObservedCount":sum(s in returns for s in sox) if sox else None,"soxExpectedCount":len(sox) if sox else None,"soxMissingSymbols":[s for s in sox if s not in returns] if sox else None,"proxyPositiveBreadthPct":breadth(active),"fiveStockPositiveBreadthPct":breadth(BASKET),"observedCount":sum(s in returns for s in active),"missingSymbols":missing,"structuralMissingSymbols":[s for s in missing if s in CORPORATE_ACTIONS and d>CORPORATE_ACTIONS[s]["lastTradingDate"]],"expectedCount":len(active),"topFiveAverageReturnPct":sum(v for _,v in ranked[:5])/5 if len(ranked)==len(UNIVERSE) else None,"allConstituentAverageReturnPct":sum(returns[s] for s in active)/len(active) if all(s in returns for s in active) else None,"topFiveContributionShare":None,"verifiedSoxBreadthPct":breadth(sox) if sox else None})
 result={"schemaVersion":1,"status":"research_only","universeType":"fixed_30_stock_research_proxy_separate_from_date_scoped_SOX","universeSource":"scripts/refresh.py SEMI_BREADTH; membership not independently verified","universe":UNIVERSE,"officialSoxMembershipSnapshots":[{"effectiveDate":SOX_EFFECTIVE,"symbols":SOX_2026_SEPT,"source":SOX_SOURCE,"changeEvidence":SOX_CHANGE_SOURCE,"status":"2026_September_reconstitution_snapshot; earlier membership not independently verified"}],"corporateActions":CORPORATE_ACTIONS,"fiveStockBasket":BASKET,"currentConstituentBackfill":{"symbols":SOX_2026_SEPT,"snapshotDate":"2026-10-13","membershipMode":"fixed_current_constituents_applied_retroactively","source":"https://indexes.nasdaqomx.com/Index/Weighting/ESOX","limitations":"Not historical official SOX membership; includes survivorship and look-ahead selection bias; no imputation for pre-listing Q or other missing prices."},"historicalMembershipVerified":False,"priceSource":"Massive adjusted daily aggregates","missingSymbolDiagnostics":"Per-symbol missing returns identify missing current or previous daily close; source does not distinguish no trading from provider gap.","priceWindow":{"start":START,"end":END},"method":"Daily positive close-to-close return; strict breadth requires all 30 constituents; observed breadth divides by available valid-return constituents and is always accompanied by observed count and coverage percent.","records":records,"limitations":["Fixed research proxy is not official SOX breadth and contains survivorship bias.","Do not call proxy breadth SOX constituent breadth or use for historical causal inference.","Concentration by market-cap weight unavailable; top-five contribution share null.","Absent adjusted prices remain missing, never zero-filled.","QRVO ceased trading after 2026-10-02 following its merger; do not synthesize QRVO returns or silently substitute SWKS.","No arbitrary SNDK substitution. SOX breadth uses the published September 2026 membership snapshot only from its effective date; earlier SOX membership is unverified.","Date alignment assumes a shared US equity trading calendar.","Observed-only breadth has changing-denominator selection bias and should be compared with coverage and missing-symbol diagnostics; do not treat it as full 30-stock breadth.","Current-constituent backfill is a fixed October 2026 basket, not historical SOX membership; avoid training historical point-in-time models on it without accounting for look-ahead constituent selection."]}
 OUT.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"sessions":len(records),"fullCoverage":sum(r["proxyPositiveBreadthPct"] is not None for r in records)}))
if __name__=="__main__":main()
