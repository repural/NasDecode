#!/usr/bin/env python3
"""Build point-in-time Hype Engine observations for the Resilience Engine.

Phase 1 data only. Hype Pressure is NOT consumed by any production NasDecode score.

Inputs:
- Curated Open Watch history: timestamped material events with expected direction/materiality.
- Upcoming earnings calendar: scheduled attention/anticipation only; earnings are NOT assumed bullish.

Important anti-look-ahead rules:
- Curated news becomes eligible no earlier than firstReported/eventTime.
- Scheduled events are captured prospectively from the currently known calendar.
- Auto-detected catalyst headlines are intentionally excluded from directional pressure until curated.
- Market price reaction is NOT used here. Hype Acceptance/Efficiency belongs to later phases.
"""
import datetime as dt
import json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"history"/"hype-daily.json"
RESILIENCE=ROOT/"data"/"history"/"resilience-daily.json"
WATCH=ROOT/"data"/"history"/"market-watch-events.json"
EARNINGS=ROOT/"data"/"upcoming-earnings.json"

MATERIALITY={"Low":30,"Medium":50,"Medium-High":65,"High":80,"Very High":95}
HALF_LIFE={
    "macro":1.0,"fed-rates":1.0,"oil-geopolitics":1.0,
    "earnings":3.0,"semiconductor-demand":4.0,"ai-infrastructure":5.0,
    "m-and-a":2.0,"partnership":3.0,"contract":3.0,"product":2.0,
}
SOX_RELEVANCE={"Semiconductor sector":1.0,"Semiconductor sector / AI":1.0,
               "Nasdaq-wide":0.75,"Nasdaq-wide macro":0.75}
MACRO_CONTEXT_CATEGORIES={"macro","fed-rates","oil-geopolitics"}
SCHEDULED_IMPORTANCE={"NVDA":95,"TSM":90,"ASML":85,"AVGO":85,"AMD":80,"MU":80}

def load(path,default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def parse_dt(x):
    if not x: return None
    try: return dt.datetime.fromisoformat(str(x).replace("Z","+00:00"))
    except Exception: return None

def direction_value(text):
    s=str(text or "").lower()
    if "positive" in s and "negative" not in s: return 1
    if "negative" in s and "positive" not in s: return -1
    return 0

def relevance(event):
    scope=str(((event.get("expectedImpact") or {}).get("scope") or ""))
    if scope in SOX_RELEVANCE: return SOX_RELEVANCE[scope]
    low=scope.lower()
    if "semiconductor" in low: return 1.0
    if "nasdaq" in low or "technology" in low: return 0.75
    return 0.6

def materiality(event):
    m=str(((event.get("expectedImpact") or {}).get("materiality") or "Medium"))
    return MATERIALITY.get(m,50)

def event_start_date(event):
    # firstReported is the strongest anti-look-ahead boundary in the curated archive.
    fr=event.get("firstReported")
    try: return dt.date.fromisoformat(fr) if fr else None
    except ValueError: pass
    t=parse_dt(event.get("eventTime"))
    return t.date() if t else None

def event_impulse(event, day):
    start=event_start_date(event)
    if not start or day<start: return None
    age=(day-start).days
    hl=HALF_LIFE.get(str(event.get("category") or ""),2.0)
    if age>max(7,int(math.ceil(hl*4))): return None
    d=direction_value(((event.get("expectedImpact") or {}).get("direction")))
    base=materiality(event)*relevance(event)
    decay=0.5**(age/hl)
    signed=d*base*decay
    return {
        "id":event.get("id"),"headline":event.get("headline"),"category":event.get("category"),
        "direction":d,"materiality":materiality(event),"soxRelevance":round(relevance(event),2),
        "ageDays":age,"halfLifeDays":hl,"decay":round(decay,4),
        "signedImpulse":round(signed,2),"source":event.get("source"),
        "eventTime":event.get("eventTime"),"firstReported":event.get("firstReported"),
        "hypeEligible":str(event.get("category") or "") not in MACRO_CONTEXT_CATEGORIES
    }

def saturation(x):
    return round(100*(1-math.exp(-max(0,x)/100)),1)

def net_index(pos,neg):
    # 50 neutral, approaches 100 with dominant positive pressure and 0 with negative pressure.
    return round(50+50*math.tanh((pos-neg)/100),1)

def scheduled_for(day, earnings):
    out=[]
    for e in earnings:
        try: ed=dt.date.fromisoformat(e.get("date",""))
        except ValueError: continue
        delta=(ed-day).days
        if delta<0 or delta>14: continue
        importance=SCHEDULED_IMPORTANCE.get(e.get("ticker"),70 if e.get("scope")=="sox" else 55)
        proximity=round(0.5**(delta/5.0),4)
        out.append({
            "ticker":e.get("ticker"),"company":e.get("company"),"date":e.get("date"),
            "session":e.get("session"),"scope":e.get("scope"),"status":e.get("status"),
            "daysAway":delta,"importance":importance,"proximity":proximity,
            "attentionImpulse":round(importance*proximity,2),
            "direction":None,
            "note":"Scheduled event creates attention only; no bullish/bearish direction is assumed."
        })
    return sorted(out,key=lambda x:(x["daysAway"],-x["importance"],x["ticker"] or ""))

def build_record(day, watch_events, scheduled, observed_at, provenance):
    active=[x for e in watch_events if (x:=event_impulse(e,day)) is not None]
    eligible=[x for x in active if x.get("hypeEligible")]
    macro_context=[x for x in active if not x.get("hypeEligible")]
    pos=sum(max(0,x["signedImpulse"]) for x in eligible)
    neg=sum(max(0,-x["signedImpulse"]) for x in eligible)
    attention=sum(x["attentionImpulse"] for x in scheduled)
    return {
        "date":day.isoformat(),"observedAtUTC":observed_at,"provenance":provenance,
        "news":{
            "activeEventCount":len(active),"positiveImpulseRaw":round(pos,2),
            "negativeImpulseRaw":round(neg,2),"positivePressure":saturation(pos),
            "negativePressure":saturation(neg),"netPressureIndex":net_index(pos,neg),
            "events":eligible,
            "excludedMacroContextEvents":macro_context,
            "note":"Macro/Fed/oil headlines are retained as context but excluded from Hype Pressure to avoid double-counting Phase 2 macro variables."
        },
        "anticipation":{
            "scheduledEventCount":len(scheduled),"attentionRaw":round(attention,2),
            "attentionIndex":saturation(attention),"directionalPressure":None,
            "events":scheduled,
            "note":"Attention is separate from direction. Upcoming earnings are not automatically bullish."
        },
        "candidateInputs":{
            "newsNetPressureIndex":net_index(pos,neg),
            "newsPositivePressure":saturation(pos),"newsNegativePressure":saturation(neg),
            "anticipationAttentionIndex":saturation(attention),
            "directionalAnticipation":None
        },
        "excludedFromInput":{
            "hypeAcceptance":None,"hypeEfficiency":None,
            "note":"Price response is deliberately excluded to avoid circularity; calculated in later phases."
        }
    }

def main():
    now=dt.datetime.now(dt.timezone.utc)
    today=now.date()
    existing=load(OUT,{"records":{}})
    records=existing.get("records") or {}
    watch=load(WATCH,{"events":[]}).get("events") or []
    earnings_doc=load(EARNINGS,{"events":[]})
    earnings=earnings_doc.get("events") or []

    # Safe historical enrichment is limited to timestamped curated Open Watch events.
    # We do not project today's rolling earnings calendar backward into prior sessions.
    resilience=load(RESILIENCE,{"records":{}})
    sessions=sorted((resilience.get("records") or {}).keys())
    for ds in sessions:
        day=dt.date.fromisoformat(ds)
        if any(event_start_date(e) and event_start_date(e)<=day for e in watch):
            records[ds]=build_record(day,watch,[],now.isoformat(timespec="seconds"),
                                     "curated_timestamped_history")

    # Prospective snapshot: preserve what is actually known today, including upcoming events.
    records[today.isoformat()]=build_record(today,watch,scheduled_for(today,earnings),
                                           now.isoformat(timespec="seconds"),
                                           "prospective_point_in_time")

    cutoff=today-dt.timedelta(days=365)
    records={d:records[d] for d in sorted(records) if dt.date.fromisoformat(d)>=cutoff}
    out={
        "schemaVersion":1,"enginePhase":1,"methodologyVersion":"hype-inputs-1.0",
        "purpose":"Point-in-time narrative/catalyst pressure inputs for the future SOX Resilience Engine; not used by current scores.",
        "rules":{
            "directionalNews":"Curated Open Watch semiconductor/narrative catalysts only; materiality x SOX relevance x time decay. Macro/Fed/oil events are context, not Hype Pressure.",
            "scheduledEvents":"Attention/proximity only unless a separately timestamped directional expectation exists.",
            "autoDetectedNews":"Excluded from directional pressure until curated/deduplicated.",
            "priceReaction":"Excluded; Hype Acceptance and Hype Efficiency are later validation outputs."
        },
        "upcomingCalendarAsOf":earnings_doc.get("asOfDate"),
        "records":records
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("hype history:",len(records),"daily observations; today",today)

if __name__=="__main__":
    main()
