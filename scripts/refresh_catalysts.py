#!/usr/bin/env python3
import datetime as dt
import json, os, re, urllib.request, urllib.error
from pathlib import Path

from market_watch_global import discover_global_candidates

ROOT=Path(__file__).resolve().parents[1]
UNIVERSE_PATH=ROOT/"data"/"catalyst-universe.json"
OUT_PATH=ROOT/"data"/"semiconductor-catalysts.json"
TAVILY_URL="https://api.tavily.com/search"

MATERIAL_TERMS={
  "earnings":4,"guidance":4,"forecast":3,"outlook":3,"buyback":4,"repurchase":4,
  "acquisition":4,"acquire":4,"merger":4,"partnership":3,"contract":3,"deal":3,
  "investment":3,"launch":2,"product":2,"chip":2,"ai":2,"data center":3,
  "export":4,"restriction":4,"license":3,"sanction":4,"investigation":4,
  "lawsuit":3,"settlement":3,"ceo":3,"cfo":3,"resign":3,"appoint":2,
  "customer":2,"order":2,"capacity":2,"pricing":2,"production":2,"supply":2
}
TRUSTED_DOMAINS=(
  "reuters.com","bloomberg.com","cnbc.com","wsj.com","ft.com","marketwatch.com",
  "businesswire.com","prnewswire.com","globenewswire.com","sec.gov"
)
ALIASES={
 "AMD":["advanced micro devices"],"ADI":["analog devices"],"AMAT":["applied materials"],
 "ARM":["arm holdings"],"ASML":["asml"],"ALAB":["astera labs"],"AVGO":["broadcom"],
 "COHR":["coherent"],"CRDO":["credo technology"],"ENTG":["entegris"],"GFS":["globalfoundries"],
 "INTC":["intel"],"KLAC":["kla corp","kla corporation"],"LRCX":["lam research"],
 "MTSI":["macom"],"MRVL":["marvell"],"MCHP":["microchip technology"],"MU":["micron"],
 "MPWR":["monolithic power systems"],"NVMI":["nova ltd","nova measuring"],"NVDA":["nvidia"],
 "NXPI":["nxp semiconductors"],"ON":["on semiconductor","onsemi"],"QRVO":["qorvo"],
 "QCOM":["qualcomm"],"RMBS":["rambus"],"SWKS":["skyworks"],"TSM":["taiwan semiconductor","tsmc"],
 "TER":["teradyne"],"TXN":["texas instruments"],
 "AAPL":["apple"],"MSFT":["microsoft"],"AMZN":["amazon"],"GOOGL":["alphabet","google"],
 "META":["meta platforms"],"TSLA":["tesla"]
}

def load_json(path, default):
    try:
        with open(path,encoding="utf-8") as f: return json.load(f)
    except (OSError,json.JSONDecodeError): return default

def tavily_search(query, days=2, max_results=12):
    key=os.environ.get("TAVILY_API_KEY") or os.environ.get("TAVILY_KEY")
    if not key: raise RuntimeError("TAVILY_API_KEY/TAVILY_KEY missing")
    payload=json.dumps({
      "api_key":key,"query":query,"topic":"news","search_depth":"advanced",
      "days":days,"max_results":max_results,"include_answer":False,
      "include_raw_content":False
    }).encode()
    req=urllib.request.Request(TAVILY_URL,data=payload,headers={"Content-Type":"application/json","User-Agent":"NasDecode/1.0"})
    with urllib.request.urlopen(req,timeout=45) as r:
        return json.load(r).get("results",[])

def mentioned_tickers(text, universe):
    low=text.lower()
    found=[]
    for t in universe:
        aliases=ALIASES.get(t,[])
        if re.search(rf"(?<![A-Z0-9])\$?{re.escape(t)}(?![A-Z0-9])", text):
            found.append(t); continue
        if any(a in low for a in aliases): found.append(t)
    return sorted(set(found))

def materiality(title, content, url):
    t=(title or "").lower(); c=(content or "").lower()
    score=0; reasons=[]
    for term,w in MATERIAL_TERMS.items():
        if term in t:
            score+=w; reasons.append(term)
        elif term in c:
            score+=max(1,w-2)
    if any(d in (url or "").lower() for d in TRUSTED_DOMAINS): score+=2
    if any(x in t for x in ("announces","reports","raises","cuts","wins","launches","invests","acquires","approves")): score+=2
    return score, sorted(set(reasons))

def event_type(text):
    x=text.lower()
    for k,v in [
      ("earnings","earnings"),("guidance","guidance"),("buyback","capital_return"),
      ("repurchase","capital_return"),("acquisition","m_and_a"),("merger","m_and_a"),
      ("partnership","partnership"),("contract","contract"),("export","regulatory"),
      ("restriction","regulatory"),("sanction","regulatory"),("investigation","legal"),
      ("lawsuit","legal"),("launch","product"),("product","product")]:
        if k in x:return v
    return "company_specific"

def normalize_date(s):
    if not s: return dt.datetime.now(dt.timezone.utc).date().isoformat()
    try:
        return dt.datetime.fromisoformat(s.replace("Z","+00:00")).date().isoformat()
    except ValueError:
        return dt.datetime.now(dt.timezone.utc).date().isoformat()

def fingerprint(e):
    base=(e.get("ticker","")+"|"+e.get("date","")+"|"+re.sub(r"\W+"," ",e.get("title","").lower())).strip()
    return re.sub(r"\s+"," ",base)

def main():
    universe=load_json(UNIVERSE_PATH,{})
    sox=universe.get("components",[])
    mega=universe.get("megaCaps",[])
    symbols=list(dict.fromkeys(sox+mega))
    batches=[symbols[i:i+10] for i in range(0,len(symbols),10)]
    discovered=[]
    global_diagnostics={"searchesAttempted":0,"searchesFailed":0,"resultsReturned":0,"resultsQualified":0,"resultsRejected":0,"failures":[]}
    for batch in batches:
        names=[]
        for t in batch:
            names.append(t)
            names.extend(ALIASES.get(t,[])[:1])
        query=' OR '.join(f'"{n}"' for n in names)
        query += ' semiconductor technology major announcement earnings guidance buyback acquisition partnership contract product export restriction'
        try:
            results=tavily_search(query)
        except Exception as e:
            print("Tavily batch failed",batch,type(e).__name__,str(e))
            continue
        for r in results:
            title=str(r.get("title") or "").strip()
            content=str(r.get("content") or "").strip()
            url=str(r.get("url") or "").strip()
            # Attribute an event only when the company/ticker appears in the headline.
            # Body-text matches are too noisy for roundup stories that mention many companies.
            tickers=mentioned_tickers(title,batch)
            if not tickers: continue
            score,reasons=materiality(title,content,url)
            if score<5: continue
            for ticker in tickers:
                discovered.append({
                  "id":f"auto-{normalize_date(r.get('published_date'))}-{ticker}-{abs(hash((title,url)))%100000000:08d}",
                  "date":normalize_date(r.get("published_date")),
                  "release":"during_session",
                  "ticker":ticker,
                  "type":event_type(title+" "+content),
                  "scope":"sector" if ticker in sox else "mega_cap",
                  "title":title[:180],
                  "expectedReadThrough":"Auto-detected major catalyst; verify breadth and relative-price confirmation",
                  "source":url,
                  "autoDetected":True,
                  "materialityScore":score,
                  "materialityReasons":reasons[:6],
                  "discoveredAtUTC":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                })
    # Global semiconductor discovery complements the ticker-centric U.S. scan.
    # It captures material Asia/Europe semiconductor shocks even when no SOX
    # ticker is present in the headline.
    global_rows, global_diagnostics = discover_global_candidates(
        lambda query: tavily_search(query, days=2, max_results=12)
    )
    discovered.extend(global_rows)

    existing=load_json(OUT_PATH,{"schemaVersion":1,"events":[]})
    events=existing.get("events",[])
    seen={fingerprint(e) for e in events}
    for e in sorted(discovered,key=lambda x:(x["date"],x["materialityScore"]),reverse=True):
        fp=fingerprint(e)
        if fp not in seen:
            events.append(e); seen.add(fp)
    cutoff=dt.datetime.now(dt.timezone.utc).date()-dt.timedelta(days=14)
    keep=[]
    for e in events:
        try: d=dt.date.fromisoformat(e.get("date",""))
        except ValueError: d=cutoff
        if e.get("autoDetected"):
            # Company rows retain the strict headline-attribution rule. Global
            # semiconductor rows are market-level events and intentionally do not
            # require a SOX ticker in the headline.
            if e.get("type") != "global-semiconductor":
                ticker=e.get("ticker")
                if ticker not in mentioned_tickers(str(e.get("title") or ""),[ticker] if ticker else []):
                    continue
            if d<cutoff:
                continue
        keep.append(e)
    keep.sort(key=lambda x:(x.get("date",""),x.get("materialityScore",0)),reverse=True)
    out={
      "schemaVersion":2,
      "description":"Semiconductor and mega-cap catalysts. Auto-detected events are retained for reaction/persistence analysis; manual events remain authoritative.",
      "universe":{"soxComponents":sox,"megaCaps":mega},
      "lastDiscoveryUTC":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
      "globalDiscovery":global_diagnostics,
      "events":keep
    }
    OUT_PATH.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(
      f"catalyst monitor: {len(discovered)} candidate rows, {len(keep)} stored events; "
      f"global searches={global_diagnostics['searchesAttempted']} failed={global_diagnostics['searchesFailed']} "
      f"returned={global_diagnostics['resultsReturned']} qualified={global_diagnostics['resultsQualified']}"
    )

if __name__=="__main__":
    main()
