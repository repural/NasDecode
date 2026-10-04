#!/usr/bin/env python3
"""Build the canonical one-year input dataset for the NasDecode Resilience Engine.

Phase 1 only: collect and normalize observations. This script does NOT calculate
or feed any NasDecode score. On first run it backfills ~1 calendar year; later
runs overlap the tail and append/update completed sessions.

Primary market source: Massive adjusted daily aggregates.
Macro-market history adapter: Yahoo chart history for Treasury yields, VXN and
oil futures. Provider/source is persisted per observation so adapters can be
replaced without changing the resilience schema.
"""
import datetime, json, math, os, time, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,'data','history','resilience-daily.json')
NY=ZoneInfo('America/New_York')
MASSIVE='https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}'
PACE=12.5
_last_massive=0.0

MARKET={
    'SOX':'I:SOX','QQQ':'QQQ','SOXX':'SOXX','SMH':'SMH',
    'NVDA':'NVDA','AMD':'AMD','AVGO':'AVGO','TSM':'TSM','MU':'MU'
}
MACRO_YAHOO={'VXN':'^VXN','Brent':'BZ=F','WTI':'CL=F'}
MACRO={'US10Y':'US Treasury BC_10YEAR','US2Y':'US Treasury BC_2YEAR',**MACRO_YAHOO}
BASKET=('NVDA','AMD','AVGO','TSM','MU')

def num(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None

def pct(a,b):
    return ((a/b)-1)*100 if a is not None and b not in (None,0) else None

def massive_fetch(ticker,start,end):
    global _last_massive
    key=os.environ.get('MASSIVE_API_KEY','').strip()
    if not key: raise RuntimeError('MASSIVE_API_KEY is missing')
    wait=PACE-(time.monotonic()-_last_massive)
    if _last_massive and wait>0: time.sleep(wait)
    url=MASSIVE.format(ticker=urllib.parse.quote(ticker,safe=''),start=start,end=end)
    url+='?adjusted=true&sort=asc&limit=50000'
    req=urllib.request.Request(url,headers={'Authorization':f'Bearer {key}','User-Agent':'NasDecode/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=40) as resp:
            p=json.load(resp); _last_massive=time.monotonic()
        rows=p.get('results') or []
        print('Massive',ticker,'rows',len(rows),'status',p.get('status'))
        return rows
    except urllib.error.HTTPError as e:
        _last_massive=time.monotonic()
        print('Massive',ticker,'HTTP',e.code,e.read().decode('utf-8',errors='replace')[:300])
        return []

def treasury_yields(start,end):
    """Official US Treasury daily par yields for 2Y and 10Y."""
    out={'US2Y':{},'US10Y':{}}
    for year in range(start.year,end.year+1):
        url=('https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml'
             f'?data=daily_treasury_yield_curve&field_tdr_date_value={year}')
        req=urllib.request.Request(url,headers={'User-Agent':'NasDecode/1.0'})
        try:
            with urllib.request.urlopen(req,timeout=40) as resp:
                root=ET.fromstring(resp.read())
            count=0
            for entry in root.iter():
                if entry.tag.split('}')[-1]!='properties': continue
                vals={child.tag.split('}')[-1]:(child.text or '').strip() for child in entry}
                ds=vals.get('NEW_DATE')
                if not ds: continue
                day=ds[:10]
                try: d=datetime.date.fromisoformat(day)
                except ValueError: continue
                if not (start<=d<=end): continue
                for name,field in [('US2Y','BC_2YEAR'),('US10Y','BC_10YEAR')]:
                    v=num(vals.get(field))
                    if v is not None:
                        out[name][day]={'open':None,'high':None,'low':None,'close':v,'volume':None,
                                        'source':'U.S. Treasury daily par yield curve'}
                count+=1
            print('US Treasury',year,'rows',count)
        except Exception as e:
            print('US Treasury',year,'unavailable:',repr(e))
    return out


def yahoo_fetch(symbol,start,end):
    # Query range includes end date by adding one day to period2.
    p1=int(datetime.datetime.combine(start,datetime.time(),tzinfo=datetime.timezone.utc).timestamp())
    p2=int(datetime.datetime.combine(end+datetime.timedelta(days=1),datetime.time(),tzinfo=datetime.timezone.utc).timestamp())
    enc=urllib.parse.quote(symbol,safe='')
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{enc}?period1={p1}&period2={p2}&interval=1d&events=history&includeAdjustedClose=true'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 NasDecode/1.0','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as resp: p=json.load(resp)
        result=((p.get('chart') or {}).get('result') or [None])[0]
        if not result: return []
        ts=result.get('timestamp') or []
        q=(((result.get('indicators') or {}).get('quote') or [{}])[0])
        out=[]
        for i,t in enumerate(ts):
            day=datetime.datetime.fromtimestamp(t,datetime.timezone.utc).date().isoformat()
            row={'date':day}
            for src,dst in [('open','o'),('high','h'),('low','l'),('close','c'),('volume','v')]:
                vals=q.get(src) or []
                row[dst]=num(vals[i]) if i<len(vals) else None
            if row['c'] is not None: out.append(row)
        print('Yahoo',symbol,'rows',len(out))
        return out
    except Exception as e:
        print('Yahoo',symbol,'unavailable:',repr(e))
        return []

def massive_rows(rows):
    out={}
    for b in rows:
        day=datetime.datetime.fromtimestamp(b['t']/1000,datetime.timezone.utc).date().isoformat()
        out[day]={'open':num(b.get('o')),'high':num(b.get('h')),'low':num(b.get('l')),
                  'close':num(b.get('c')),'volume':num(b.get('v')),'vwap':num(b.get('vw')),
                  'source':'Massive adjusted daily aggregate'}
    return out

def yahoo_rows(rows,symbol):
    return {b['date']:{'open':b['o'],'high':b['h'],'low':b['l'],'close':b['c'],
                       'volume':b['v'],'source':f'Yahoo Finance daily chart ({symbol})'}
            for b in rows}

def with_changes(series,yield_series=False):
    prev=None
    for day in sorted(series):
        x=series[day]; close=x.get('close')
        x['previousClose']=prev
        if yield_series:
            x['changeBp']=round((close-prev)*100,3) if close is not None and prev is not None else None
            x['changePct']=round(pct(close,prev),4) if close is not None and prev is not None else None
        else:
            x['return1dPct']=round(pct(close,prev),4) if close is not None and prev is not None else None
        if close is not None: prev=close
    return series

def main():
    today=datetime.datetime.now(NY).date()
    end=today-datetime.timedelta(days=1)
    # Initial target is a full 12 calendar months plus overlap for first-day changes.
    target_start=end-datetime.timedelta(days=370)
    existing={}
    if os.path.exists(OUT):
        try:
            with open(OUT,encoding='utf-8') as f: existing=json.load(f)
        except Exception: existing={}
    old_records=existing.get('records') or {}
    needs_full_backfill=not old_records or not ((existing.get('providerAvailability') or {}).get('US2Y') or {}).get('available')
    if old_records and not needs_full_backfill:
        last=max(old_records)
        incremental=datetime.date.fromisoformat(last)-datetime.timedelta(days=7)
        fetch_start=max(target_start,incremental)
    else:
        fetch_start=target_start
    # Five extra calendar days let us compute the first in-window daily change.
    request_start=fetch_start-datetime.timedelta(days=7)
    print('Resilience Phase 1 range',fetch_start,'through',end)

    series={}
    availability={}
    for name,ticker in MARKET.items():
        s=with_changes(massive_rows(massive_fetch(ticker,request_start.isoformat(),end.isoformat())))
        series[name]=s
        availability[name]={'provider':'Massive','ticker':ticker,'rows':len(s),'available':bool(s)}

    treasury=treasury_yields(request_start,end)
    for name in ('US10Y','US2Y'):
        s=with_changes(treasury.get(name,{}) ,yield_series=True)
        series[name]=s
        availability[name]={'provider':'U.S. Treasury','ticker':MACRO[name],'rows':len(s),'available':bool(s)}
    for name,symbol in MACRO_YAHOO.items():
        s=with_changes(yahoo_rows(yahoo_fetch(symbol,request_start,end),symbol),yield_series=False)
        series[name]=s
        availability[name]={'provider':'Yahoo Finance','ticker':symbol,'rows':len(s),'available':bool(s)}

    # SOX trading sessions are the canonical row calendar.
    sox_days=[d for d in sorted(series['SOX']) if fetch_start.isoformat()<=d<=end.isoformat()]
    records=dict(old_records)
    for day in sox_days:
        market={k:series[k].get(day) for k in MARKET}
        macro={k:series[k].get(day) for k in MACRO}
        sox=market['SOX'] or {}; qqq=market['QQQ'] or {}; soxx=market['SOXX'] or {}; smh=market['SMH'] or {}
        basket_returns={k:(market[k] or {}).get('return1dPct') for k in BASKET}
        valid=[v for v in basket_returns.values() if v is not None]
        qret=qqq.get('return1dPct')
        breadth=(100*sum(v>0 for v in valid)/len(valid)) if valid else None
        outperform=(100*sum(v>qret for v in valid)/len(valid)) if valid and qret is not None else None
        records[day]={
            'date':day,
            'market':market,
            'macro':macro,
            'derived':{
                'soxReturn1dPct':sox.get('return1dPct'),
                'qqqReturn1dPct':qret,
                'soxVsQqqRelative1dPp':round(sox.get('return1dPct')-qret,4) if sox.get('return1dPct') is not None and qret is not None else None,
                'soxxVsQqqRelative1dPp':round(soxx.get('return1dPct')-qret,4) if soxx.get('return1dPct') is not None and qret is not None else None,
                'smhVsQqqRelative1dPp':round(smh.get('return1dPct')-qret,4) if smh.get('return1dPct') is not None and qret is not None else None,
                'basketReturnsPct':basket_returns,
                'basketPositiveBreadthPct':round(breadth,1) if breadth is not None else None,
                'basketOutperformQqqPct':round(outperform,1) if outperform is not None else None
            },
            'futureInputs':{
                'fedRepricing':None,
                'macroSurprise':None,
                'catalystContext':None,
                'note':'Reserved for point-in-time enrichment; never backfilled from future knowledge.'
            }
        }

    # Retain only the requested rolling one-year calendar window.
    cutoff=(end-datetime.timedelta(days=365)).isoformat()
    records={d:records[d] for d in sorted(records) if d>=cutoff and d<=end.isoformat()}
    payload={
        'schemaVersion':1,
        'enginePhase':1,
        'purpose':'Canonical observed-input history for future SOX resilience modeling. Not used by current scores.',
        'window':{'calendarMonths':12,'start':min(records) if records else None,'end':max(records) if records else None,'sessions':len(records)},
        'series':{
            'market':MARKET,
            'macro':MACRO,
            'semiconductorBasket':list(BASKET)
        },
        'fieldDefinitions':{
            'changeBp':'Yield close-to-close change in basis points.',
            'return1dPct':'Adjusted close-to-close daily percentage return.',
            'soxVsQqqRelative1dPp':'SOX daily return minus QQQ daily return, percentage points.',
            'basketPositiveBreadthPct':'Share of NVDA/AMD/AVGO/TSM/MU with positive daily return.',
            'basketOutperformQqqPct':'Share of basket names whose daily return exceeded QQQ.'
        },
        'providerAvailability':availability,
        'records':records
    }
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT,'w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2); f.write('\n')
    print('Stored',len(records),'SOX sessions in',OUT)
    for k,v in availability.items(): print(k,v)

if __name__=='__main__':
    main()
