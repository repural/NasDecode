#!/usr/bin/env python3
import json, re
from datetime import date
from pathlib import Path
SRC=Path("data/history/daily.json"); OUT=Path("public/data/chart-history.json")
def number(text,pattern):
    m=re.search(pattern,str(text or ""),re.I)
    return float(m.group(1)) if m else None
def latest(rec,name): return ((rec.get("factors") or {}).get(name) or {}).get("latest")
data=json.loads(SRC.read_text()); out=[]
for day,rec in sorted((data.get("records") or {}).items()):
    try:
        if date.fromisoformat(day).weekday()>=5: continue
    except ValueError: continue
    row={"date":day,
      "nasdaqScore":(rec.get("nasdaqScore") or {}).get("score"),
      "opportunity":(rec.get("opportunityScore") or {}).get("score"),
      "vxn":number(latest(rec,"Nasdaq volatility (VXN / VIX)"),r"VXN\s+([0-9.]+)"),
      "tenY":number(latest(rec,"10Y Treasury Yield"),r"([0-9.]+)%"),
      "twoY":number(latest(rec,"2Y Treasury yield"),r"([0-9.]+)%"),
      "oil":number(latest(rec,"Oil (WTI / Brent)"),r"WTI\s*\$([0-9.]+)"),
      "breadth":number(latest(rec,"Market breadth"),r"\(([0-9.]+)%\)"),
      "semi":number(latest(rec,"Semiconductor leadership"),r"basket\s+([+-]?[0-9.]+)%"),
      "mega":number(latest(rec,"Mega-cap leadership"),r"basket\s+([+-]?[0-9.]+)%"),
      "sp50":number(latest(rec,"S&P 500 50D Breadth / Oversold"),r"([0-9.]+)%\s+above")}
    if any(v is not None for k,v in row.items() if k!="date"): out.append(row)
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps({"schemaVersion":1,"records":out[-10:]},indent=2)+"\n")
print(f"Wrote {OUT} with {len(out[-10:])} trading-session records")
