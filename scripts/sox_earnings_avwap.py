"""SOX earnings AVWAP research diagnostics. Never feeds production scores."""
import datetime as dt
import statistics

def compute(bars, earnings_date, session, *, asof=None, max_anchor_days=130):
    if not earnings_date or session not in ("before_open","after_close"):
        return {"status":"unverified_anchor"}
    day=dt.date.fromisoformat(earnings_date)
    today=asof or dt.date.today()
    if day>today or (today-day).days>max_anchor_days:
        return {"status":"outdated_anchor","earningsDate":earnings_date}
    selected=[]
    for b in bars:
        try:
            date=dt.datetime.fromtimestamp(b["t"]/1000,dt.timezone.utc).date()
            vw=float(b["vw"]); vol=float(b["v"]); close=float(b["c"])
            if vol<=0 or vw<=0 or close<=0: continue
            if (date>day if session=="after_close" else date>=day) and date<=today:
                selected.append((date,vw,vol,close))
        except (KeyError,TypeError,ValueError,OverflowError): continue
    selected.sort(key=lambda x:x[0])
    if not selected: return {"status":"missing_bars","earningsDate":earnings_date}
    pv=volume=0.0; series=[]
    for date,vw,vol,close in selected:
        pv+=vw*vol; volume+=vol
        a=pv/volume
        series.append({"date":date.isoformat(),"avwap":round(a,6),"close":close,
                       "distancePct":round(100*(close/a-1),4)})
    if (today-selected[-1][0]).days>5:
        return {"status":"stale_bars","throughDate":selected[-1][0].isoformat()}
    last=series[-1]
    momentum={str(n)+"d":round(last["distancePct"]-series[-n-1]["distancePct"],4)
              if len(series)>n else None for n in (1,3,5)}
    return {"status":"ok","earningsDate":earnings_date,"releaseSession":session,
            "anchorDate":series[0]["date"],"throughDate":last["date"],
            "sessions":len(series),"avwap":last["avwap"],"close":last["close"],
            "distancePct":last["distancePct"],"above":last["distancePct"]>=0,
            "momentumPp":momentum}

def aggregate(details, universe, basket):
    valid={s:details[s] for s in universe if details.get(s,{}).get("status")=="ok"}
    def metrics(group):
        xs=[valid[s] for s in group if s in valid]
        ds=[x["distancePct"] for x in xs]
        out={"universe":len(group),"covered":len(xs),"coveragePct":round(100*len(xs)/len(group),2) if group else 0,
             "above":sum(v>=0 for v in ds),
             "breadthPct":round(100*sum(v>=0 for v in ds)/len(ds),2) if ds else None,
             "medianDistancePct":round(statistics.median(ds),3) if ds else None,
             "extensionPct":{"above5":round(100*sum(v>5 for v in ds)/len(ds),2) if ds else None,
                              "above10":round(100*sum(v>10 for v in ds)/len(ds),2) if ds else None,
                              "above20":round(100*sum(v>20 for v in ds)/len(ds),2) if ds else None,
                              "p90":round(sorted(ds)[min(len(ds)-1,int(.9*(len(ds)-1)))],3) if ds else None},
             "momentumPp":{}}
        for n in ("1d","3d","5d"):
            vals=[x["momentumPp"][n] for x in xs if x["momentumPp"][n] is not None]
            out["momentumPp"][n]=round(statistics.median(vals),3) if vals else None
        return out
    return {"sox":metrics(universe),"originalBasket":metrics(basket),
            "excluded":{s:details.get(s,{"status":"missing_anchor"}).get("status") for s in universe if s not in valid}}
