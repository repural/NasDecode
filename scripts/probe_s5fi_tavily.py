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
    "https://www.investing.com/indices/s-p-500-stocks-above-50-day-average-historical-data",
    "https://uk.investing.com/indices/s-p-500-stocks-above-50-day-average-historical-data",
    "https://in.investing.com/indices/s-p-500-stocks-above-50-day-average-historical-data",
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
    """Read the first Price column of dated historical table rows, not Change %."""
    rows = {}
    for line in raw.splitlines():
        cols = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cols) < 5:
            continue
        date_text = cols[0]
        date = None
        for fmt in ("%b %d, %Y", "%b %d %Y", "%d/%m/%Y",
                    "%d-%m-%Y", "%Y-%m-%d"):
            try:
                date = dt.datetime.strptime(date_text, fmt).date()
                break
            except ValueError:
                pass
        if date is None or date > dt.datetime.now(dt.timezone.utc).date():
            continue
        try:
            price, opening, high, low = (float(cols[i].replace(",", "")) for i in (1, 2, 3, 4))
        except ValueError:
            continue
        if not (0 <= low <= price <= high <= 100 and 0 <= opening <= 100):
            continue
        rows[date.isoformat()] = {"date": date.isoformat(), "pctAbove50dma": price}
    return list(rows.values())

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
    return {"lineCount": len(lines), "datedSamples": matches, "tableLineCount": sum(1 for line in lines if "|" in line), "tableSamples": [re.sub(r"https?://\\S+", "[url]", line.strip())[:180] for line in lines if "|" in line][:12]}

def main():
    response=extract(URLS)
    result={"schemaVersion":1,"source":"Tavily extract","collectedAtUTC":dt.datetime.now(dt.timezone.utc).isoformat(),
            "status":"unverified","observations":[],"sources":[]}
    bydate={}
    for page in response.get("results",[]):
        url=page.get("url","")
        rows=candidates(page.get("raw_content") or "")
        result["sources"].append({"url":url,"candidateCount":len(rows),"candidateObservations":rows[:35],"contentLength":len(page.get("raw_content") or ""),"diagnostic":diagnostic(page.get("raw_content") or "")})
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
