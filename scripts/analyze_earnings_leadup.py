#!/usr/bin/env python3
"""Analyze the seven trading sessions leading into the latest earnings announcement
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
    meta={x['ticker']:x for x in watch['tickers'] if x['ticker'] in BASKET}
    missing=[x for x in BASKET if x not in meta]
    if missing: raise RuntimeError('Missing earnings metadata: '+','.join(missing))

    dates=[datetime.date.fromisoformat(meta[t]['earningsDate']) for t in BASKET]
    start=(min(dates)-datetime.timedelta(days=20)).isoformat()
    end=(max(dates)+datetime.timedelta(days=3)).isoformat()

    tickers=list(BASKET)+list(BENCH.values())
    raw={t:series(fetch(t,start,end)) for t in tickers}

    events={}
    for t in BASKET:
        ed=meta[t]['earningsDate']
        days=sorted(d for d in raw[t] if d<=ed)
        if ed not in raw[t]:
            # For non-trading earnings dates, use the last trading session on/before announcement.
            event_trade_day=days[-1]
        else:
            event_trade_day=ed
        idx=days.index(event_trade_day)
        window=days[max(0,idx-7):idx+1]
        rows=[]
        for offset,day in zip(range(-len(window)+1,1),window):
            rows.append({
                'offset':offset,
                'date':day,
                'stockChangePct':raw[t].get(day,{}).get('changePct'),
                'nasdaqChangePct':raw[BENCH['Nasdaq']].get(day,{}).get('changePct'),
                'soxChangePct':raw[BENCH['SOX']].get(day,{}).get('changePct'),
                'stockClose':raw[t].get(day,{}).get('close'),
                'nasdaqClose':raw[BENCH['Nasdaq']].get(day,{}).get('close'),
                'soxClose':raw[BENCH['SOX']].get(day,{}).get('close')
            })
        pre=[r for r in rows if r['offset']<0]
        incl=rows
        events[t]={
            'earningsDate':ed,
            'releaseSession':meta[t].get('releaseSession'),
            'source':meta[t].get('source'),
            'eventTradingDay':event_trade_day,
            'rows':rows,
            'summary':{
                'stockPre7Pct':compound([r['stockChangePct'] for r in pre]),
                'nasdaqPre7Pct':compound([r['nasdaqChangePct'] for r in pre]),
                'soxPre7Pct':compound([r['soxChangePct'] for r in pre]),
                'stockIncludingEventDayPct':compound([r['stockChangePct'] for r in incl]),
                'nasdaqIncludingEventDayPct':compound([r['nasdaqChangePct'] for r in incl]),
                'soxIncludingEventDayPct':compound([r['soxChangePct'] for r in incl]),
                'positivePreEventSessions':sum(1 for r in pre if (r['stockChangePct'] or 0)>0),
                'preEventSessions':len(pre)
            }
        }

    output={
        'version':1,
        'generatedAtUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'methodology':{
            'dailyReturn':'Adjusted close-to-close percentage return from Massive daily aggregates.',
            'pre7':'Compound return across offsets -7 through -1, excluding announcement day.',
            'includingEventDay':'Compound return across offsets -7 through 0.',
            'timingNote':'For after-close reporters, offset 0 is pre-announcement trading. For before-open reporters, offset 0 includes the earnings reaction.'
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
