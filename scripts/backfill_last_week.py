#!/usr/bin/env python3
"""Backfill recent completed daily market history from Massive.

The default window starts on Monday of the previous calendar week and ends
yesterday. This repairs the previous week plus any completed sessions in the
current week while preserving point-in-time NasBoard model scores already stored.

This intentionally backfills only observed market data. It does NOT reconstruct
NasBoard model scores because historical OHLC alone cannot reproduce the full
point-in-time factor set (Fed pricing, breadth, options, volatility, etc.).
"""
import datetime, json, os, time, urllib.parse, urllib.request, urllib.error
from zoneinfo import ZoneInfo

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH=os.path.join(ROOT,'data','history','daily.json')
NY=ZoneInfo('America/New_York')
API='https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}'
PACE=12.5
_last=0.0

# Massive stock/ETF tickers plus the corresponding Massive index tickers.
SERIES={
    'Nasdaq': 'I:COMP',
    'SOX': 'I:SOX',
    'SMH': 'SMH',
    'SOXX': 'SOXX',
    'NVDA': 'NVDA',
    'AMD': 'AMD',
    'AVGO': 'AVGO',
    'TSM': 'TSM',
    'MU': 'MU',
    'QQQ': 'QQQ',
}

def fetch(ticker,start,end):
    global _last
    key=os.environ.get('MASSIVE_API_KEY','').strip()
    if not key:
        raise RuntimeError('MASSIVE_API_KEY is missing')
    wait=PACE-(time.monotonic()-_last)
    if _last and wait>0:
        time.sleep(wait)
    url=API.format(ticker=urllib.parse.quote(ticker,safe=''),start=start,end=end)
    url+='?adjusted=true&sort=asc&limit=100'
    req=urllib.request.Request(url,headers={'Authorization':f'Bearer {key}','User-Agent':'NasBoard/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=30) as resp:
            payload=json.load(resp)
            _last=time.monotonic()
            print(f"{ticker}: HTTP {resp.status}, status={payload.get('status')}, results={len(payload.get('results',[]))}")
            return payload.get('results',[]) if payload.get('status') in ('OK','DELAYED') else []
    except urllib.error.HTTPError as e:
        _last=time.monotonic()
        body=e.read().decode('utf-8',errors='replace')[:500]
        print(f"{ticker}: HTTP {e.code} {body}")
        return []

def day_of(bar):
    return datetime.datetime.fromtimestamp(bar['t']/1000,datetime.timezone.utc).date().isoformat()

def obs(bar,ticker):
    o=float(bar['o']); c=float(bar['c'])
    return {
        'ticker':ticker,
        'open':round(o,6),
        'high':round(float(bar['h']),6),
        'low':round(float(bar['l']),6),
        'close':round(c,6),
        'changeOpenToClosePct':round((c/o-1)*100,4) if o else None,
        'volume':bar.get('v'),
        'vwap':bar.get('vw'),
        'source':'Massive adjusted daily aggregate',
    }

def main():
    today=datetime.datetime.now(NY).date()
    this_monday=today-datetime.timedelta(days=today.weekday())
    start=this_monday-datetime.timedelta(days=7)
    end=today-datetime.timedelta(days=1)
    start_s,end_s=start.isoformat(),end.isoformat()
    print(f'Backfilling recent completed sessions: {start_s} through {end_s}')

    with open(PATH,encoding='utf-8') as f:
        hist=json.load(f)
    hist['schemaVersion']=max(4,int(hist.get('schemaVersion',0) or 0))
    records=hist.setdefault('records',{})

    fetched={}
    unavailable=[]
    for label,ticker in SERIES.items():
        fetch_start=(start-datetime.timedelta(days=5)).isoformat()
        bars=fetch(ticker,fetch_start,end_s)
        if not bars:
            unavailable.append({'label':label,'ticker':ticker})
        series={}
        prior_close=None
        for bar in bars:
            day=day_of(bar)
            x=obs(bar,ticker)
            x['previousClose']=round(prior_close,6) if prior_close is not None else None
            x['changeCloseToClosePct']=round((x['close']/prior_close-1)*100,4) if prior_close not in (None,0) else None
            series[day]=x
            prior_close=x['close']
        fetched[label]={day:x for day,x in series.items() if start_s <= day <= end_s}

    all_days=sorted(set().union(*(set(x.keys()) for x in fetched.values())))
    for day in all_days:
        rec=records.setdefault(day,{
            'schemaVersion':4,
            'timestampET':day+'T16:00:00-04:00',
            'market':{},
            'factors':{},
        })
        rec['schemaVersion']=max(4,int(rec.get('schemaVersion',0) or 0))
        levels=rec.setdefault('sessionLevels',{})
        market=rec.setdefault('market',{})
        for label,ticker in SERIES.items():
            x=fetched[label].get(day)
            if not x:
                continue
            levels[label]=x
            key={ 'Nasdaq':'.IXIC', 'SOX':'.SOX' }.get(label,label)
            market[key]={
                'open':x['open'],'high':x['high'],'low':x['low'],'last':x['close'],
                'previousClose':x.get('previousClose'),'changePct':x.get('changeCloseToClosePct'),
                'openToClosePct':x['changeOpenToClosePct'],'observationDate':day,
                'dataState':'historical','provider':'Massive','ticker':ticker
            }
        rec['historicalBackfill']={
            'source':'Massive adjusted daily aggregates',
            'range':f'{start_s}..{end_s}',
            'note':'Market OHLC only; NasBoard scores are not reconstructed from incomplete point-in-time inputs.'
        }

    # Keep deterministic chronological JSON ordering.
    hist['records']={k:records[k] for k in sorted(records)}
    with open(PATH,'w',encoding='utf-8') as f:
        json.dump(hist,f,ensure_ascii=False,indent=2)
        f.write('\n')
    print('Stored days:',all_days)
    if unavailable:
        print('Unavailable Massive series:',json.dumps(unavailable))

if __name__=='__main__':
    main()
