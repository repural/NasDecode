#!/usr/bin/env python3
"""Analyze T-7 through T+7 around the latest and previous earnings announcements
for the NasBoard semiconductor basket, with Nasdaq Composite and SOX benchmarks.

Output is research data only; it does not alter model scores.
"""
import datetime, json, os, time, urllib.parse, urllib.request, urllib.error

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH=os.path.join(ROOT,'data','earnings_avwap_watchlist.json')
OUT=os.path.join(ROOT,'data','history','earnings_leadup_analysis.json')
API='https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}'
PACE=12.5
_last=0.0
BASKET=('NVDA','AMD','AVGO','TSM','MU')
BENCH={'Nasdaq':'I:COMP','SOX':'I:SOX'}
EVENTS={
 # All completed 2026 earnings events through the current date.
 # Latest dates are also cross-checked against the live AVWAP watchlist below.
 'NVDA':[('2026-08-26','after_close'),('2026-05-20','after_close'),('2026-02-25','after_close')],
 'AMD':[('2026-08-04','after_close'),('2026-05-05','after_close'),('2026-02-03','after_close')],
 'AVGO':[('2026-09-02','after_close'),('2026-06-04','after_close'),('2026-03-04','after_close')],
 'TSM':[('2026-07-16','before_open'),('2026-04-16','before_open'),('2026-01-15','before_open')],
 'MU':[('2026-06-24','after_close'),('2026-03-18','after_close')],
}

def fetch(ticker,start,end):
    global _last
    key=os.environ.get('MASSIVE_API_KEY','').strip()
    if not key: raise RuntimeError('MASSIVE_API_KEY is missing')
    wait=PACE-(time.monotonic()-_last)
    if _last and wait>0: time.sleep(wait)
    url=API.format(ticker=urllib.parse.quote(ticker,safe=''),start=start,end=end)
    url+='?adjusted=true&sort=asc&limit=5000'
    req=urllib.request.Request(url,headers={'Authorization':f'Bearer {key}','User-Agent':'NasBoard/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=30) as resp:
            payload=json.load(resp); _last=time.monotonic()
            print(ticker, payload.get('status'), len(payload.get('results',[])))
            return payload.get('results',[]) if payload.get('status') in ('OK','DELAYED') else []
    except urllib.error.HTTPError as e:
        _last=time.monotonic()
        print(ticker,'HTTP',e.code,e.read().decode('utf-8',errors='replace')[:300])
        return []

def day_of(bar):
    return datetime.datetime.fromtimestamp(bar['t']/1000,datetime.timezone.utc).date().isoformat()

def series(bars):
    out={}; prev=None
    for b in bars:
        day=day_of(b); close=float(b['c'])
        out[day]={
            'close':round(close,6),
            'previousClose':round(prev,6) if prev is not None else None,
            'changePct':round((close/prev-1)*100,4) if prev not in (None,0) else None
        }
        prev=close
    return out

def compound(vals):
    xs=[x for x in vals if x is not None]
    if not xs: return None
    p=1.0
    for x in xs: p*=1+x/100.0
    return round((p-1)*100,4)

def main():
    with open(WATCH,encoding='utf-8') as f: watch=json.load(f)
    latest_meta={x['ticker']:x for x in watch['tickers'] if x['ticker'] in BASKET}
    missing=[x for x in BASKET if x not in latest_meta]
    if missing: raise RuntimeError('Missing earnings metadata: '+','.join(missing))

    # Keep the watchlist as the authority for the latest event; explicit prior-event
    # dates extend the research history without changing live AVWAP anchors.
    event_meta={}
    for t in BASKET:
        latest=(latest_meta[t]['earningsDate'],latest_meta[t].get('releaseSession'))
        configured=EVENTS[t]
        if configured[0][0] != latest[0]:
            configured=[latest]+[x for x in configured if x[0]!=latest[0]]
        event_meta[t]=configured

    dates=[datetime.date.fromisoformat(ed) for t in BASKET for ed,_ in event_meta[t]]
    start=(min(dates)-datetime.timedelta(days=20)).isoformat()
    end=(max(dates)+datetime.timedelta(days=20)).isoformat()

    tickers=list(BASKET)+list(BENCH.values())
    raw={t:series(fetch(t,start,end)) for t in tickers}

    events={}
    for t in BASKET:
        ticker_events=[]
        for event_index,(ed,release_session) in enumerate(event_meta[t]):
            all_days=sorted(raw[t])
            before=sorted(d for d in all_days if d<=ed)
            if not before: raise RuntimeError(f'No trading data on/before {t} {ed}')
            event_trade_day=ed if ed in raw[t] else before[-1]
            idx=all_days.index(event_trade_day)
            window=all_days[max(0,idx-7):min(len(all_days),idx+8)]
            event_pos=window.index(event_trade_day)
            rows=[]
            for pos,day in enumerate(window):
                offset=pos-event_pos
                rows.append({
                    'offset':offset,
                    'date':day,
                    'stock':raw[t].get(day),
                    'nasdaq':raw[BENCH['Nasdaq']].get(day),
                    'sox':raw[BENCH['SOX']].get(day)
                })
            pre=[r for r in rows if -7<=r['offset']<0]
            incl=[r for r in rows if -7<=r['offset']<=0]
            post=[r for r in rows if 1<=r['offset']<=7]
            def vals(rows,key):
                return [r[key].get('changePct') if r.get(key) else None for r in rows]
            summary={
                'stockPre7Pct':compound(vals(pre,'stock')),
                'nasdaqPre7Pct':compound(vals(pre,'nasdaq')),
                'soxPre7Pct':compound(vals(pre,'sox')),
                'stockIncludingEventDayPct':compound(vals(incl,'stock')),
                'nasdaqIncludingEventDayPct':compound(vals(incl,'nasdaq')),
                'soxIncludingEventDayPct':compound(vals(incl,'sox')),
                'positivePreEventSessions':sum(1 for r in pre if r.get('stock') and (r['stock'].get('changePct') or 0)>0),
                'preEventSessions':len(pre)
            }
            for n in range(1,8):
                nrows=[r for r in post if r['offset']<=n]
                summary[f'stockPost{n}CumulativePct']=compound(vals(nrows,'stock'))
                summary[f'nasdaqPost{n}CumulativePct']=compound(vals(nrows,'nasdaq'))
                summary[f'soxPost{n}CumulativePct']=compound(vals(nrows,'sox'))
            ticker_events.append({
                'eventNumber':'latest' if event_index==0 else f'previous{event_index}',
                'earningsDate':ed,
                'releaseSession':release_session,
                'source':latest_meta[t].get('source') if event_index==0 else 'historical earnings calendar / issuer IR',
                'eventTradingDay':event_trade_day,
                'rows':rows,
                'summary':summary
            })
        events[t]=ticker_events

    output={
        'version':3,
        'generatedAtUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'methodology':{
            'dailyReturn':'Adjusted close-to-close percentage return from Massive daily aggregates.',
            'storedMarketData':'For stock, Nasdaq Composite and SOX, each row retains adjusted close, previous close and close-to-close changePct.',
            'window':'T-7 through T+7 regular trading sessions around the announcement-date session.',
            'pre7':'Compound return across offsets -7 through -1, excluding announcement day.',
            'includingEventDay':'Compound return across offsets -7 through 0.',
            'postEvent':'Cumulative T+1 through T+n returns are stored for n=1..7.',
            'timingNote':'For after-close reporters, T0 is pre-announcement trading and T+1 contains the first regular-session earnings reaction. For before-open reporters, T0 already contains the first earnings reaction.'
        },
        'basket':list(BASKET),
        'benchmarks':BENCH,
        'events':events
    }
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT,'w',encoding='utf-8') as f:
        json.dump(output,f,ensure_ascii=False,indent=2); f.write('\n')
    print('Wrote',OUT)

if __name__=='__main__':
    main()

# workflow-trigger-v1
