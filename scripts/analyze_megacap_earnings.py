#!/usr/bin/env python3
"""Store T-7 through T+7 around every completed 2026 earnings event for NasBoard mega caps.

NVDA is intentionally excluded here because its 2026 earnings windows already live in
earnings_leadup_analysis.json with the semiconductor basket. Benchmarks are Nasdaq Composite
and QQQ because this dataset is for NasBoard's mega-cap leadership basket.
"""
import datetime, json, os, time, urllib.parse, urllib.request, urllib.error

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,'data','history','megacap_earnings_analysis.json')
API='https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}'
PACE=12.5
_last=0.0
BASKET=('AAPL','MSFT','AMZN','GOOGL','META','TSLA')
BENCH={'Nasdaq':'I:COMP','QQQ':'QQQ'}
EVENTS={
 'AAPL':[('2026-01-29','after_close'),('2026-04-30','after_close'),('2026-07-30','after_close')],
 'MSFT':[('2026-01-28','after_close'),('2026-04-29','after_close'),('2026-07-29','after_close')],
 'AMZN':[('2026-02-05','after_close'),('2026-04-29','after_close'),('2026-07-30','after_close')],
 'GOOGL':[('2026-02-04','after_close'),('2026-04-29','after_close'),('2026-07-22','after_close')],
 'META':[('2026-01-28','after_close'),('2026-04-29','after_close'),('2026-07-29','after_close')],
 'TSLA':[('2026-01-28','after_close'),('2026-04-22','after_close'),('2026-07-22','after_close')],
}
SOURCES={
 'AAPL':'Apple Newsroom / Investor Relations',
 'MSFT':'Microsoft Investor Relations',
 'AMZN':'Amazon Investor Relations',
 'GOOGL':'Alphabet Investor Relations',
 'META':'Meta Investor Relations',
 'TSLA':'Tesla Investor Relations',
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
            print(ticker,payload.get('status'),len(payload.get('results',[])))
            return payload.get('results',[]) if payload.get('status') in ('OK','DELAYED') else []
    except urllib.error.HTTPError as e:
        _last=time.monotonic(); print(ticker,'HTTP',e.code,e.read().decode('utf-8',errors='replace')[:300]); return []

def day_of(bar):
    return datetime.datetime.fromtimestamp(bar['t']/1000,datetime.timezone.utc).date().isoformat()

def series(bars):
    out={}; prev=None
    for b in bars:
        day=day_of(b); close=float(b['c'])
        out[day]={'close':round(close,6),'previousClose':round(prev,6) if prev is not None else None,
                  'changePct':round((close/prev-1)*100,4) if prev not in (None,0) else None}
        prev=close
    return out

def compound(vals):
    xs=[x for x in vals if x is not None]
    if not xs:return None
    p=1.0
    for x in xs:p*=1+x/100
    return round((p-1)*100,4)

def main():
    dates=[datetime.date.fromisoformat(d) for es in EVENTS.values() for d,_ in es]
    start=(min(dates)-datetime.timedelta(days=20)).isoformat()
    end=(max(dates)+datetime.timedelta(days=20)).isoformat()
    raw={t:series(fetch(t,start,end)) for t in list(BASKET)+list(BENCH.values())}
    events={}
    for t in BASKET:
        tes=[]
        for i,(ed,session) in enumerate(EVENTS[t]):
            days=sorted(raw[t]); before=[d for d in days if d<=ed]
            if not before:raise RuntimeError(f'No data for {t} {ed}')
            event_day=ed if ed in raw[t] else before[-1]
            idx=days.index(event_day); window=days[max(0,idx-7):min(len(days),idx+8)]
            ep=window.index(event_day); rows=[]
            for pos,day in enumerate(window):
                rows.append({'offset':pos-ep,'date':day,'stock':raw[t].get(day),
                             'nasdaq':raw[BENCH['Nasdaq']].get(day),'qqq':raw[BENCH['QQQ']].get(day)})
            def vals(rs,key):return [r[key].get('changePct') if r.get(key) else None for r in rs]
            pre=[r for r in rows if -7<=r['offset']<0]; incl=[r for r in rows if -7<=r['offset']<=0]
            post=[r for r in rows if 1<=r['offset']<=7]
            summary={}
            for key in ('stock','nasdaq','qqq'):
                summary[key+'Pre7Pct']=compound(vals(pre,key))
                summary[key+'IncludingEventDayPct']=compound(vals(incl,key))
                for n in range(1,8):
                    summary[f'{key}Post{n}CumulativePct']=compound(vals([r for r in post if r['offset']<=n],key))
            summary['positivePreEventSessions']=sum(1 for r in pre if r['stock'] and (r['stock'].get('changePct') or 0)>0)
            summary['preEventSessions']=len(pre)
            tes.append({'eventNumber':i+1,'earningsDate':ed,'releaseSession':session,'source':SOURCES[t],
                        'eventTradingDay':event_day,'rows':rows,'summary':summary})
        events[t]=tes
    output={'version':1,'generatedAtUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'methodology':{'dailyReturn':'Adjusted close-to-close percentage return from Massive daily aggregates.',
              'storedMarketData':'Each T-7 through T+7 row retains adjusted close, previous close and close-to-close changePct for the stock, Nasdaq Composite and QQQ.',
              'window':'T-7 through T+7 regular trading sessions around the announcement-date session.',
              'timingNote':'All included mega-cap earnings events were released after the regular-session close, so T+1 contains the first regular-session earnings reaction.',
              'scope':'Remaining NasBoard mega-cap leadership basket excluding NVDA, whose 2026 earnings history is stored with the semiconductor earnings dataset.'},
            'basket':list(BASKET),'benchmarks':BENCH,'events':events}
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT,'w',encoding='utf-8') as f:json.dump(output,f,ensure_ascii=False,indent=2);f.write('\n')
    print('Wrote',OUT)

if __name__=='__main__':main()

# workflow-trigger
