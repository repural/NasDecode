#!/usr/bin/env python3
"""Conservative Tavily S5FI collector: never publish unverified scraped values."""
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path

OUT = Path("data/history/s5fi-tavily-observations.json")
URLS = [
    "https://www.investing.com/indices/sp-500-stocks-above-50-day-average-historical-data",
    "https://www.barchart.com/stocks/quotes/$S5FI/historical-prices",
]

def extract(urls):
    payload=json.dumps({"urls":urls,"extract_depth":"advanced","include_images":False}).encode()
    req=urllib.request.Request("https://api.tavily.com/extract",data=payload,headers={
        "Authorization":"Bearer "+os.environ["TAVILY_API_KEY"],
        "Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=90) as response:
        return json.load(response)

def candidates(raw):
    # Require an ISO date and nearby percentage on the same text line.
    # Never infer a historical close from a page's headline/current quote.
    rows=[]
    for line in raw.splitlines():
        m=re.search(r"\b(20\d{2}-\d{2}-\d{2})\b.{0,110}?\b(\d{1,2}(?:\.\d{1,3})?|100(?:\.0+)?)\s*%",line)
        if not m:continue
        date,value=m.group(1),float(m.group(2))
        try:dt.date.fromisoformat(date)
        except ValueError:continue
        if 0<=value<=100:rows.append({"date":date,"pctAbove50dma":value})
    return rows


def diagnostic(raw):
    """Sample only date-bearing source lines, never raw pages or secrets."""
    patterns = {
        "iso": r"\\b20\\d{2}[-/]\\d{1,2}[-/]\\d{1,2}\\b",
        "us_numeric": r"\\b\\d{1,2}/\\d{1,2}/20\\d{2}\\b",
        "named_month": r"\\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\\s+\\d{1,2},?\\s+20\\d{2}\\b",
    }
    matches = {name: [] for name in patterns}
    lines = raw.splitlines()
    for line in lines:
        for name, pattern in patterns.items():
            if len(matches[name]) >= 5 or not re.search(pattern, line, re.I):
                continue
            safe = re.sub(r"<[^>]*>", " ", line)
            safe = re.sub(r"https?://\\S+|[\\w.+-]+@[\\w.-]+", "[redacted]", safe)
            safe = re.sub(r"(?i)(?:api[_-]?key|token|secret)\\s*[:=]\\s*\\S+", "[redacted]", safe)
            safe = re.sub(r"[\\x00-\\x1f\\x7f]+", " ", safe)
            safe = re.sub(r"\\s+", " ", safe).strip()[:190]
            if safe and safe not in matches[name]:
                matches[name].append(safe)
    return {"lineCount": len(lines), "datedSamples": matches, "tableLineCount": sum(1 for line in lines if line.lstrip().startswith("|"))}

def main():
    response=extract(URLS)
    result={"schemaVersion":1,"source":"Tavily extract","collectedAtUTC":dt.datetime.now(dt.timezone.utc).isoformat(),
            "status":"unverified","observations":[],"sources":[]}
    bydate={}
    for page in response.get("results",[]):
        url=page.get("url","")
        rows=candidates(page.get("raw_content") or "")
        result["sources"].append({"url":url,"candidateCount":len(rows),"contentLength":len(page.get("raw_content") or ""),"diagnostic":diagnostic(page.get("raw_content") or "")})
        for row in rows:
            bydate.setdefault(row["date"],[]).append((url,row["pctAbove50dma"]))
    for date,entries in sorted(bydate.items()):
        hosts={__import__('urllib.parse',fromlist=['urlparse']).urlparse(u).netloc for u,_ in entries}
        values=[v for _,v in entries]
        if len(hosts)>=2 and max(values)-min(values)<=0.1:
            result["observations"].append({"date":date,"pctAbove50dma":round(sum(values)/len(values),3),"verifiedSources":sorted(hosts)})
    if result["observations"]:result["status"]="cross_verified"
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"verified":len(result["observations"]),"sources":result["sources"]}))
if __name__=="__main__":main()
