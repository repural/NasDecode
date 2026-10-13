"""Daily-bar Shannon-inspired setup diagnostics; research-only, not trade signals."""
import datetime
from itertools import combinations

def assess(window, anchors, price, relative_volume, momentum):
    def date(bar):
        return datetime.datetime.fromtimestamp(bar["t"]/1000,datetime.timezone.utc).date().isoformat()
    def series(anchor):
        start=anchor.get("anchorDate")
        seq=[b for b in window if date(b)>=start] if start else []
        total=0.0
        volume=0.0
        result={}
        for b in seq:
            v=float(b["v"]);volume+=v;total+=float(b["vw"])*v
            result[date(b)]=total/volume
        return result
    histories={name:series(a) for name,a in anchors.items()}
    today=date(window[-1]); yesterday=date(window[-2])
    low=float(window[-1]["l"]);close=float(window[-1]["c"])
    near=[name for name,a in anchors.items() if a["avwap"]>0
          and abs(price/a["avwap"]-1)<=0.015]
    touched=[name for name,history in histories.items() if today in history
             and low<=history[today]<=float(window[-1]["h"])]
    defended=[name for name in touched if close>=histories[name][today]
              and close>float(window[-1]["o"])]
    failed=[name for name in touched if close<histories[name][today]]
    reaction="bounce_confirmed_daily_proxy" if defended else (
        "failed_touch_daily_proxy" if failed else "touch_detected" if touched else
        "approaching" if near else "no_setup")
    # A separate aggressive touch detection is retained; the conservative confirmation
    # is a same-session green close above the relevant AVWAP, not intraday sequencing.
    touch={"name":"Buy the Touch","state":"match" if defended else "watch" if touched or near else "no_match",
           "phase":reaction,"aggressiveTouch":bool(touched),
           "conservativeDailyReaction":bool(defended),
           "evidence":"Daily high/low crosses AVWAP; green close above = daily bounce proxy. No intraday ordering confirmation.",
           "availability":"daily_proxy"}
    crossed=[name for name,h in histories.items()
             if yesterday in h and today in h
             and float(window[-2]["c"])<h[yesterday] and close>=h[today]]
    pullback={"name":"Pullbacks and Breakouts",
              "state":"match" if crossed or momentum else "no_match",
              "reclaimedAnchors":crossed,"breakout":bool(momentum),
              "evidence":"Prior close below its own date's AVWAP and latest close above latest AVWAP, or daily momentum breakout",
              "availability":"daily_proxy"}
    pairs=[]
    for (a,ah),(b,bh) in combinations(histories.items(),2):
        if today not in ah or today not in bh or yesterday not in ah or yesterday not in bh:continue
        diff=abs(ah[today]-bh[today])/min(ah[today],bh[today])*100
        prior=abs(ah[yesterday]-bh[yesterday])/min(ah[yesterday],bh[yesterday])*100
        pairs.append({"anchors":[a,b],"distancePct":round(diff,3),
                      "previousDistancePct":round(prior,3),"converging":diff<prior,
                      "close":diff<=1.5})
    near_any=any(abs(price/a["avwap"]-1)<=0.015 for a in anchors.values())
    matched=[p for p in pairs if p["close"] and p["converging"] and near_any]
    pinch={"name":"AVWAP Pinch","state":"match" if matched else "watch" if any(p["close"] for p in pairs) else "no_match",
           "pairs":pairs,"evidence":"All available anchor pairs: <=1.5% separation, narrowing since previous session, price within 1.5% of an anchor",
           "availability":"daily_proxy"}
    return touch,pullback,pinch
