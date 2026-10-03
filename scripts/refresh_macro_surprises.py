#!/usr/bin/env python3
"""Refresh NasDecode Macro Data Impulse inputs from the public U.S. economic calendar.

The calendar supplies actual, previous and consensus values. NasDecode only ingests
explicitly mapped releases with both an actual and a consensus. Unknown releases fail
closed and never enter the model.

Taxonomy:
  inflation -> CPI/PCE price pressure
  labor     -> payroll demand, wage pressure, unemployment/slack
  growth    -> ISM/PMI activity, retail demand, GDP

The signal is deliberately rate-sensitive: positive means the surprise mix is more
supportive for Nasdaq discount rates. Therefore hotter inflation/wages/activity and
stronger payrolls are restrictive; higher unemployment is supportive.
"""

import datetime as dt
import html
import json
import os
import re
import urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

ROOT=os.path.dirname(os.path.dirname(__file__))
PATH=os.path.join(ROOT,"data","macro-surprises.json")
URL="https://tradingeconomics.com/united-states/calendar"
NY=ZoneInfo("America/New_York")
UTC=dt.timezone.utc

# key, calendar label, family, subtype, surprise scale, importance, half-life,
# direction, normal ET release time, official source
RULES=[
 ("nfp","Non Farm Payrolls","labor","payroll_demand",75.0,1.00,5,"higher_is_negative","08:30","U.S. Bureau of Labor Statistics"),
 ("unemployment","Unemployment Rate","labor","labor_slack",0.20,0.75,5,"higher_is_positive","08:30","U.S. Bureau of Labor Statistics"),
 ("ahe-mom","Average Hourly Earnings MoM","labor","wage_pressure",0.10,0.85,7,"higher_is_negative","08:30","U.S. Bureau of Labor Statistics"),
 ("core-cpi-mom","Core Inflation Rate MoM","inflation","core_cpi",0.10,1.00,7,"higher_is_negative","08:30","U.S. Bureau of Labor Statistics"),
 ("cpi-mom","Inflation Rate MoM","inflation","headline_cpi",0.15,0.60,6,"higher_is_negative","08:30","U.S. Bureau of Labor Statistics"),
 ("core-pce-mom","Core PCE Price Index MoM","inflation","core_pce",0.10,1.00,8,"higher_is_negative","08:30","U.S. Bureau of Economic Analysis"),
 ("pce-mom","PCE Price Index MoM","inflation","headline_pce",0.15,0.60,7,"higher_is_negative","08:30","U.S. Bureau of Economic Analysis"),
 ("ism-manufacturing","ISM Manufacturing PMI","growth","manufacturing_activity",1.50,0.60,3,"higher_is_negative","10:00","Institute for Supply Management"),
 ("ism-services","ISM Services PMI","growth","services_activity",1.50,0.75,3,"higher_is_negative","10:00","Institute for Supply Management"),
 ("retail-sales-mom","Retail Sales MoM","growth","consumer_demand",0.50,0.70,4,"higher_is_negative","08:30","U.S. Census Bureau"),
 ("gdp-adv","GDP Growth Rate QoQ Adv","growth","gdp_growth",0.80,0.90,7,"higher_is_negative","08:30","U.S. Bureau of Economic Analysis"),
 ("gdp-2nd","GDP Growth Rate QoQ 2nd","growth","gdp_growth",0.80,0.50,5,"higher_is_negative","08:30","U.S. Bureau of Economic Analysis"),
 ("gdp-final","GDP Growth Rate QoQ Final","growth","gdp_growth",0.80,0.30,4,"higher_is_negative","08:30","U.S. Bureau of Economic Analysis"),
]

class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag=="tr": self.row=[]
        elif tag in ("td","th") and self.row is not None: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in ("td","th") and self.cell is not None and self.row is not None:
            s=html.unescape(" ".join(self.cell))
            s=re.sub(r"\s+"," ",s).strip()
            self.row.append(s); self.cell=None
        elif tag=="tr" and self.row is not None:
            if any(self.row): self.rows.append(self.row)
            self.row=None; self.cell=None

def parse_number(s):
    s=(s or "").replace("®","").replace(",","").strip()
    if not s or s in {"-","—"}: return None,None
    m=re.search(r"([-+]?\d+(?:\.\d+)?)\s*([KMBT%]?)",s,re.I)
    if not m: return None,None
    return float(m.group(1)),m.group(2).upper()

def date_from_row(row):
    for cell in row:
        m=re.search(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+([A-Z][a-z]+)\s+(\d{1,2})\s+(20\d{2})",cell)
        if m:
            try: return dt.datetime.strptime(" ".join(m.groups()),"%A %B %d %Y").date()
            except ValueError: pass
    return None

def event_cell_index(row,label):
    target=label.lower()
    for i,cell in enumerate(row):
        c=re.sub(r"\s+"," ",cell).strip().lower()
        if c==target or c.startswith(target+" "): return i
    return None

def release_timestamp(day,hm):
    h,m=map(int,hm.split(":"))
    return dt.datetime(day.year,day.month,day.day,h,m,tzinfo=NY).isoformat()

def load():
    try:
        with open(PATH,encoding="utf-8") as f: return json.load(f)
    except (OSError,json.JSONDecodeError): return {"schemaVersion":2,"events":[]}

def main():
    doc=load()
    now=dt.datetime.now(UTC)
    last=doc.get("lastCalendarFetchAt")
    if last:
        try:
            age=(now-dt.datetime.fromisoformat(last.replace("Z","+00:00"))).total_seconds()
            if age<12*60:
                print("Macro calendar checked recently; keeping existing observations.")
                return
        except ValueError: pass

    req=urllib.request.Request(URL,headers={
        "User-Agent":"Mozilla/5.0 (compatible; NasDecode/1.0; economic-calendar-refresh)",
        "Accept":"text/html,application/xhtml+xml"
    })
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            body=r.read().decode("utf-8","replace")
    except Exception as e:
        print("Macro calendar refresh unavailable:",repr(e))
        return

    p=TableRows(); p.feed(body)
    current_date=None; found=[]
    for row in p.rows:
        d=date_from_row(row)
        if d:
            current_date=d
            continue
        if current_date is None: continue
        for key,label,family,subtype,scale,importance,half_life,direction,hm,official in RULES:
            idx=event_cell_index(row,label)
            if idx is None: continue
            tail=row[idx+1:]
            # Calendar columns after Event are Actual, Previous, Consensus, Forecast.
            if len(tail)<3: continue
            actual,au=parse_number(tail[0]); consensus,cu=parse_number(tail[2])
            if actual is None or consensus is None: continue
            unit=au or cu
            event={
                "id":f"{current_date.isoformat()}-{key}",
                "name":label,
                "family":family,
                "subtype":subtype,
                "releasedAt":release_timestamp(current_date,hm),
                "actual":actual,"consensus":consensus,"unit":unit,
                "direction":direction,"scale":scale,"importance":importance,
                "halfLifeDays":half_life,
                "verified":True,"sourceMode":"calendar_automated",
                "source":f"{official} actual / Trading Economics consensus",
                "sourceUrl":URL,
                "officialSource":official,
                "consensusSource":"Trading Economics survey consensus"
            }
            found.append(event)
            break

    if not found:
        print("Macro calendar parsed but no mapped releases with actual + consensus were found; preserving file.")
        return

    existing={e.get("id"):e for e in doc.get("events",[]) if e.get("id")}
    for e in found: existing[e["id"]]=e
    cutoff=(dt.datetime.now(NY).date()-dt.timedelta(days=45)).isoformat()
    events=[e for e in existing.values() if str(e.get("releasedAt",""))[:10]>=cutoff]
    events.sort(key=lambda e:e.get("releasedAt",""),reverse=True)

    doc.update({
        "schemaVersion":2,
        "description":"Verified U.S. macro actual-vs-consensus observations used by NasDecode's decaying Macro Data Impulse.",
        "taxonomy":{
            "inflation":"CPI/PCE price pressure",
            "labor":"Payroll demand, wage pressure and unemployment/slack",
            "growth":"ISM/PMI activity, retail demand and GDP growth"
        },
        "signalLens":"Rate-sensitive Nasdaq: positive means the recent surprise mix is more supportive for discount rates; negative means more restrictive.",
        "calendarSource":URL,
        "lastCalendarFetchAt":now.isoformat().replace("+00:00","Z"),
        "events":events
    })
    os.makedirs(os.path.dirname(PATH),exist_ok=True)
    with open(PATH,"w",encoding="utf-8") as f: json.dump(doc,f,indent=2,ensure_ascii=False); f.write("\n")
    print(f"Macro calendar refresh: {len(found)} mapped releases found; {len(events)} retained.")

if __name__=="__main__": main()
