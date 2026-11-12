#!/usr/bin/env python3
"""Verify macro Actual values against primary publishers and record measured latency.

Consensus remains the market-survey value captured by refresh_macro_surprises.py.
Actual values are promoted to official_verified only when a primary-source page
matches the release. If a source cannot be reached or parsed, the existing event is
left intact and the model never fabricates a verification.
"""
import datetime as dt
import html
import json
import os
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

ROOT=os.path.dirname(os.path.dirname(__file__))
PATH=os.path.join(ROOT,"data","macro-surprises.json")
NY=ZoneInfo("America/New_York")
UTC=dt.timezone.utc
UA="Mozilla/5.0 (compatible; NasDecode/1.0; macro-primary-source-verifier)"

class TextLinks(HTMLParser):
    def __init__(self):
        super().__init__(); self.text=[]; self.links=[]; self.href=None; self.anchor=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="a":
            self.href=dict(attrs).get("href"); self.anchor=[]
    def handle_data(self,data):
        self.text.append(data)
        if self.href is not None: self.anchor.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self.href is not None:
            self.links.append((re.sub(r"\s+"," "," ".join(self.anchor)).strip(),self.href))
            self.href=None; self.anchor=[]
    def clean_text(self):
        return re.sub(r"\s+"," ",html.unescape(" ".join(self.text))).strip()

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req,timeout=18) as r:
        return r.read().decode("utf-8","replace")

def page(url):
    p=TextLinks(); p.feed(fetch(url)); return p.clean_text(),p.links

def num(pattern,text,flags=re.I):
    m=re.search(pattern,text,flags)
    return float(m.group(1).replace(",","")) if m else None

def page_release_date(text):
    pats=[
      r"(?:embargoed until release at .*?\b|for immediate release:\s*)(?:Monday|Tuesday|Wednesday|Thursday|Friday)?[,]?\s*([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
      r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
      r"\b([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})\b"
    ]
    for pat in pats:
        m=re.search(pat,text,re.I)
        if m:
            try:return dt.datetime.strptime(m.group(1),"%B %d, %Y").date()
            except ValueError: pass
    return None

def official_snapshot():
    out={}
    # BLS Employment Situation: payrolls, unemployment and average hourly earnings.
    try:
        url="https://www.bls.gov/news.release/empsit.nr0.htm"; text,_=page(url); day=page_release_date(text)
        payroll_jobs=num(r"nonfarm payroll employment\s*\(\+?([0-9,.]+)\)",text)
        unemployment=num(r"unemployment rate\s*\(([0-9.]+) percent\)",text)
        wages=num(r"average hourly earnings for all employees.*?(?:rose|increased|edged up).*?or\s+([0-9.]+) percent",text)
        # BLS prose reports payroll changes as an absolute number of jobs (for example
        # "29,000"). NasDecode's NFP consensus/scale are stored in thousands ("K"), so
        # normalize the official Actual to K before comparison. Keeping 29,000 with unit
        # "K" would incorrectly mean 29 million jobs and can reverse the macro signal.
        if payroll_jobs is not None: out["nfp"]=(day,payroll_jobs/1000.0,"K",url)
        if unemployment is not None: out["unemployment"]=(day,unemployment,"%",url)
        if wages is not None: out["ahe-mom"]=(day,wages,"%",url)
    except Exception as e: print("BLS employment verification unavailable:",repr(e))

    # BLS CPI: current headline and core month-over-month readings.
    try:
        url="https://www.bls.gov/news.release/cpi.htm"; text,_=page(url); day=page_release_date(text)
        headline=num(r"Consumer Price Index for All Urban Consumers.*?(?:increased|rose)\s+([0-9.]+) percent on a seasonally adjusted basis",text)
        core=num(r"index for all items less food and energy\s+(?:increased|rose)\s+([0-9.]+) percent",text)
        if headline is not None: out["cpi-mom"]=(day,headline,"%",url)
        if core is not None: out["core-cpi-mom"]=(day,core,"%",url)
    except Exception as e: print("BLS CPI verification unavailable:",repr(e))

    # Census Advance Monthly Retail Trade: headline month-over-month sales.
    try:
        url="https://www.census.gov/retail/sales.html"; text,_=page(url); day=page_release_date(text)
        retail=num(r"sales.*?were\s+\$?[0-9,.]+\s+billion,\s+(?:up|down)\s+([0-9.]+) percent.*?from the previous month",text)
        sign=-1 if re.search(r"sales.*?were\s+\$?[0-9,.]+\s+billion,\s+down\s+[0-9.]+ percent.*?from the previous month",text,re.I) else 1
        if retail is not None: out["retail-sales-mom"]=(day,sign*retail,"%",url)
    except Exception as e: print("Census retail verification unavailable:",repr(e))

    # BEA current releases: discover current PIO and GDP links, then parse the release itself.
    try:
        base="https://www.bea.gov/news/current-releases"; _,links=page(base)
        for label,href in links:
            low=label.lower()
            if "personal income and outlays" in low:
                url=urllib.parse.urljoin(base,href); text,_=page(url); day=page_release_date(text)
                headline=num(r"From the preceding month, the PCE price index.*?increased\s+([0-9.]+) percent",text)
                core=num(r"Excluding food and energy, the PCE price index increased\s+([0-9.]+) percent",text)
                if headline is not None: out["pce-mom"]=(day,headline,"%",url)
                if core is not None: out["core-pce-mom"]=(day,core,"%",url)
                break
        for label,href in links:
            if label.lower().startswith("gdp"):
                url=urllib.parse.urljoin(base,href); text,_=page(url); day=page_release_date(text)
                gdp=num(r"Real gross domestic product \(GDP\) (?:increased|decreased) at an annual rate of\s+([0-9.]+) percent",text)
                if gdp is not None:
                    if re.search(r"Real gross domestic product \(GDP\) decreased at an annual rate",text,re.I): gdp=-gdp
                    key="gdp-adv" if "advance estimate" in text.lower() else ("gdp-2nd" if "second estimate" in text.lower() else "gdp-final")
                    out[key]=(day,gdp,"%",url)
                break
    except Exception as e: print("BEA verification unavailable:",repr(e))

    # ISM: discover the current report links. The landing page always points to the
    # currently published Manufacturing and Services reports.
    try:
        base="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/"
        _,links=page(base)
        reports=[]
        for label,href in links:
            if label.strip().lower()=="view report":
                reports.append(urllib.parse.urljoin(base,href))
        for url in reports[:2]:
            text,_=page(url)
            if "Manufacturing PMI" in text:
                v=num(r"Manufacturing PMI[^0-9]{0,40}([0-9.]+) percent",text)
                if v is None: v=num(r"Manufacturing PMI.*?registered\s+([0-9.]+) percent",text)
                # ISM page URL encodes the report month; release day comes from event ID,
                # so date matching is handled below using the event's scheduled release.
                if v is not None: out["ism-manufacturing"]=(None,v,"",url)
            elif "Services PMI" in text:
                v=num(r"Services PMI.*?registered\s+([0-9.]+) percent",text)
                if v is not None: out["ism-services"]=(None,v,"",url)
    except Exception as e: print("ISM verification unavailable:",repr(e))
    return out

def iso_now():
    return dt.datetime.now(UTC).isoformat().replace("+00:00","Z")

def seconds_since(released_at,observed):
    try:
        a=dt.datetime.fromisoformat(released_at)
        b=dt.datetime.fromisoformat(observed.replace("Z","+00:00"))
        return max(0,round((b-a.astimezone(UTC)).total_seconds()))
    except Exception:return None

def main():
    try:
        with open(PATH,encoding="utf-8") as f: doc=json.load(f)
    except Exception as e:
        print("Macro verification skipped:",repr(e)); return
    snap=official_snapshot(); now=iso_now(); changed=0
    for e in doc.get("events",[]):
        key=str(e.get("id","")).split("-",3)[-1]
        # IDs contain dates plus keys; recover known key by suffix.
        key=next((k for k in sorted(snap,key=len,reverse=True) if str(e.get("id","")).endswith("-"+k)),None)
        if not key: continue
        official_day,value,unit,url=snap[key]
        event_day=str(e.get("releasedAt",""))[:10]
        # For agencies with a release date in the page, never apply a different release.
        if official_day is not None and official_day.isoformat()!=event_day: continue
        # ISM current report must correspond to the event's month; stale prior-month
        # services/manufacturing reports are rejected by the release-date window.
        if official_day is None:
            released=dt.datetime.fromisoformat(e["releasedAt"])
            if abs((dt.datetime.now(NY)-released).total_seconds())>8*86400: continue
        if abs(float(e.get("actual",value))-float(value))>0.051:
            e["calendarActual"]=e.get("actual")
        e["actual"]=value; e["unit"]=unit or e.get("unit","")
        e["verified"]=True; e["sourceMode"]="official_verified"
        e["officialSourceUrl"]=url
        e["officialVerifiedAt"]=e.get("officialVerifiedAt") or now
        e["source"]=f"{e.get('officialSource','Primary publisher')} actual / {e.get('consensusSource','market consensus')}"
        # Latency is only meaningful for observations captured live by the automated
        # calendar path. Never manufacture a multi-day "lag" for historical seeds
        # merely because the verifier was introduced later.
        if e.get("firstObservedAt"):
            e["ingestionLagSeconds"]=seconds_since(e.get("releasedAt"),e["firstObservedAt"])
            e["officialVerificationLagSeconds"]=seconds_since(e.get("releasedAt"),e["officialVerifiedAt"])
        else:
            e["ingestionLagSeconds"]=None
            e["officialVerificationLagSeconds"]=None
            e["latencyTracking"]="pre_tracking_release"
        changed+=1
    doc["lastOfficialVerificationAt"]=now
    doc["latencyDefinition"]={
      "ingestionLagSeconds":"Seconds from scheduled release time to first NasDecode observation.",
      "officialVerificationLagSeconds":"Seconds from scheduled release time to first successful primary-source verification."
    }
    with open(PATH,"w",encoding="utf-8") as f: json.dump(doc,f,indent=2,ensure_ascii=False); f.write("\n")
    print(f"Primary-source macro verification: {changed} observations verified or refreshed.")

if __name__=="__main__": main()
