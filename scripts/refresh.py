"""NasBoard market-data refresh engine.

Data flow:
1. Fetch/normalize free market and official-source observations.
2. Update the 15 underlying Nasdaq factors.
3. Derive each factor's Signal, Trend, Current Impact, explanation, and scorecard.
4. Compute the Nasdaq Setup and Consolidation Risk model outputs.
5. Persist daily/intraday history and publish data/dashboard.json.

Design rule: missing or stale inputs fail closed. NasBoard should label unavailable data
rather than infer a live value from an old observation.
"""

import json, urllib.request, urllib.parse, datetime, os, re, time, statistics, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT=os.path.dirname(os.path.dirname(__file__))
PATH=os.path.join(ROOT,'data','dashboard.json')
HISTORY_DIR=os.path.join(ROOT,'data','history')
DAILY_PATH=os.path.join(HISTORY_DIR,'daily.json')
EARNINGS_AVWAP_PATH=os.path.join(ROOT,'data','earnings_avwap_watchlist.json')
_MASSIVE_LAST_CALL=0.0
NY=ZoneInfo('America/New_York')
CNBC_BASE='https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol'
MEGACAPS=['AAPL','MSFT','AMZN','GOOGL','META','NVDA','TSLA']
BREADTH=['NVDA','AAPL','MU','MSFT','AMD','AMZN','TSLA','GOOGL','INTC','GOOG','AVGO','META','AMAT','WMT','LRCX','CSCO','COST','KLAC','SNDK','NFLX','PANW','TXN','PLTR','MRVL','LIN','WDC','STX','AMGN','QCOM','CRWD','ADI','PEP','ASML','TMUS','APP','GILD','ARM','ISRG','SHOP','BKNG','VRTX','SBUX','FTNT','CDNS','MAR','MNST','CEG','ADP','CSX','CMCSA','DDOG','MELI','SNPS','ADBE','ALAB','ORLY','DASH','TER','AEP','MDLZ','INTU','NXPI','HON','HONA','ROST','CTAS','MPWR','WBD','LITE','REGN','RBLX','NBIS','ABNB','RKLB','FAST','BKR','PDD','XEL','FANG','MCHP','FER','EXC','TTWO','AXON','ODFL','CCEP','CRWV','KDP','IDXX','ADSK','ALNY','PYPL','PAYX','ROP','TRI','GEHC','MSTR','KHC','CPRT','DXCM','WDAY','SPCX']
SYMBOLS=list(dict.fromkeys(['US10Y','US2Y','ZQU6','ZQV6','ZQX6','ZQZ6','ZQF7','ZQG7','ZQH7','.IXIC','QQQ','NVDA','AMD','AVGO','TSM','MU','SMH','.VIX','.VXN','@CL.1','@LCO.1','HYG','LQD','S5FI','.SOX','SOX']+MEGACAPS+BREADTH))

def cnbc_quotes(symbols):
    params={'symbols':'|'.join(symbols),'requestMethod':'itv','noform':'1','partnerId':'2','fund':'1','exthrs':'1','output':'json','events':'1'}
    url=CNBC_BASE+'?'+urllib.parse.urlencode(params,safe='|@.')
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/plain,*/*','Referer':'https://www.cnbc.com/'})
    with urllib.request.urlopen(req,timeout=20) as r: raw=r.read().decode('utf-8',errors='replace')
    data=json.loads(raw); qs=data.get('FormattedQuoteResult',{}).get('FormattedQuote',[])
    if isinstance(qs,dict): qs=[qs]
    return {q.get('symbol'):q for q in qs if q.get('symbol') and q.get('code')==0}

def massive_daily_bars(ticker, days=120):
    """Fetch adjusted daily OHLCV/VWAP bars with pacing and bounded 429 retries."""
    global _MASSIVE_LAST_CALL
    key=os.environ.get('MASSIVE_API_KEY','').strip()
    if not key: return []
    end=datetime.datetime.now(NY).date()
    start=end-datetime.timedelta(days=days)
    url=(f'https://api.massive.com/v2/aggs/ticker/{urllib.parse.quote(ticker)}/range/1/day/'
         f'{start.isoformat()}/{end.isoformat()}?adjusted=true&sort=asc&limit=5000')
    req=urllib.request.Request(url,headers={'Authorization':f'Bearer {key}','User-Agent':'NasBoard/1.0'})
    backoffs=(15,30,60)
    for attempt in range(4):
        # Preserve a conservative free-tier pace on every attempt, including retries.
        wait=12.5-(time.monotonic()-_MASSIVE_LAST_CALL)
        if _MASSIVE_LAST_CALL and wait>0: time.sleep(wait)
        try:
            with urllib.request.urlopen(req,timeout=20) as resp:
                payload=json.load(resp)
                _MASSIVE_LAST_CALL=time.monotonic()
                remaining=resp.headers.get('X-RateLimit-Remaining')
                limit=resp.headers.get('X-RateLimit-Limit')
                reset=resp.headers.get('X-RateLimit-Reset')
                if any(x is not None for x in (remaining,limit,reset)):
                    print(f'Massive rate info {ticker}: limit={limit} remaining={remaining} reset={reset}')
            return payload.get('results',[]) if payload.get('status') in ('OK','DELAYED') else []
        except urllib.error.HTTPError as e:
            _MASSIVE_LAST_CALL=time.monotonic()
            if e.code!=429 or attempt>=len(backoffs):
                print(f'Massive history unavailable for {ticker}:',repr(e))
                return []
            retry_after=e.headers.get('Retry-After') if e.headers else None
            limit=e.headers.get('X-RateLimit-Limit') if e.headers else None
            remaining=e.headers.get('X-RateLimit-Remaining') if e.headers else None
            reset=e.headers.get('X-RateLimit-Reset') if e.headers else None
            try:
                retry_seconds=max(float(retry_after),0)+1 if retry_after is not None else backoffs[attempt]
            except (TypeError,ValueError):
                retry_seconds=backoffs[attempt]
            print(f'Massive 429 for {ticker}: attempt {attempt+1}/4; retry_after={retry_after}; '
                  f'limit={limit}; remaining={remaining}; reset={reset}; sleeping {retry_seconds:.0f}s')
            time.sleep(retry_seconds)
        except Exception as e:
            _MASSIVE_LAST_CALL=time.monotonic()
            print(f'Massive history unavailable for {ticker}:',repr(e))
            return []
    return []


def massive_index_latest(candidates):
    """Try Massive index aggregate symbols and return the latest observed close."""
    for ticker in candidates:
        bars=massive_daily_bars(ticker,days=10)
        if bars:
            b=bars[-1]
            v=num(b.get('c'))
            if v is not None:
                return {'ticker':ticker,'value':v,'date':datetime.datetime.fromtimestamp(b['t']/1000,datetime.timezone.utc).date().isoformat()}
    return None

def historical_context(bars):
    """Summarize objective historical context from daily closes.

    Returns streak, multi-session return, moving-average distance, and the date of the
    highest close in the fetched window. Calculations require observed bars and return
    None when history is insufficient rather than fabricating context.
    """
    closes=[float(b['c']) for b in bars if b.get('c') is not None]
    if not closes: return None
    streak=0
    for i in range(len(closes)-1,0,-1):
        if closes[i]>closes[i-1]:
            if streak<0: break
            streak+=1
        elif closes[i]<closes[i-1]:
            if streak>0: break
            streak-=1
        else: break
    ret1=(closes[-1]/closes[-2]-1)*100 if len(closes)>=2 else None
    ret3=(closes[-1]/closes[-4]-1)*100 if len(closes)>=4 else None
    ret5=(closes[-1]/closes[-6]-1)*100 if len(closes)>=6 else None
    ma20=sum(closes[-20:])/20 if len(closes)>=20 else None
    ma50=sum(closes[-50:])/50 if len(closes)>=50 else None
    ma20dist=(closes[-1]/ma20-1)*100 if ma20 else None
    ma50dist=(closes[-1]/ma50-1)*100 if ma50 else None
    rsi14=None
    if len(closes)>=15:
        changes=[b-a for a,b in zip(closes[-15:-1],closes[-14:])]
        ag=sum(max(x,0) for x in changes)/14
        al=sum(max(-x,0) for x in changes)/14
        rsi14=100 if al==0 else 100-(100/(1+ag/al))
    max_i=max(range(len(closes)),key=lambda i:closes[i])
    max_date=datetime.datetime.fromtimestamp(bars[max_i]['t']/1000,datetime.timezone.utc).date().isoformat() if bars[max_i].get('t') else None
    return {'streak':streak,'return1d':ret1,'return3d':ret3,'return5d':ret5,
            'ma20Distance':ma20dist,'ma50Distance':ma50dist,'rsi14':rsi14,
            'windowHighDate':max_date,'windowHighClose':closes[max_i],'bars':len(closes)}



def earnings_avwap_from_daily_bars(bars, earnings_date, release_session):
    """Calculate an earnings-anchored VWAP from Massive daily VWAP and volume.

    After-close releases anchor at the next trading session; before-open releases anchor
    on the release date. Daily aggregate VWAP × volume preserves the cumulative VWAP
    mathematics without downloading every trade. The function also returns the AVWAP
    slope over the latest five included sessions.
    """
    anchor=datetime.date.fromisoformat(earnings_date)
    selected=[]
    for b in bars:
        if b.get('t') is None or b.get('v') in (None,0) or b.get('vw') is None: continue
        day=datetime.datetime.fromtimestamp(b['t']/1000,datetime.timezone.utc).date()
        include=day>anchor if release_session=='after_close' else day>=anchor
        if include: selected.append((day,float(b['vw']),float(b['v'])))
    if not selected: return None
    seq=[]; pv=0.0; vol=0.0
    for day,vw,v in selected:
        pv+=vw*v; vol+=v; seq.append((day,pv/vol))
    slope=(seq[-1][1]/seq[-6][1]-1)*100 if len(seq)>=6 else None
    return {'anchorDate':seq[0][0].isoformat(),'avwap':seq[-1][1],
            'slope5dPct':slope,'sessions':len(seq),'throughDate':seq[-1][0].isoformat()}


def build_earnings_avwap_factor(quotes):
    """Refresh the selective earnings-AVWAP basket and derive one Nasdaq Setup factor.

    The factor measures whether important semiconductor/AI leaders trade above their
    post-earnings institutional cost basis. Individual ticker details remain available
    in dashboard.json while the composite row prevents six highly correlated stocks
    from being counted as six independent Nasdaq Setup factors.
    """
    try:
        with open(EARNINGS_AVWAP_PATH,encoding='utf-8') as f: cfg=json.load(f)
    except (FileNotFoundError,json.JSONDecodeError):
        return None,{}
    details={}
    for item in cfg.get('tickers',[]):
        ticker=item.get('ticker')
        if not ticker: continue
        bars=massive_daily_bars(ticker,180)
        calc=earnings_avwap_from_daily_bars(bars,item['earningsDate'],item.get('releaseSession','after_close'))
        current=num(quotes.get(ticker,{}).get('last'))
        if calc and current is not None:
            dist=(current/calc['avwap']-1)*100
            calc.update({'ticker':ticker,'price':current,'distancePct':dist,
                         'above':dist>=0,'earningsDate':item['earningsDate'],
                         'source':item.get('source','company investor relations')})
            details[ticker]=calc
    vals=list(details.values())
    if not vals:
        row={'factor':'Earnings AVWAP leadership','latest':'Awaiting Earnings AVWAP data',
             'direction':'Awaiting data','signal':'mixed','freshness':'STALE — Massive/anchor data unavailable',
             'source':'Massive aggregates + verified company earnings dates','currentImpact':'Low',
             'explanation':'Tracks a selective semiconductor/AI basket versus VWAP anchored to each company’s latest earnings release.'}
        return row,details
    above=sum(x['above'] for x in vals); ratio=above/len(vals)
    median_dist=statistics.median(x['distancePct'] for x in vals)
    # Earnings AVWAP has a nonlinear directional effect. Moderate positive distance
    # confirms leadership; extreme positive distance loses directional benefit because
    # the same strength has become an extension risk. Exact thresholds remain private
    # model implementation details rather than being exposed in public descriptions.
    if median_dist < 0:
        signal='negative' if ratio<=1/2 else 'mixed'
    elif median_dist <= 8:
        signal='positive' if ratio>=2/3 else 'mixed'
    elif median_dist <= 12:
        signal='mixed'
    else:
        signal='negative'
    direction=('Healthy support above earnings anchors' if signal=='positive' else
               ('Overextended above earnings anchors' if median_dist>8 else
                ('Weakness below earnings anchors' if signal=='negative' else 'Mixed around earnings anchors')))
    names=', '.join(f"{x['ticker']} {x['distancePct']:+.1f}%" for x in vals)
    row={'factor':'Earnings AVWAP leadership',
         'latest':f"{above}/{len(vals)} above Earnings AVWAP · median {median_dist:+.1f}%",
         'direction':direction,'signal':signal,'freshness':'Massive daily aggregates + CNBC current price',
         'source':'Massive aggregates + verified company earnings dates',
         'currentImpact':'High' if abs(median_dist)>=3 or ratio in (0,1) else 'Medium',
         'medianDistancePct':median_dist,'aboveCount':above,'coveredCount':len(vals),
         'explanation':f"{names}. Earnings AVWAP approximates the volume-weighted institutional cost basis since each company’s latest earnings reset."}
    return row,details

def num(v):
    if v is None:return None
    try:return float(str(v).replace(',','').replace('%','').replace('$','').strip())
    except:return None

def pct(q):
    # CNBC often supplies an authoritative change_pct even when previous_day_closing is
    # duplicated from last in delayed equity/ETF snapshots. Prefer the supplied move.
    cp=num(q.get('change_pct'))
    if cp is not None: return cp
    v=num(q.get('last')); p=num(q.get('previous_day_closing'))
    return ((v/p)-1)*100 if v is not None and p not in (None,0) and v!=p else None

def fresh(q):
    t=q.get('last_time') or q.get('last_timedate') or 'timestamp unavailable'
    # CNBC sometimes returns only YYYY-MM-DD for equities outside their active quote session.
    return ('CNBC previous close · '+t) if len(str(t))==10 else ('CNBC intraday · '+str(t))

def is_intraday(q,now):
    t=str(q.get('last_time') or q.get('last_timedate') or '')
    return len(t)>10 and t[:10]==now.strftime('%Y-%m-%d')

def equity_session(now):
    mins=now.hour*60+now.minute
    if 4*60 <= mins < 9*60+30: return 'premarket'
    if 9*60+30 <= mins < 16*60: return 'regular'
    if 16*60 <= mins < 20*60: return 'afterhours'
    return 'closed'

def quoted_move(q,session):
    # CNBC's main change_pct is the regular-session move vs prior close.
    # POST_MKT ExtendedMktQuote.change_pct is the after-hours move vs the cash close.
    if session=='afterhours':
        ex=q.get('ExtendedMktQuote') or {}
        if ex.get('type')=='POST_MKT' and ex.get('change_pct') not in (None,''):
            return num(ex.get('change_pct'))
    if session=='regular' and is_intraday(q,datetime.datetime.now(NY)):
        return num(q.get('change_pct')) if q.get('change_pct') not in (None,'') else pct(q)
    return None

def equity_quote_available(q,session):
    if session=='regular': return is_intraday(q,datetime.datetime.now(NY))
    if session=='afterhours':
        ex=q.get('ExtendedMktQuote') or {}
        return ex.get('type')=='POST_MKT' and ex.get('change_pct') not in (None,'')
    return False

def setrow(rows,name,latest,direction,signal,freshness,source='CNBC quote feed',explanation=None):
    r=next(x for x in rows if x['factor']==name); r.update(latest=latest,direction=direction,signal=signal,freshness=freshness,source=source)
    if explanation is not None: r['explanation']=explanation

def explain_current_rows(rows):
    # Regenerate explanations from current values and selected related factors.
    by={r['factor']:r for r in rows}
    def tone(r):
        return {'positive':'supportive','negative':'a headwind','mixed':'neutral/mixed'}.get(r.get('signal'),'neutral/mixed')
    def latest(name):
        return by.get(name,{}).get('latest','unavailable')
    def signal(name):
        return by.get(name,{}).get('signal','mixed')
    def direction(name):
        return by.get(name,{}).get('direction','unknown').lower()
    def live(name):
        r=by.get(name,{})
        return bool(r) and 'Awaiting' not in r.get('latest','') and not str(r.get('freshness','')).startswith('STALE')

    for r in rows:
        n=r['factor']; x=r.get('latest',''); d=r.get('direction',''); t=tone(r)
        if n=='10Y Treasury Yield' or n=='2Y Treasury yield':
            level={'positive':'supportive','negative':'a headwind','mixed':'neutral/mixed'}.get(r.get('levelSignal'),'neutral/mixed')
            move='supportive because yields fell' if r.get('changeSignal')=='positive' else ('a headwind because yields rose' if r.get('changeSignal')=='negative' else 'roughly neutral')
            other='2Y Treasury yield' if n=='10Y Treasury Yield' else '10Y Treasury Yield'
            confirm=''
            if live(other):
                od=by[other].get('changeSignal','mixed')
                confirm=(' The other key Treasury maturity is also falling, confirming near-term easing in rate pressure.' if od==r.get('changeSignal')=='positive' else (' The other key Treasury maturity is also rising, confirming broader near-term rate pressure.' if od==r.get('changeSignal')=='negative' else ' The two Treasury maturities are not giving a fully aligned change signal.'))
            real=f" The latest 10Y real yield is {r.get('realYield'):.2f}% ({r.get('realYieldDate','latest Treasury close')}), so the real discount-rate backdrop remains {'a headwind' if r.get('realYield')>=2.0 else 'less restrictive'}." if n=='10Y Treasury Yield' and r.get('realYield') is not None else ''
            curve=(f" Curve context: {r.get('curveContext')}." if r.get('curveContext') else '')
            r['explanation']=f'{x}. Level: {level}. Latest change: {move}.{confirm}{curve}{real}'
        elif n=='Semiconductor leadership':
            breadth=f" Market breadth is {direction('Market breadth')} ({latest('Market breadth')})." if live('Market breadth') else ''
            mega=f" Mega-cap leadership is {direction('Mega-cap leadership')}." if live('Mega-cap leadership') else ''
            r['explanation']=f'{x}. Semiconductors are {d.lower()}. Chips are a major Nasdaq/AI leadership group, so relative strength versus QQQ is an important risk-appetite confirmation. Current implication: {t}.{breadth}{mega}'
        elif n=='Mega-cap leadership':
            breadth=f" Breadth is {direction('Market breadth')}; {'broad participation confirms the move' if signal('Market breadth')=='positive' else 'the wider market is not giving equally strong confirmation' if signal('Market breadth')=='negative' else 'the wider market is giving only partial confirmation'}." if live('Market breadth') else ''
            semi=f" Semiconductor leadership is {direction('Semiconductor leadership')}." if live('Semiconductor leadership') else ''
            r['explanation']=f'{x}. The mega-cap basket is {d.lower()}. Nasdaq is more durable when its largest weights participate rather than the index being carried by a narrow subset. Current implication: {t}.{breadth}{semi}'
        elif n=='S&P 500 50D Breadth / Oversold':
            r['explanation']=f'{x}. This is the percentage of S&P 500 stocks above their 50-day moving average. NasBoard interprets it as both breadth and an oversold/extended condition: low readings show weak participation, but a turn upward from below 30% can be an early recovery signal rather than simply bearish. Current state: {d.lower()}.'
        elif n=='Market breadth':
            leaders=[]
            if live('Semiconductor leadership'): leaders.append('semiconductors are '+direction('Semiconductor leadership'))
            if live('Mega-cap leadership'): leaders.append('mega-caps are '+direction('Mega-cap leadership'))
            context=(' At the same time, '+ ' and '.join(leaders)+'.') if leaders else ''
            r['explanation']=f'{x}. Breadth is {d.lower()}. A larger share of advancing Nasdaq-100 constituents means wider participation; weak participation makes index strength less robust. Current implication: {t}.{context}'
        elif n=='Earnings AVWAP leadership':
            r['explanation']=f"{x}. The selective semiconductor/AI basket is {d.lower()}. Holding above a post-earnings AVWAP is supportive because price remains above the volume-weighted cost basis established since the latest earnings reset; large positive distances also contribute to Consolidation Risk as extension."
        elif n=='Nasdaq volatility (VXN / VIX)':
            if d=='Diverging':
                interp='VXN and VIX are moving in opposite directions, so Nasdaq-specific and broad-market volatility do not confirm each other.'
            elif d=='Falling together':
                interp='VXN and VIX are falling together, confirming reduced demand for near-term protection.'
            elif d=='Rising together':
                interp='VXN and VIX are rising together, confirming increasing demand for protection.'
            else:
                interp='The two volatility gauges are not producing a strong aligned move.'
            context=''
            if live('10Y Treasury Yield') and live('2Y Treasury yield'):
                context=f" Rate levels remain {tone(by['10Y Treasury Yield'])} at the 10Y and {tone(by['2Y Treasury yield'])} at the 2Y."
            vm=re.search(r'VXN ([0-9.]+).*?VIX ([0-9.]+)',str(r.get('latest','')))
            regime_text=''
            if vm:
                vxn_l=float(vm.group(1)); vix_l=float(vm.group(2))
                vxn_band='very low' if vxn_l<=15 else ('low' if vxn_l<=18 else ('normal/moderate' if vxn_l<=23 else ('elevated' if vxn_l<=28 else ('high' if vxn_l<=33 else 'stress'))))
                vix_band='very low' if vix_l<=12 else ('low' if vix_l<=15 else ('normal/moderate' if vix_l<=20 else ('elevated' if vix_l<=25 else ('high' if vix_l<=30 else 'stress'))))
                regime_text=f' VXN is in a {vxn_band} regime; VIX is {vix_band}.'
            r['explanation']=f'{x}. {interp}{regime_text} NasBoard weights VXN regime 50%, VIX regime 20%, VXN movement 20% and VIX movement 10%. Overall volatility signal: {t}.{context}'
        elif n=='Credit conditions':
            vol=f" Volatility is also {direction('Nasdaq volatility (VXN / VIX)')}, providing {'consistent risk-on confirmation' if signal('Nasdaq volatility (VXN / VIX)')=='positive' and r.get('signal')=='positive' else 'a separate cross-check on risk appetite'}." if live('Nasdaq volatility (VXN / VIX)') else ''
            r['explanation']=f'{x}. HYG versus LQD is a liquid credit-risk proxy: stronger high-yield relative performance suggests easier/risk-on conditions, while underperformance suggests tightening. Credit is {d.lower()} and {t}.{vol}'
        elif n=='Oil (WTI / Brent)':
            rates=f" The 10Y yield is {latest('10Y Treasury Yield')}; oil matters for Nasdaq mainly through inflation expectations and the rate path." if live('10Y Treasury Yield') else ''
            r['explanation']=f'{x}. Oil is {d.lower()}. Large energy moves can alter inflation expectations and therefore Treasury yields/Fed expectations. Current implication: {t}.{rates}'
        elif n=='Options positioning / sentiment':
            vol=f" VXN/VIX are {direction('Nasdaq volatility (VXN / VIX)')} ({latest('Nasdaq volatility (VXN / VIX)')}), so options positioning and implied volatility together {'lean toward improving risk appetite' if signal('Nasdaq volatility (VXN / VIX)')=='positive' and r.get('signal')=='positive' else 'do not currently give the same strong directional signal'}." if live('Nasdaq volatility (VXN / VIX)') else ''
            r['explanation']=f'{x}. Equity put/call is compared with its 5-session baseline; Index and Total P/C add context because index puts often reflect institutional hedging. Positioning is {d.lower()} and {t}; this is not dealer gamma. {vol}'.strip()
        elif n=='Fed expectations':
            # Preserve the detailed probability explanation generated by the Fed futures model.
            if not r.get('explanation') or 'market-implied' not in r.get('freshness','').lower():
                yields=f" Current rate-market context: 2Y {latest('2Y Treasury yield')} and 10Y {latest('10Y Treasury Yield')}." if live('2Y Treasury yield') and live('10Y Treasury Yield') else ''
                r['explanation']=f'{x}. Market-implied Fed expectations are temporarily unavailable. {yields}'.strip()
        elif n=='Economic / inflation data':
            yields=f" With 2Y at {latest('2Y Treasury yield')} and 10Y at {latest('10Y Treasury Yield')}, a surprise that shifts inflation/Fed expectations can feed quickly into Nasdaq discount rates." if live('2Y Treasury yield') and live('10Y Treasury Yield') else ''
            if r.get('surprise') is not None:
                r['explanation']=f"{x}. This factor measures the latest macro release against market consensus—not event proximity. {r.get('surpriseText','')} Current implication: {t}.{yields}".strip()
            else:
                r['explanation']=f"{x}. No verified actual-versus-consensus macro surprise is currently stored, so the factor stays neutral rather than treating an upcoming event as bullish or bearish.{yields}".strip()
        else:
            r['explanation']=f'Current reading: {x}. Direction: {d}. NasBoard currently classifies this factor as {t}. This row will become more specific as its underlying live/research source is automated.'

def cme_fedwatch_aggregated():
    # Best-effort public FedWatch page scrape. CME renders the probability tool in an iframe,
    # so this intentionally fails closed if the aggregated table is not present in returned HTML.
    url='https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,*/*'})
    with urllib.request.urlopen(req,timeout=25) as r: html=r.read().decode('utf-8',errors='replace')
    # Preserve diagnostics for discovering CME's current embedded/public data path without
    # inventing probabilities. We only publish values once a real aggregate table is parsed.
    meetings=re.findall(r'(?:Meeting Date|FOMC)[^<]{0,80}?(\\d{1,2}/\\d{1,2}/\\d{4})',html,re.I)
    rates=re.findall(r'(\\d+\\.\\d+%?)\\s*[-–]\\s*(\\d+\\.\\d+%?)',html)
    probs=re.findall(r'(\\d{1,3}\\.\\d{1,2})%',html)
    return {'url':url,'htmlBytes':len(html),'meetingCandidates':meetings[:10],
            'rateRangeCandidates':rates[:20],'probabilityCandidates':probs[:40],
            'hasAggregated':bool(re.search(r'Aggregated',html,re.I))}


def eoddata_s5fi():
    """Fetch S5FI from EODData's server-rendered INDEX/S5FI page."""
    url='https://www.eoddata.com/stockquote/INDEX/S5FI.htm'
    req=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36',
        'Accept':'text/html,application/xhtml+xml,*/*',
        'Accept-Language':'en-US,en;q=0.9'
    })
    with urllib.request.urlopen(req,timeout=20) as r:
        html=r.read().decode('utf-8',errors='replace')
    clean=re.sub(r'<[^>]+>',' ',html)
    clean=re.sub(r'&nbsp;|&#160;',' ',clean)
    clean=re.sub(r'\\s+',' ',clean)
    # Prefer the explicit LAST/PREV fields on the quote page.
    lm=re.search(r'LAST:\s*([0-9]+(?:\\.[0-9]+)?)',clean,re.I)
    pm=re.search(r'PREV:\s*([0-9]+(?:\\.[0-9]+)?)',clean,re.I)
    dm=re.search(r'(\\d{1,2}\s+[A-Za-z]{3}\s+\\d{2})\s+\\d{1,2}:\\d{2}',clean)
    last=float(lm.group(1)) if lm else None
    previous=float(pm.group(1)) if pm else None
    if last is None or not (0 <= last <= 100):
        # Fallback to the first two Recent End of Day close observations.
        pairs=re.findall(r'(\\d{1,2}\s+[A-Za-z]{3}\s+\\d{2})\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)',clean)
        if pairs:
            last=float(pairs[0][4])
            if len(pairs)>1: previous=float(pairs[1][4])
    if last is None or not (0 <= last <= 100):
        raise ValueError('EODData S5FI value not parseable')
    obs_date=None
    if dm:
        try: obs_date=datetime.datetime.strptime(dm.group(1),'%d %b %y').date().isoformat()
        except Exception: pass
    return {'last':last,'previous':previous,'date':obs_date,'url':url}

def barchart_zq_prices():
    """Free delayed ZQ quotes from Barchart's public Websol quote pages."""
    symbols=['ZQV26','ZQX26','ZQZ26','ZQF27','ZQG27','ZQH27']
    out={}; stamps={}
    for sym in symbols:
        url='https://barchart.websol.barchart.com/?1_selected=futureQuote&lang=en&module=futureDetail&region=US&symbol='+sym
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,*/*'})
        with urllib.request.urlopen(req,timeout=20) as r: html=r.read().decode('utf-8',errors='replace')
        m=re.search(r'Last\\s*</[^>]+>\\s*<[^>]+>\\s*([0-9]{2}\\.[0-9]{3,5})',html,re.I|re.S)
        if not m:
            # Fallback for alternate Websol rendering: first price after the "Last" label.
            m=re.search(r'Last.{0,600}?([0-9]{2}\\.[0-9]{3,5})',html,re.I|re.S)
        if not m: raise ValueError('Barchart ZQ quote not parseable for '+sym)
        out[sym]=float(m.group(1))
        tm=re.search(r'as of\\s+([^<\\n]+)',html,re.I)
        if tm: stamps[sym]=re.sub(r'\\s+',' ',tm.group(1)).strip()
    return out,stamps,'https://barchart.websol.barchart.com/'


def latest_effr():
    """Latest official effective fed funds rate from the Federal Reserve H.15 page."""
    url='https://www.federalreserve.gov/releases/h15/'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,*/*'})
    with urllib.request.urlopen(req,timeout=20) as r: html=r.read().decode('utf-8',errors='replace')
    # Capture the Federal funds (effective) row and use its last published numeric observation.
    m=re.search(r'Federal funds \\(effective\\).{0,5000}?</tr>',html,re.I|re.S)
    if not m: raise ValueError('EFFR row not found in H.15')
    vals=[float(x) for x in re.findall(r'>\\s*([0-9]+\\.[0-9]+)\\s*<',m.group(0))]
    if not vals: raise ValueError('EFFR value not found in H.15')
    return vals[-1],url

def fed_meeting_probabilities(now):
    """Approximate CME-style conditional hike/hold/cut probabilities from ZQ futures."""
    import calendar
    prices,price_stamps,price_url=barchart_zq_prices()
    effr,effr_url=latest_effr()
    meetings=[
      (datetime.date(2026,10,28),'Oct 28','ZQV26',effr),
      (datetime.date(2026,12,9),'Dec 9','ZQZ26',100-prices['ZQX26']),
      (datetime.date(2027,1,27),'Jan 27','ZQF27',None),
    ]
    results=[]; prior_end=None
    for dt,label,sym,start in meetings:
        if dt < now.date(): continue
        if start is None: start=prior_end
        avg=100-prices[sym]
        days=calendar.monthrange(dt.year,dt.month)[1]
        pre=dt.day-1; post=days-pre
        end=(avg*days-start*pre)/post
        change_bp=(end-start)*100
        units=change_bp/25.0
        if units>=0:
            whole=int(units); frac=max(0,min(1,units-whole))
            if whole==0: probs={'hike':frac*100,'hold':(1-frac)*100,'cut':0.0}
            else: probs={'hike':100.0,'hold':0.0,'cut':0.0}
        else:
            u=-units; whole=int(u); frac=max(0,min(1,u-whole))
            if whole==0: probs={'hike':0.0,'hold':(1-frac)*100,'cut':frac*100}
            else: probs={'hike':0.0,'hold':0.0,'cut':100.0}
        results.append({'date':dt.isoformat(),'label':label,'contract':sym,'price':prices[sym],
                        'startEFFR':start,'impliedEndEFFR':end,'changeBp':change_bp,'probabilities':probs})
        prior_end=end
    return results,{'priceSource':price_url,'priceTimestamps':price_stamps,'effrSource':effr_url,'effr':effr,'prices':prices}

def treasury_10y_real(year):
    url='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_real_yield_curve&field_tdr_date_value='+str(year)
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/xml,text/xml,*/*'})
    with urllib.request.urlopen(req,timeout=20) as r: raw=r.read()
    root=ET.fromstring(raw); points=[]
    for props in root.iter():
        if not str(props.tag).endswith('properties'): continue
        vals={str(x.tag).split('}')[-1]: (x.text or '').strip() for x in list(props)}
        date=vals.get('NEW_DATE') or vals.get('new_date')
        y10=vals.get('TC_10YEAR') or vals.get('tc_10year')
        if date and y10:
            try: points.append((datetime.datetime.fromisoformat(date.replace('Z','+00:00')).date(),float(y10)))
            except: pass
    if not points: raise ValueError('Treasury TC_10YEAR real yield not found in XML feed')
    points.sort(); return points[-1]

def cboe_put_call(day=None):
    url='https://www.cboe.com/markets/us/options/market-statistics/daily'
    if day is not None: url += '?dt='+day.isoformat()
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,*/*'})
    with urllib.request.urlopen(req,timeout=20) as r: html=r.read().decode('utf-8',errors='replace')
    labels={'total':r'TOTAL PUT/CALL RATIO','index':r'INDEX PUT/CALL RATIO','equity':r'EQUITY PUT/CALL RATIO'}
    out={}
    for k,label in labels.items():
        m=re.search(label+r'.{0,500}?([0-9]+\.[0-9]+)',html,re.I|re.S)
        if not m: raise ValueError('Cboe '+k+' put/call ratio not found')
        out[k]=float(m.group(1))
    return out

def cboe_put_call_5d(now):
    vals=[]; day=now.date(); attempts=0
    while len(vals)<5 and attempts<12:
        attempts+=1
        if day.weekday()<5:
            try:
                x=cboe_put_call(day)
                vals.append((day,x))
            except Exception:
                pass
        day-=datetime.timedelta(days=1)
    if len(vals)<5: raise ValueError('Fewer than 5 Cboe trading sessions available')
    return vals

def main():
    with open(PATH,encoding='utf-8') as f:d=json.load(f)
    now=datetime.datetime.now(NY); rows=[r for r in d['rows'] if r.get('factor') not in {'AI / data-center financing','System liquidity','U.S. Dollar (DXY)','10Y real yield'}];
    for r in rows:
        if r.get('factor')=='10Y nominal yield': r['factor']='10Y Treasury Yield'
    # Add S&P 500 50-day breadth/oversold as a separate factor. It is intentionally
    # distinct from the session-based Nasdaq breadth row.
    if not any(r.get('factor')=='S&P 500 50D Breadth / Oversold' for r in rows):
        rows.append({
          'factor':'S&P 500 50D Breadth / Oversold',
          'latest':'Awaiting S5FI data source',
          'direction':'Awaiting data',
          'signal':'mixed',
          'freshness':'STALE — S5FI source not yet connected',
          'source':'S5FI — S&P 500 stocks above 50-day moving average',
          'explanation':'S5FI measures the percentage of S&P 500 stocks above their 50-day moving average. NasBoard uses both the breadth level and its direction so an oversold reading is not automatically treated as bearish.',
          'currentImpact':'Low'
        })
    d['rows']=rows
    # Preserve the previous refresh so we can show whether each factor is improving or deteriorating.
    previous={r.get('factor'):{'signal':r.get('signal','mixed'),'currentImpact':r.get('currentImpact','Low'),'latest':r.get('latest','')} for r in rows}
    try:
        q=cnbc_quotes(SYMBOLS)
        # Probe the public CME FedWatch page first. We publish no probability unless the
        # actual aggregated table is retrievable; stale prior values are safer than fabrication.
        try:
            fw=cme_fedwatch_aggregated()
            d.setdefault('diagnostics',{})['cmeFedWatchPublic']=fw
            print('CME FedWatch public probe:',json.dumps(fw))
        except Exception as e:
            d.setdefault('diagnostics',{})['cmeFedWatchPublic']={'error':repr(e)}
            print('CME FedWatch public probe failed:',repr(e))

        # Fed Funds futures probe retained only as a fallback diagnostic.
        zq_probe={}
        for zsym in ['ZQU6','ZQV6','ZQX6','ZQZ6','ZQF7','ZQG7','ZQH7']:
            if zsym in q:
                zx=q[zsym]
                zq_probe[zsym]={k:zx.get(k) for k in ['symbol','name','last','previous_day_closing','last_time','last_timedate','code']}
        d.setdefault('diagnostics',{})['fedFundsFutures']=zq_probe
        print('Fed Funds futures CNBC probe:',json.dumps(zq_probe))

        # S5FI probe: S&P 500 stocks above 50-day moving average breadth index.
        # Keep this as a source test until CNBC symbol availability is verified in a real Action run.
        if 'S5FI' in q:
            sx=q['S5FI']
            print('S5FI CNBC probe:', json.dumps({k:sx.get(k) for k in ['symbol','name','last','previous_day_closing','last_time','last_timedate','code']}))
        else:
            print('S5FI CNBC probe: symbol not returned')

        # Probe PHLX Semiconductor Index symbols through the existing CNBC quote service.
        # This is diagnostic first: once a returned symbol is confirmed, NasBoard can use its
        # last/previous-close pair for the 1-day SOX move without adding another provider.
        sox_probe={'tested':['.SOX','SOX'],'returned':[]}
        for sox_symbol in ('.SOX','SOX'):
            if sox_symbol in q:
                sx=q[sox_symbol]
                item={k:sx.get(k) for k in ['symbol','name','last','previous_day_closing','change_pct','last_time','last_timedate','code']}
                item['oneDayPct']=pct(sx)
                sox_probe['returned'].append(item)
                print('SOX CNBC probe:', sox_symbol, json.dumps(item))
        sox_probe['status']='supported' if sox_probe['returned'] else 'not_returned'
        d['diagnostics']=d.get('diagnostics',{})
        d['diagnostics']['cnbcSOX']=sox_probe

        # Treasury yields
        for sym,name in [('US10Y','10Y Treasury Yield'),('US2Y','2Y Treasury yield')]:
            x=q.get(sym); v=num(x.get('last')) if x else None; p=num(x.get('previous_day_closing')) if x else None; bp=(v-p)*100 if v is not None and p is not None else None
            if v is None:
                rr=next((z for z in rows if z['factor']==name),None)
                if rr: rr['freshness']='STALE — Treasury quote unavailable'
                continue
            level_sig='negative' if v>=4.5 else ('mixed' if v>=4.0 else 'positive')
            change_sig='negative' if bp is not None and bp>1 else ('positive' if bp is not None and bp<-1 else 'mixed')
            # Dashboard Signal should describe the current market impulse. Keep the absolute
            # yield level separately because a high level can remain a valuation headwind
            # even while a falling yield is supportive for today's Nasdaq session.
            # Keep structural level and short-term momentum separate. The row's overall
            # signal blends both; cards expose each dimension independently.
            if level_sig==change_sig: sig=level_sig
            elif change_sig=='mixed': sig=level_sig
            elif level_sig=='mixed': sig=change_sig
            else: sig='mixed'
            setrow(rows,name,f'{v:.3f}%'+(f' ({bp:+.1f} bp vs prev close)' if bp is not None else ''),'Rising' if bp and bp>0 else ('Falling' if bp and bp<0 else 'Flat'),sig,fresh(x),'CNBC / Tradeweb quote feed')
            rr=next(z for z in rows if z['factor']==name)
            rr['levelSignal']=level_sig
            rr['changeSignal']=change_sig

        # Derived 2s10s curve context: 10Y minus 2Y. Store level and daily change,
        # but keep it as background context rather than a separate dashboard factor.
        y10=q.get('US10Y',{}); y2=q.get('US2Y',{})
        y10v=num(y10.get('last')); y2v=num(y2.get('last'))
        y10p=num(y10.get('previous_day_closing')); y2p=num(y2.get('previous_day_closing'))
        curve_2s10s=None; curve_change=None; curve_regime=None
        if y10v is not None and y2v is not None:
            curve_2s10s=(y10v-y2v)*100
            if y10p is not None and y2p is not None:
                curve_change=curve_2s10s-(y10p-y2p)*100
            curve_regime='inverted' if curve_2s10s < -5 else ('flat' if curve_2s10s <= 5 else 'upward-sloping')
            # Classify the mechanism using each maturity's daily bp move.
            d10=(y10v-y10p)*100 if y10p is not None else None
            d2=(y2v-y2p)*100 if y2p is not None else None
            mechanism='stable'
            if d10 is not None and d2 is not None and abs(d10-d2)>=0.5:
                if curve_change > 0:
                    mechanism='bull steepener' if d2 < d10 and d2 < 0 else 'bear steepener'
                elif curve_change < 0:
                    mechanism='bear flattener' if d2 > d10 and d2 > 0 else 'bull flattener'
            curve_text=f"2s10s {curve_2s10s:+.1f} bp ({curve_regime})"
            if curve_change is not None:
                curve_text+=f", {mechanism}, {curve_change:+.1f} bp vs prev close"
            for nm in ('10Y Treasury Yield','2Y Treasury yield'):
                rr=next((z for z in rows if z['factor']==nm),None)
                if rr:
                    rr['curve2s10s']={'spreadBp':round(curve_2s10s,1),'changeBp':round(curve_change,1) if curve_change is not None else None,
                                      'shape':curve_regime,'mechanism':mechanism}
                    rr['curveContext']=curve_text

        # Add the daily 10Y real yield as context inside the single 10Y Treasury factor.
        try:
            real_date,real_value=treasury_10y_real(now.year)
            rr=next(z for z in rows if z['factor']=='10Y Treasury Yield')
            rr['realYield']=real_value; rr['realYieldDate']=real_date.isoformat()
            rr['source']='CNBC / Tradeweb quote feed; U.S. Treasury 10Y TIPS real yield context'
        except Exception as e:
            print('10Y real yield context unavailable:',e)

        # Session-aware equity leadership. CNBC currently exposes reliable regular-session
        # and POST_MKT extended quotes. Its premarket ExtendedMktQuote is not consistently populated,
        # so premarket is explicitly left unavailable rather than mixing yesterday's close into today.
        semis=['NVDA','AMD','AVGO','TSM','MU']
        session=equity_session(now)
        session_label={'regular':'Live','afterhours':'After-hours','premarket':'Premarket','closed':'Closed'}[session]
        equity_available='QQQ' in q and equity_quote_available(q['QQQ'],session)

        if equity_available and all(sym in q and equity_quote_available(q[sym],session) for sym in semis):
            moves={sym:quoted_move(q[sym],session) for sym in semis}; qqq=quoted_move(q['QQQ'],session)
            valid=[v for v in moves.values() if v is not None]
            if valid and qqq is not None:
                avg=sum(valid)/len(valid); rel=avg-qqq; pos=sum(v>0 for v in valid)
                smh_move=quoted_move(q['SMH'],session) if 'SMH' in q and equity_quote_available(q['SMH'],session) else None
                smh_rel=(smh_move-qqq) if smh_move is not None else None
                # Primary signal is the equal-weight five-stock leadership basket vs QQQ.
                # SMH acts as confirmation: agreement strengthens the read; disagreement flags narrow/mixed leadership.
                basket_dir=1 if rel>0.25 else (-1 if rel<-0.25 else 0)
                smh_dir=1 if smh_rel is not None and smh_rel>0.25 else (-1 if smh_rel is not None and smh_rel<-0.25 else 0)
                if basket_dir>0 and smh_dir>=0: sig='positive'; direction='Leading QQQ' if smh_dir==0 else 'Confirmed leadership'
                elif basket_dir<0 and smh_dir<=0: sig='negative'; direction='Lagging QQQ' if smh_dir==0 else 'Confirmed weakness'
                elif basket_dir>0 and smh_dir<0: sig='mixed'; direction='Narrow leader strength'
                elif basket_dir<0 and smh_dir>0: sig='mixed'; direction='Broader semis holding up'
                else: sig='mixed'; direction='In line with QQQ'
                smh_txt=f' | SMH {smh_move:+.2f}% | SMH vs QQQ {smh_rel:+.2f} pp' if smh_move is not None else ' | SMH confirmation unavailable'
                txt=session_label+' · '+f'5-stock basket {avg:+.2f}% | {pos}/5 positive | QQQ {qqq:+.2f}% | basket vs QQQ {rel:+.2f} pp'+smh_txt
                setrow(rows,'Semiconductor leadership',txt,direction,sig,session_label+' CNBC quote','CNBC quotes; session-aware equal-weight NVDA/AMD/AVGO/TSM/MU vs QQQ, confirmed by SMH vs QQQ')
        else:
            msg='Premarket quote unavailable from CNBC extended-hours feed' if session=='premarket' else f'Awaiting {session_label.lower()} equity quotes'
            setrow(rows,'Semiconductor leadership',msg,'Awaiting session','mixed',session_label+' — insufficient current equity data','CNBC quotes; no previous-close substitution')

        # Mega-cap leadership, regular session or reliable CNBC POST_MKT quotes.
        if equity_available:
            mm={sym:quoted_move(q[sym],session) for sym in MEGACAPS if sym in q and equity_quote_available(q[sym],session)}
            vals=[v for v in mm.values() if v is not None]; qqq=quoted_move(q['QQQ'],session)
            if len(vals)>=5 and qqq is not None:
                avg=sum(vals)/len(vals); rel=avg-qqq; pos=sum(v>0 for v in vals)
                if rel>0.20 and pos>=4: sig='positive'; direction='Leading QQQ'
                elif qqq>0 and pos>=6 and rel>=-0.20: sig='positive'; direction='Broad participation'
                elif rel<-0.20 and pos<=3: sig='negative'; direction='Lagging QQQ'
                elif qqq<0 and pos<=1 and rel<=0.20: sig='negative'; direction='Broad weakness'
                else: sig='mixed'; direction='In line with QQQ'
                setrow(rows,'Mega-cap leadership',f'{session_label} · {len(vals)}-stock basket {avg:+.2f}% | {pos}/{len(vals)} positive | QQQ {qqq:+.2f}% | relative {rel:+.2f} pp',direction,sig,session_label+' CNBC quote','CNBC quotes; session-aware mega-cap basket vs QQQ')
            else:
                setrow(rows,'Mega-cap leadership',f'{session_label} · insufficient mega-cap quote coverage','Awaiting coverage','mixed',session_label+' — partial coverage','CNBC quotes')
        else:
            msg='Premarket quote unavailable from CNBC extended-hours feed' if session=='premarket' else f'Awaiting {session_label.lower()} mega-cap quotes'
            setrow(rows,'Mega-cap leadership',msg,'Awaiting session','mixed',session_label+' — insufficient current equity data','CNBC quotes; no previous-close substitution')

        # Breadth hierarchy: live regular-session breadth first; after-hours breadth when coverage
        # is sufficient; otherwise use the most recent regular-session breadth as explicitly labelled context.
        bm={sym:quoted_move(q[sym],session) for sym in BREADTH if sym in q and equity_quote_available(q[sym],session)}
        vals=[v for v in bm.values() if v is not None]
        min_coverage=80 if session=='regular' else 40
        breadth_set=False
        if session in ('regular','afterhours') and len(vals)>=min_coverage:
            adv=sum(v>0 for v in vals); dec=sum(v<0 for v in vals); flat=len(vals)-adv-dec; ratio=adv/len(vals)*100
            sig='positive' if ratio>=65 else ('negative' if ratio<=35 else 'mixed')
            direction='Broadening' if ratio>=65 else ('Weakening' if ratio<=35 else 'Mixed')
            label='Nasdaq-100 breadth' if session=='regular' else 'After-hours breadth'
            setrow(rows,'Market breadth',f'{session_label} · {label}: {adv}/{len(vals)} advancing ({ratio:.0f}%) · {dec} declining · {flat} flat',direction,sig,session_label+' CNBC constituent quotes','CNBC quotes; session-aware Nasdaq-100 constituent breadth')
            breadth_set=True
        if not breadth_set:
            # CNBC's delayed equity snapshot still carries the prior regular-session change_pct.
            prev_moves={sym:num(q[sym].get('change_pct')) for sym in BREADTH if sym in q and q[sym].get('change_pct') not in (None,'')}
            pv=[v for v in prev_moves.values() if v is not None]
            if len(pv)>=80:
                adv=sum(v>0 for v in pv); dec=sum(v<0 for v in pv); flat=len(pv)-adv-dec; ratio=adv/len(pv)*100
                sig='positive' if ratio>=65 else ('negative' if ratio<=35 else 'mixed')
                direction='Broad participation' if ratio>=65 else ('Weak participation' if ratio<=35 else 'Mixed participation')
                stamps=[str(q[sym].get('last_timedate') or q[sym].get('last_time') or '') for sym in BREADTH if sym in q]
                dated=[x for x in stamps if re.search(r'\d{2}/\d{2}/\d{2}',x)]
                stamp=dated[0] if dated else 'most recent regular session'
                setrow(rows,'Market breadth',f'Previous close · Nasdaq-100 breadth: {adv}/{len(pv)} advancing ({ratio:.0f}%) · {dec} declining · {flat} flat',direction,sig,f'Previous regular session · {stamp}','CNBC quotes; previous regular-session Nasdaq-100 constituent breadth')
            else:
                setrow(rows,'Market breadth',f'Previous-close breadth unavailable — only {len(pv)} constituent quotes','Awaiting coverage','mixed','STALE — insufficient breadth coverage','CNBC quotes')

        # S5FI: percentage of S&P 500 stocks above their 50-day MA.
        # CNBC does not currently return this symbol in our feed, so publish it only when
        # a real quote is available; otherwise keep the row explicitly stale.
        # EODData is the sole primary source for S5FI. It exposes the breadth index
        # in server-rendered HTML, which is suitable for deterministic GitHub Actions refreshes.
        sx=None; s5_source=None; s5_freshness=None
        try:
            ex=eoddata_s5fi()
            sx={'last':str(ex['last']),'previous_day_closing':str(ex['previous']) if ex['previous'] is not None else ''}
            s5_source='EODData INDEX:S5FI'
            s5_freshness='EODData EOD'+((' · '+ex['date']) if ex.get('date') else '')
        except Exception as e:
            print('EODData S5FI unavailable:',repr(e))
        if sx and num(sx.get('last')) is not None:
            sv=num(sx.get('last')); sp=num(sx.get('previous_day_closing'))
            delta=(sv-sp) if sp is not None else None
            rising=delta is not None and delta>=1.0
            falling=delta is not None and delta<=-1.0
            if sv<30:
                # Oversold is weak breadth, but an upturn is an early recovery signal.
                sig='positive' if rising else ('negative' if falling else 'mixed')
                direction='Oversold, recovering' if rising else ('Oversold, deteriorating' if falling else 'Oversold')
            elif sv<40:
                sig='mixed' if rising else ('negative' if falling else 'mixed')
                direction='Weak, improving' if rising else ('Weak, deteriorating' if falling else 'Weak breadth')
            elif sv<=60:
                sig='positive' if rising else ('negative' if falling else 'mixed')
                direction='Broadening' if rising else ('Narrowing' if falling else 'Neutral breadth')
            elif sv<=70:
                sig='positive' if not falling else 'mixed'
                direction='Healthy breadth' if not falling else 'Healthy, weakening'
            else:
                # >70 is broad participation/extended breadth, not automatically bearish.
                sig='positive' if not falling else 'mixed'
                direction='Very broad / extended' if not falling else 'Extended, cooling'
            move=f' · {delta:+.1f} pp vs prior' if delta is not None else ''
            setrow(rows,'S&P 500 50D Breadth / Oversold',f'{sv:.1f}% above 50D MA{move}',direction,sig,s5_freshness or 'Current',s5_source or 'S5FI')
        else:
            rr=next((z for z in rows if z['factor']=='S&P 500 50D Breadth / Oversold'),None)
            if rr:
                rr['freshness']='STALE — S5FI source not yet connected'
                rr['latest']='Awaiting S5FI data source'

        # Volatility: VXN is Nasdaq-specific; VIX is included as confirmation.
        vx=q.get('.VXN'); vi=q.get('.VIX')
        if vx and vi:
            vxn=num(vx.get('last')); vix=num(vi.get('last')); vxnp=pct(vx); vixp=pct(vi)
            # Nasdaq volatility model: absolute regime dominates short-term movement.
            # VXN is primary because NasBoard models Nasdaq; VIX confirms broad-market stress.
            def vol_regime_score(value,levels):
                if value is None: return 0.0
                a,b,c,d,e=levels
                if value<=a: return 1.0
                if value<=b: return 0.70
                if value<=c: return 0.20
                if value<=d: return -0.40
                if value<=e: return -0.70
                return -1.0
            vxn_reg=vol_regime_score(vxn,(15,18,23,28,33))
            vix_reg=vol_regime_score(vix,(12,15,20,25,30))
            vxn_move=max(-1,min(1,-(vxnp or 0)/8.0))
            vix_move=max(-1,min(1,-(vixp or 0)/8.0))
            vol_score=0.50*vxn_reg+0.20*vix_reg+0.20*vxn_move+0.10*vix_move
            sig='positive' if vol_score>=0.20 else ('negative' if vol_score<=-0.20 else 'mixed')
            if vxnp is not None and vixp is not None and vxnp<0 and vixp<0: direction='Falling together'
            elif vxnp is not None and vixp is not None and vxnp>0 and vixp>0: direction='Rising together'
            elif vxnp is not None and vixp is not None and vxnp*vixp<0: direction='Diverging'
            else: direction='Mixed / flat'
            setrow(rows,'Nasdaq volatility (VXN / VIX)',f'VXN {vxn:.2f} ({vxnp:+.2f}%) | VIX {vix:.2f} ({vixp:+.2f}%)',direction,sig,fresh(vx),'CNBC / Cboe quotes')

        # Credit conditions: HYG risk credit versus investment-grade LQD confirmation.
        hy=q.get('HYG'); lq=q.get('LQD')
        if hy and lq:
            hm=pct(hy); lm=pct(lq)
            if hm is not None and lm is not None:
                rel=hm-lm
                sig='positive' if rel>=0.25 else ('negative' if rel<=-0.25 else 'mixed')
                direction='Easing / risk-on' if rel>=0.25 else ('Tightening / risk-off' if rel<=-0.25 else 'Stable')
                setrow(rows,'Credit conditions',f'HYG {hm:+.2f}% | LQD {lm:+.2f}% | HYG vs LQD {rel:+.2f} pp',direction,sig,fresh(hy),'CNBC quotes; HYG high-yield ETF vs LQD investment-grade ETF proxy')

        # Dollar
        dx=q.get('.DXY')
        if dx:
            v=num(dx.get('last')); m=pct(dx); sig='positive' if m is not None and m<-0.15 else ('negative' if m is not None and m>0.15 else 'mixed')
            setrow(rows,'U.S. Dollar (DXY)',f'DXY {v:.3f} ({m:+.2f}% vs prev close)','Rising' if m and m>0 else ('Falling' if m and m<0 else 'Flat'),sig,fresh(dx),'CNBC / ICE quote feed')

        # Oil
        w=q.get('@CL.1'); b=q.get('@LCO.1')
        if w and b:
            wv=num(w.get('last')); bv=num(b.get('last')); wm=pct(w); bm=pct(b); avg=(wm+bm)/2
            sig='positive' if avg<-1 else ('negative' if avg>1 else 'mixed')
            setrow(rows,'Oil (WTI / Brent)',f'WTI ${wv:.2f} ({wm:+.2f}%) | Brent ${bv:.2f} ({bm:+.2f}%)','Falling' if avg<0 else ('Rising' if avg>0 else 'Flat'),sig,fresh(w),'CNBC futures quotes')

    except Exception as e:
        print('CNBC refresh failed:',repr(e))
        for name in ('10Y Treasury Yield','2Y Treasury yield','Semiconductor leadership','Nasdaq volatility (VXN / VIX)','Oil (WTI / Brent)'):
            rr=next((x for x in rows if x['factor']==name),None)
            if rr: rr['freshness']='STALE — CNBC refresh failed'

    # Official Cboe options-volume put/call ratios. This is sentiment/positioning, not dealer gamma exposure.
    try:
        hist=cboe_put_call_5d(now)
        day,pc=hist[0]; eq,ix,tot=pc['equity'],pc['index'],pc['total']
        avg=sum(x['equity'] for _,x in hist)/len(hist)
        delta=eq-avg
        trend='↑ defensive' if delta>=0.08 else ('↓ call-heavy' if delta<=-0.08 else '→ stable')
        # Level is primary; deviation from the 5-session average adjusts borderline readings.
        score=0
        if eq>=0.90: score-=2
        elif eq>=0.75: score-=1
        elif eq<=0.50: score+=2
        elif eq<=0.60: score+=1
        if delta>=0.08: score-=1
        elif delta<=-0.08: score+=1
        sig='positive' if score>=2 else ('negative' if score<=-2 else 'mixed')
        direction='Defensive / put-heavy' if score<=-2 else ('Call-heavy' if score>=2 else 'Balanced')
        setrow(rows,'Options positioning / sentiment',
          f'Equity P/C {eq:.2f} | 5D avg {avg:.2f} | {trend} | Index {ix:.2f} | Total {tot:.2f}',
          direction,sig,
          f'Cboe daily · latest session {day.isoformat()} · checked {now.strftime("%Y-%m-%d %H:%M ET")}',
          'Cboe Daily Market Statistics — 5-session equity put/call trend; index/total context; not dealer gamma exposure')
    except Exception as e:
        print('Cboe put/call refresh failed:',repr(e))
        r=next(x for x in rows if x['factor']=='Options positioning / sentiment')
        r['freshness']='STALE — Cboe put/call refresh failed'
        r['source']='Cboe Daily Market Statistics — options volume put/call ratios'

    # Economic / inflation data is a SURPRISE factor, not an event-calendar factor.
    # Only verified actual-versus-consensus observations should move its signal. Upcoming
    # releases belong in the pre-market/event-risk layer and must not affect direction.
    macro_surprises=d.get('macroSurprises',[])
    verified=[x for x in macro_surprises if x.get('actual') is not None and x.get('consensus') is not None and x.get('releasedAt')]
    verified.sort(key=lambda x:x.get('releasedAt',''),reverse=True)
    if verified:
        m=verified[0]
        actual=float(m['actual']); consensus=float(m['consensus']); delta=actual-consensus
        # surpriseDirection is explicit because "higher" is not universally bearish:
        # inflation/wage upside is generally a Nasdaq headwind, while labor/growth data
        # can be context-dependent. Unknown mappings fail closed as mixed.
        sd=m.get('surpriseDirection','mixed')
        sig='negative' if sd=='higher_is_negative' and delta>0 else ('positive' if sd=='higher_is_negative' and delta<0 else ('positive' if sd=='higher_is_positive' and delta>0 else ('negative' if sd=='higher_is_positive' and delta<0 else 'mixed')))
        unit=m.get('unit','')
        latest_txt=f"{m.get('name','Macro release')}: {actual:g}{unit} actual vs {consensus:g}{unit} consensus · surprise {delta:+g}{unit}"
        setrow(rows,'Economic / inflation data',latest_txt,'Hotter than expected' if delta>0 else ('Cooler/weaker than expected' if delta<0 else 'In line'),sig,f"Verified release · {m['releasedAt']}",m.get('source','Verified macro release'))
        rr=next(x for x in rows if x['factor']=='Economic / inflation data')
        rr['surprise']=delta; rr['surpriseText']=f"Actual {actual:g}{unit} versus {consensus:g}{unit}; surprise {delta:+g}{unit}."
    else:
        setrow(rows,'Economic / inflation data','Awaiting verified actual vs consensus release','No active surprise','mixed',f'No verified surprise · checked {now.strftime("%Y-%m-%d %H:%M ET")}','NasBoard verified macro-surprise feed')
    # Fed expectations: market-implied conditional move probabilities from 30-Day Fed Funds futures.
    # Fail closed: keep the prior successful row and mark it stale if either public source changes/breaks.
    try:
        fp,meta=fed_meeting_probabilities(now)
        d.setdefault('diagnostics',{})['fedExpectationsModel']=meta
        if fp:
            def fmt(x):
                p=x['probabilities']
                parts=[]
                if p['hike']>=0.5: parts.append(f"Hike {p['hike']:.0f}%")
                if p['hold']>=0.5: parts.append(f"Hold {p['hold']:.0f}%")
                if p['cut']>=0.5: parts.append(f"Cut {p['cut']:.0f}%")
                return x['label']+': '+' / '.join(parts)
            latest_txt=' · '.join(fmt(x) for x in fp[:3])
            first=fp[0]['probabilities']
            net=first['cut']-first['hike']
            sig='positive' if net>=20 else ('negative' if net<=-20 else 'mixed')
            direction='Dovish / cuts priced' if sig=='positive' else ('Hawkish / hikes priced' if sig=='negative' else 'Balanced')
            detail='; '.join(f"{x['label']} ZQ {x['price']:.4f}, implied move {x['changeBp']:+.0f} bp" for x in fp[:3])
            setrow(rows,'Fed expectations',latest_txt,direction,sig,
                   f"Market-implied · checked {now.strftime('%Y-%m-%d %H:%M ET')}",
                   '30-Day Fed Funds futures (Barchart delayed public quotes); Federal Reserve H.15 EFFR; CME FedWatch methodology',
                   f"{latest_txt}. Conditional probabilities are estimated from monthly 30-Day Fed Funds futures using CME FedWatch methodology and the latest official EFFR. {detail}.")
            d['diagnostics']['fedExpectationsModel']['meetings']=fp
    except Exception as e:
        print('Fed expectations model failed:',repr(e))
        d.setdefault('diagnostics',{})['fedExpectationsModel']={'error':repr(e)}
        rr=next((x for x in rows if x['factor']=='Fed expectations'),None)
        if rr: rr['freshness']='STALE — Fed futures probability refresh failed'

    # Earnings AVWAP is a selective leadership factor, not one factor per stock. This
    # avoids double-counting correlated semiconductor names in the Nasdaq Setup score.
    avwap_row,avwap_details=build_earnings_avwap_factor(q)
    rows=[r for r in rows if r.get('factor')!='Earnings AVWAP leadership']
    if avwap_row: rows.append(avwap_row)
    # Individual AVWAP observations belong in history snapshots, not public dashboard.json.

    # Current impact = magnitude of the factor's present Nasdaq effect, not its structural importance.
    # It is intentionally based on current observations/freshness and can change each refresh.
    for r in rows:
        n=r['factor']; imp='Medium'
        freshness=str(r.get('freshness',''))
        if 'Awaiting' in r.get('latest','') or freshness.startswith('STALE'):
            imp='Low'
        elif freshness in ('Research snapshot','Official data lag'):
            # Undated/manual snapshots can provide background direction, but not a defensible current-impact magnitude.
            imp='Low'
        elif n in ('10Y Treasury Yield','2Y Treasury yield'):
            # High absolute yields remain important; a meaningful daily move raises immediate relevance.
            m=re.search(r'\(([+-]?[0-9.]+) bp',r.get('latest',''))
            bp=abs(float(m.group(1))) if m else 0
            imp='Very High' if bp>=5 else ('High' if bp>=2 else 'Medium')
        elif n=='Earnings AVWAP leadership':
            # Broad alignment and large median distance from earnings anchors increase
            # the immediate relevance of this leadership factor.
            md=abs(float(r.get('medianDistancePct',0)))
            cov=int(r.get('coveredCount',0)); above=int(r.get('aboveCount',0))
            aligned=cov>0 and above in (0,cov)
            imp='High' if aligned or md>=5 else ('Medium' if md>=2 else 'Low')
        elif n=='Nasdaq volatility (VXN / VIX)':
            nums=[abs(float(v)) for v in re.findall(r'\(([+-]?[0-9.]+)%\)',r.get('latest',''))]
            mv=max(nums) if nums else 0
            imp='High' if mv>=5 else ('Medium' if mv>=2 else 'Low')
        elif n=='Oil (WTI / Brent)':
            nums=[abs(float(v)) for v in re.findall(r'\(([+-]?[0-9.]+)%\)',r.get('latest',''))]
            mv=max(nums) if nums else 0
            imp='Very High' if mv>=4 else ('High' if mv>=2 else ('Medium' if mv>=1 else 'Low'))
        elif n=='U.S. Dollar (DXY)':
            m=re.search(r'\(([+-]?[0-9.]+)%',r.get('latest','')); mv=abs(float(m.group(1))) if m else 0
            imp='High' if mv>=0.7 else ('Medium' if mv>=0.3 else 'Low')
        elif n=='S&P 500 50D Breadth / Oversold':
            m=re.search(r'([0-9.]+)% above 50D',r.get('latest','')); sv=float(m.group(1)) if m else 50
            # Extremes matter more, especially while still deteriorating; a recovering oversold
            # reading is tactically useful but not treated as a maximum-risk bearish condition.
            dist=abs(sv-50)
            imp='High' if dist>=20 else ('Medium' if dist>=10 else 'Low')
        elif n=='Market breadth':
            m=re.search(r'\(([0-9]+)%\)',r.get('latest','')); adv=float(m.group(1)) if m else 50
            dev=abs(adv-50)
            imp='Very High' if dev>=30 else ('High' if dev>=20 else ('Medium' if dev>=10 else 'Low'))
        elif n in ('Semiconductor leadership','Mega-cap leadership'):
            m=re.search(r'(?:basket vs QQQ|relative) ([+-]?[0-9.]+) pp',r.get('latest','')); mv=abs(float(m.group(1))) if m else 0
            imp='Very High' if mv>=1.5 else ('High' if mv>=0.75 else ('Medium' if mv>=0.25 else 'Low'))
        elif n=='Credit conditions':
            m=re.search(r'HYG vs LQD ([+-]?[0-9.]+) pp',r.get('latest','')); mv=abs(float(m.group(1))) if m else 0
            imp='High' if mv>=0.75 else ('Medium' if mv>=0.25 else 'Low')
        elif n=='Options positioning / sentiment':
            m=re.search(r'Equity P/C ([0-9.]+).*5D avg ([0-9.]+)',r.get('latest',''))
            if m:
                eq,av=map(float,m.groups()); dev=abs(eq-av)
                imp='High' if eq>=0.9 or eq<=0.5 or dev>=0.15 else ('Medium' if eq>=0.75 or eq<=0.55 or dev>=0.08 else 'Low')
        elif n in ('Fed expectations','Economic / inflation data','Technology earnings calendar'):
            # Event impact rises ahead of the catalyst. Earnings can affect positioning well before the report,
            # so the 10-day window is deliberately treated as High.
            event_date=None
            txt=r.get('latest','')
            month_map={'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}
            matches=re.findall(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\b',txt)
            if matches:
                mon,day=matches[0]
                event_date=datetime.datetime(now.year,month_map[mon],int(day),tzinfo=NY)
                if event_date.date()<now.date(): event_date=event_date.replace(year=now.year+1)
            days=((event_date-now).total_seconds()/86400) if event_date else None
            if n=='Technology earnings calendar':
                imp='Very High' if days is not None and days<=5 else ('High' if days is not None and days<=14 else ('Medium' if days is not None and days<=28 else 'Low'))
                # Market-reaction override: major tech earnings can become immediately important before
                # the calendar threshold when Nasdaq/semiconductor price action is already unusually strong.
                # Use only current-session observations; never promote from previous-close/Awaiting data.
                semi=next((z for z in rows if z['factor']=='Semiconductor leadership'),{})
                mega=next((z for z in rows if z['factor']=='Mega-cap leadership'),{})
                vol=next((z for z in rows if z['factor']=='Nasdaq volatility (VXN / VIX)'),{})
                reaction_score=0
                if 'Awaiting' not in semi.get('latest','') and 'previous close' not in semi.get('freshness','').lower():
                    sm=re.search(r'(?:basket vs QQQ|relative) ([+-]?[0-9.]+) pp',semi.get('latest',''))
                    if sm and abs(float(sm.group(1)))>=1.0: reaction_score+=2
                    elif sm and abs(float(sm.group(1)))>=0.5: reaction_score+=1
                if 'Awaiting' not in mega.get('latest','') and 'previous close' not in mega.get('freshness','').lower():
                    mm=re.search(r'(?:basket vs QQQ|relative) ([+-]?[0-9.]+) pp',mega.get('latest',''))
                    if mm and abs(float(mm.group(1)))>=1.0: reaction_score+=1
                if 'previous close' not in vol.get('freshness','').lower():
                    vm=[abs(float(v)) for v in re.findall(r'\\(([+-]?[0-9.]+)%\\)',vol.get('latest',''))]
                    if vm and max(vm)>=5: reaction_score+=1
                # Derive the earnings row's direction from current-session market reaction.
                # Semiconductor leadership carries the most weight; mega-cap leadership and volatility confirm.
                directional_score=0
                if 'Awaiting' not in semi.get('latest','') and 'previous close' not in semi.get('freshness','').lower():
                    sm=re.search(r'(?:basket vs QQQ|relative) ([+-]?[0-9.]+) pp',semi.get('latest',''))
                    if sm:
                        sv=float(sm.group(1)); directional_score += 2 if sv>=0.5 else (-2 if sv<=-0.5 else 0)
                if 'Awaiting' not in mega.get('latest','') and 'previous close' not in mega.get('freshness','').lower():
                    mm=re.search(r'(?:basket vs QQQ|relative) ([+-]?[0-9.]+) pp',mega.get('latest',''))
                    if mm:
                        mv=float(mm.group(1)); directional_score += 1 if mv>=0.5 else (-1 if mv<=-0.5 else 0)
                if 'previous close' not in vol.get('freshness','').lower():
                    vx=re.search(r'VXN [0-9.]+ \\(([+-]?[0-9.]+)%\\)',vol.get('latest',''))
                    if vx:
                        vv=float(vx.group(1)); directional_score += 1 if vv<=-3 else (-1 if vv>=3 else 0)
                if directional_score>=2:
                    r['signal']='positive'; r['direction']='Supportive setup'
                elif directional_score<=-2:
                    r['signal']='negative'; r['direction']='Risk-off setup'
                else:
                    r['signal']='mixed'; r['direction']='Event risk'

                # Promote one tier on strong corroborating reaction; promote to Very High on exceptional reaction.
                rank={'Low':0,'Medium':1,'High':2,'Very High':3}; names=['Low','Medium','High','Very High']
                if reaction_score>=3: imp='Very High'
                elif reaction_score>=2: imp=names[min(3,rank[imp]+1)]
                r['impactReason']=f"Calendar: {days:.1f} days to event; market-reaction score {reaction_score}/4; directional score {directional_score:+d}" if days is not None else f"Market-reaction score {reaction_score}/4; directional score {directional_score:+d}"
            elif n=='Fed expectations':
                # FOMC decisions deserve more urgency than minutes; minutes still ramp as the date approaches.
                decision=('decision' in txt.lower() or 'press conference' in txt.lower())
                if decision:
                    imp='Very High' if days is not None and days<=2 else ('High' if days is not None and days<=10 else ('Medium' if days is not None and days<=21 else 'Low'))
                else:
                    imp='High' if days is not None and days<=5 else ('Medium' if days is not None and days<=14 else 'Low')
            else:
                imp='Very High' if days is not None and days<=1 else ('High' if days is not None and days<=7 else ('Medium' if days is not None and days<=14 else 'Low'))
        elif r.get('signal') in ('positive','negative'):
            imp='Medium'
        else:
            imp='Low'
        r['currentImpact']=imp

    # Trend describes the current directional impulse where the factor itself contains
    # a measurable move. Comparing only signal buckets made nearly every row appear "Stable"
    # even when yields were falling, volatility rising, breadth broadening, etc.
    sig_score={'negative':-1,'mixed':0,'positive':1}
    dynamic_trend_factors={
        '10Y Treasury Yield','2Y Treasury yield','Semiconductor leadership','Market breadth','S&P 500 50D Breadth / Oversold',
        'Nasdaq volatility (VXN / VIX)','Mega-cap leadership','Credit conditions',
        'Oil (WTI / Brent)','Options positioning / sentiment','Earnings AVWAP leadership'
    }
    for r in rows:
        n=r['factor']
        impulse=r.get('changeSignal') if n in ('10Y Treasury Yield','2Y Treasury yield') else (r.get('signal') if n in dynamic_trend_factors else 'mixed')
        if impulse=='positive':
            r['trend']='Improving ↑'
        elif impulse=='negative':
            r['trend']='Deteriorating ↓'
        else:
            r['trend']='Stable →'

    # Keep slow/background model inputs in history and the Nasdaq Setup model, but do not
    # expose them as standalone dashboard rows/cards. Research-based inputs receive a
    # deliberately small model weight until their underlying data is automated.
    background_factors={'Earnings revisions','AI capex / monetization','Credit conditions'}
    research_background={'Earnings revisions','AI capex / monetization'}

    # Nasdaq Setup v2: continuous factor strength, acceleration, correlation buckets,
    # regime-sensitive weights, and confidence separated from directional score.
    impact_w={'Very High':4,'High':3,'Medium':2,'Low':1}
    def freshness_w(r):
        f=str(r.get('freshness','')).lower()
        if f.startswith('stale') or 'research snapshot' in f or 'official data lag' in f: return 0.35
        if 'previous close' in f: return 0.70
        if 'awaiting' in f or 'insufficient' in f: return 0.20
        return 1.0
    def clamp(x,lo=-1.0,hi=1.0): return max(lo,min(hi,x))
    def first_num(pattern,text):
        m=re.search(pattern,str(text),re.I)
        return float(m.group(1)) if m else None
    def continuous_factor(r):
        # Fallback preserves every factor; high-information live factors override the
        # old -1/0/+1 bucket with a continuous strength score.
        base=float(sig_score.get(r.get('signal','mixed'),0))
        n=r.get('factor',''); t=str(r.get('latest',''))
        if n in ('10Y Treasury Yield','2Y Treasury yield'):
            level=first_num(r'([0-9.]+)%',t); bp=first_num(r'\(([+-]?[0-9.]+) bp',t)
            # Level + daily velocity. 4.0% is neutral; +/-50 bp spans the level score.
            level_s=clamp((4.0-level)/0.50) if level is not None else 0
            velocity_s=clamp(-bp/10.0) if bp is not None else 0
            return clamp(0.60*level_s+0.40*velocity_s)
        if n=='Semiconductor leadership':
            rel=first_num(r'basket vs QQQ ([+-]?[0-9.]+) pp',t)
            smh=first_num(r'SMH vs QQQ ([+-]?[0-9.]+) pp',t)
            if rel is not None: return clamp(0.75*clamp(rel/1.5)+0.25*clamp((smh or 0)/1.5))
        if n=='Mega-cap leadership':
            rel=first_num(r'relative ([+-]?[0-9.]+) pp',t)
            if rel is not None: return clamp(rel/1.25)
        if n=='Market breadth':
            adv=first_num(r'advancing \(([0-9.]+)%\)',t)
            if adv is not None: return clamp((adv-50)/30.0)
        if n=='S&P 500 50D Breadth / Oversold':
            level=first_num(r'([0-9.]+)% above 50D',t); ch=first_num(r'([+-]?[0-9.]+) pp vs prior',t)
            if level is not None:
                level_s=clamp((level-50)/25.0); velocity_s=clamp((ch or 0)/5.0)
                return clamp(0.65*level_s+0.35*velocity_s)
        if n=='Nasdaq volatility (VXN / VIX)':
            vxn_level=first_num(r'VXN ([0-9.]+)',t); vix_level=first_num(r'VIX ([0-9.]+)',t)
            vx=first_num(r'VXN [0-9.]+ \(([+-]?[0-9.]+)%\)',t)
            vi=first_num(r'VIX [0-9.]+ \(([+-]?[0-9.]+)%\)',t)
            def regime(value,levels):
                if value is None: return 0.0
                a,b,c,d,e=levels
                if value<=a: return 1.0
                if value<=b: return 0.70
                if value<=c: return 0.20
                if value<=d: return -0.40
                if value<=e: return -0.70
                return -1.0
            if vxn_level is not None:
                return clamp(0.50*regime(vxn_level,(15,18,23,28,33))+
                             0.20*regime(vix_level,(12,15,20,25,30))+
                             0.20*clamp(-(vx or 0)/8.0)+
                             0.10*clamp(-(vi or 0)/8.0))
        if n=='Oil (WTI / Brent)':
            wm=first_num(r'WTI[^|]*\(([+-]?[0-9.]+)%\)',t); bm=first_num(r'Brent[^|]*\(([+-]?[0-9.]+)%\)',t)
            vals=[x for x in (wm,bm) if x is not None]
            if vals: return clamp(-sum(vals)/len(vals)/3.0)
        if n=='Options positioning / sentiment':
            eq=first_num(r'Equity P/C ([0-9.]+)',t); avg=first_num(r'5D avg ([0-9.]+)',t)
            if eq is not None:
                level_s=clamp((0.70-eq)/0.25); trend_s=clamp(((avg-eq) if avg is not None else 0)/0.15)
                return clamp(0.7*level_s+0.3*trend_s)
        if n=='Economic / inflation data':
            # Magnitude is release-specific; retain mapped direction but scale verified surprises
            # above neutral so a real release matters more than an awaiting row.
            return 0.75*base if r.get('surprise') is not None else 0.0
        return base

    bucket_of={
      '10Y Treasury Yield':'Rates / Macro','2Y Treasury yield':'Rates / Macro','Fed expectations':'Rates / Macro',
      'Economic / inflation data':'Rates / Macro','U.S. Dollar (DXY)':'Rates / Macro','Oil (WTI / Brent)':'Rates / Macro',
      'Semiconductor leadership':'Leadership','Mega-cap leadership':'Leadership','Earnings AVWAP leadership':'Leadership',
      'Market breadth':'Breadth','S&P 500 50D Breadth / Oversold':'Breadth',
      'Nasdaq volatility (VXN / VIX)':'Volatility / Positioning','Options positioning / sentiment':'Volatility / Positioning',
      'Credit conditions':'Volatility / Positioning','Technology earnings calendar':'Event Risk'
    }
    bucket_caps={'Rates / Macro':9.0,'Leadership':9.0,'Breadth':6.0,'Volatility / Positioning':7.0,'Event Risk':4.0,'Other':4.0}
    bucket_num={}; bucket_den={}; factor_model=[]
    available_weight=0.0; possible_weight=0.0
    # Regime sensitivity: amplify the relevant bucket when conditions make it unusually important.
    y10_now=num(q.get('US10Y',{}).get('last')) if isinstance(q.get('US10Y',{}),dict) else None
    vx_now=num(q.get('.VXN',{}).get('last')) if isinstance(q.get('.VXN',{}),dict) else None
    for r in rows:
        base_w=impact_w.get(r.get('currentImpact','Low'),1)
        fw=freshness_w(r); possible_weight+=base_w
        if r.get('factor') in research_background: fw=min(fw,0.35)
        w=base_w*fw
        bucket=bucket_of.get(r.get('factor'),'Other')
        regime=1.0
        if bucket=='Rates / Macro' and y10_now is not None and y10_now>=4.85: regime=1.25
        if bucket=='Volatility / Positioning' and vx_now is not None and vx_now>=22: regime=1.20
        if bucket=='Leadership' and r.get('currentImpact') in ('High','Very High'): regime=1.15
        w*=regime
        strength=continuous_factor(r)
        bucket_num[bucket]=bucket_num.get(bucket,0.0)+strength*w
        bucket_den[bucket]=bucket_den.get(bucket,0.0)+w
        available_weight+=base_w*fw
        factor_model.append({'factor':r.get('factor'),'bucket':bucket,'strength':round(strength,3),
                             'effectiveWeight':round(w,3),'freshnessWeight':round(fw,2),'regimeMultiplier':regime})
    numerator=0.0; denominator=0.0; bucket_model=[]
    for bucket,den in bucket_den.items():
        if den<=0: continue
        strength=bucket_num[bucket]/den
        contribution_w=min(den,bucket_caps.get(bucket,4.0))
        numerator+=strength*contribution_w; denominator+=contribution_w
        bucket_model.append({'bucket':bucket,'strength':round(strength,3),'weight':round(contribution_w,2),
                             'uncappedWeight':round(den,2),'cap':bucket_caps.get(bucket,4.0)})
    raw_setup_score=round(100*numerator/denominator) if denominator else 0
    score=raw_setup_score
    # Confidence measures coverage/freshness plus agreement among independent buckets.
    coverage=clamp(available_weight/possible_weight,0,1) if possible_weight else 0
    active=[x['strength'] for x in bucket_model if abs(x['strength'])>=0.05]
    agreement=abs(sum(active))/len(active) if active else 0.0
    confidence=round(100*(0.60*coverage+0.40*agreement))
    d['environmentConfidence']=confidence
    d['environmentCoverage']=round(100*coverage)
    d['setupModel']={'version':2,'factors':factor_model,'buckets':bucket_model,
                     'coveragePct':round(100*coverage),'agreementPct':round(100*agreement)}

    # Massive supplies historical context while CNBC remains the current/session feed.
    # Start with QQQ and the semiconductor ETF SOXX because both are available as U.S.
    # securities on the free stock-history endpoint and directly support Nasdaq Setup.
    massive_context={}
    for ticker in ('QQQ','SOXX'):
        ctx=historical_context(massive_daily_bars(ticker,180))
        if ctx: massive_context[ticker]=ctx
    d['historicalContext']=massive_context

    explain_current_rows(rows)

    # Factor-specific scorecards expose the underlying observation without inventing a score.
    # The value stays neutral in the UI; arrow/change inherit the factor's Nasdaq signal color.
    for r in rows:
        n=r['factor']; latest=str(r.get('latest','')); card=None
        if n in ('10Y Treasury Yield','2Y Treasury yield'):
            m=re.search(r'([0-9.]+)%.*?[(]([+-]?[0-9.]+) bp',latest)
            if m:
                ch=float(m.group(2)); card={'value':m.group(1)+'%','arrow':'↓' if ch<0 else ('↑' if ch>0 else '→'),'change':f'{ch:+.1f} bp'}
        elif n=='Nasdaq volatility (VXN / VIX)':
            vx=re.search(r'VXN ([0-9.]+) [(]([+-]?[0-9.]+)%[)]',latest)
            vi=re.search(r'VIX ([0-9.]+) [(]([+-]?[0-9.]+)%[)]',latest)
            if vx:
                ch=float(vx.group(2)); card={'value':'VXN '+vx.group(1),'arrow':'↓' if ch<0 else ('↑' if ch>0 else '→'),'change':f'{ch:+.2f}%'}
                if vi:
                    vch=float(vi.group(2)); card['secondaryValue']='VIX '+vi.group(1); card['secondaryArrow']='↓' if vch<0 else ('↑' if vch>0 else '→'); card['secondaryChange']=f'{vch:+.2f}%'
        elif n=='S&P 500 50D Breadth / Oversold':
            m=re.search(r'([0-9.]+)% above 50D MA(?: · ([+-]?[0-9.]+) pp)?',latest)
            if m:
                ch=float(m.group(2)) if m.group(2) else None
                card={'value':m.group(1)+'%','arrow':'↓' if ch is not None and ch<0 else ('↑' if ch is not None and ch>0 else '→'),'change':f'{ch:+.1f} pp' if ch is not None else ''}
        elif n=='Earnings AVWAP leadership':
            cov=int(r.get('coveredCount',0)); above=int(r.get('aboveCount',0)); md=r.get('medianDistancePct')
            if cov and md is not None:
                card={'value':f'{above}/{cov} above','arrow':'↑' if r.get('signal')=='positive' else ('↓' if r.get('signal')=='negative' else '→'),'change':f'median {md:+.1f}%'}
        elif n=='Oil (WTI / Brent)':
            m=re.search(r'WTI[^0-9]*([0-9.]+).*?[(]([+-]?[0-9.]+)%[)]',latest,re.I)
            if m:
                ch=float(m.group(2)); card={'value':'WTI '+m.group(1),'arrow':'↓' if ch<0 else ('↑' if ch>0 else '→'),'change':f'{ch:+.2f}%'}
        elif n=='Market breadth':
            m=re.search(r'([0-9]+)/([0-9]+) advancing [(]([0-9]+)%[)]',latest)
            if m: card={'value':m.group(3)+'% advancing','arrow':'↑' if r.get('signal')=='positive' else ('↓' if r.get('signal')=='negative' else '→'),'change':''}
        r['scorecard']=card

    # Recompute summary cards from the refreshed rows instead of leaving stale labels in dashboard.json.
    group_members={
        'Rates / Macro':['Fed expectations','10Y Treasury Yield','Economic / inflation data','2Y Treasury yield','Oil (WTI / Brent)'],
        'Semiconductors':['Semiconductor leadership'],
        'Breadth':['Market breadth','Mega-cap leadership'],
        'Risk / Credit':['Nasdaq volatility (VXN / VIX)','Credit conditions','Options positioning / sentiment'],
        'AI / Fundamentals':['Earnings revisions','AI capex / monetization','Technology earnings calendar']
    }
    impact_w={'Very High':4,'High':3,'Medium':2,'Low':1}
    sig_v={'positive':1,'negative':-1,'mixed':0}
    byname={r['factor']:r for r in rows}
    def group_signal(names):
        items=[byname[x] for x in names if x in byname]
        denom=sum(impact_w.get(x.get('currentImpact','Low'),1) for x in items)
        score=sum(sig_v.get(x.get('signal','mixed'),0)*impact_w.get(x.get('currentImpact','Low'),1) for x in items)
        norm=score/denom if denom else 0
        return 'positive' if norm>=0.20 else ('negative' if norm<=-0.20 else 'mixed')
    all_signal=group_signal([r['factor'] for r in rows])
    labels={'positive':'🟢 Positive','negative':'🔴 Negative','mixed':'🟡 Mixed'}
    for g in d.get('groups',[]):
        sig=all_signal if g.get('name') in ('NASDAQ ENVIRONMENT','NASDAQ SETUP') else group_signal(group_members.get(g.get('name'),[]))
        g['signal']=sig; g['label']=labels[sig]

    # Public presentation metadata is generated here so the browser remains a dumb renderer.
    group_explanations={
        'NASDAQ SETUP':'Dynamic synthesis of the factors currently driving Nasdaq. It highlights the strongest supportive forces, the main headwinds, and the market conditions that would materially strengthen or weaken the setup.',
        'Rates / Macro':'Combines Fed policy, Treasury yields and economic/inflation data. Falling yields or easier policy expectations are generally more supportive for growth stocks.',
        'Semiconductors':'Tracks semiconductor leadership relative to QQQ. Strong chip participation often confirms Nasdaq technology momentum.',
        'Breadth':'Measures how broadly Nasdaq-100 constituents participate. Broad participation generally makes index moves more robust.',
        'Risk / Credit':'Combines volatility and credit conditions. Rising VXN/VIX or weaker high-yield credit can indicate increasing market stress.',
        'AI / Fundamentals':'Summarizes earnings revisions, AI capex/monetization and technology earnings-event risk.'
    }
    for g in d.get('groups',[]):
        if g.get('name')=='NASDAQ ENVIRONMENT': g['name']='NASDAQ SETUP'
        g['explanation']=group_explanations.get(g.get('name'),'Summary of the latest signals in this category.')
    # Build the Nasdaq Setup narrative from the same factor state used by the score.
    # This is deliberately deterministic: it explains current evidence and conditional
    # triggers without inventing historical claims that are not yet backed by stored data.
    def build_setup_explanation(rows, score, trend):
        """Turn model state into a concise market interpretation instead of a data dump.

        The narrative uses only observations already verified by NasBoard. It prioritizes
        rates, semiconductor confirmation, historical momentum, and actionable triggers;
        unavailable/stale factors are omitted rather than rendered as awkward prose.
        """
        by={r['factor']:r for r in rows}
        def row(name): return by.get(name,{})
        def latest(name): return str(row(name).get('latest',''))
        def signal(name): return row(name).get('signal','mixed')
        def yield_value(name):
            # Treasury rows can contain malformed display text if an upstream quote is
            # unexpectedly scaled. Prefer the validated CNBC quote object for analysis.
            sym='US10Y' if name=='10Y Treasury Yield' else 'US2Y'
            x=q.get(sym,{}) if isinstance(q,dict) else {}
            v=num(x.get('last')) if isinstance(x,dict) else None
            return v if v is not None and 0 < v < 20 else None
        y2=yield_value('2Y Treasury yield'); y10=yield_value('10Y Treasury Yield')
        soxx=d.get('historicalContext',{}).get('SOXX',{})
        qctx=d.get('historicalContext',{}).get('QQQ',{})
        label='strong positive' if score>=45 else ('cautiously positive' if score>=15 else ('mixed/neutral' if score>-15 else ('cautiously negative' if score>-45 else 'strong negative')))

        # Paragraph 1: explain the dominant cross-market evidence in natural language.
        evidence=[]
        if y2 is not None and y10 is not None:
            evidence.append(f"Treasury yields remain the main pressure point, with the 2Y at {y2:.3f}% and the 10Y at {y10:.3f}%.")
        st=soxx.get('streak')
        if st:
            direction='risen' if st>0 else 'fallen'
            evidence.append(f"Semiconductor momentum remains an important equity confirmation: SOXX has {direction} for {abs(st)} consecutive session{'s' if abs(st)!=1 else ''}.")
        if qctx.get('return5d') is not None and qctx.get('ma20Distance') is not None:
            evidence.append(f"QQQ is {qctx['return5d']:+.2f}% over five sessions and {qctx['ma20Distance']:+.2f}% versus its 20-day average.")
        oil=latest('Oil (WTI / Brent)')
        om=re.search(r'Brent \$([0-9.]+) \(([+-]?[0-9.]+)%\)',oil)
        if om:
            move=float(om.group(2))
            evidence.append(f"Brent is {move:+.2f}% at about ${float(om.group(1)):.2f}, {'providing some inflation relief' if move<0 else 'adding some inflation pressure'}.")

        # Paragraph 2: synthesize the tension rather than listing internal factor names.
        positives=[]
        negatives=[]
        if st and st>0: positives.append('persistent semiconductor momentum')
        if signal('Market breadth')=='positive': positives.append('healthy market breadth')
        if signal('Options positioning / sentiment')=='positive': positives.append('supportive options positioning')
        if om and float(om.group(2))<0: positives.append('falling oil')
        if signal('2Y Treasury yield')=='negative' or signal('10Y Treasury Yield')=='negative': negatives.append('elevated/rising Treasury yields')
        if signal('Semiconductor leadership')=='negative': negatives.append('weaker intraday semiconductor leadership')
        if signal('Earnings AVWAP leadership')=='positive': positives.append('semiconductor/AI leaders holding above their earnings AVWAPs')
        elif signal('Earnings AVWAP leadership')=='negative': negatives.append('semiconductor/AI leaders trading below their earnings AVWAPs')
        if signal('Nasdaq volatility (VXN / VIX)')=='negative': negatives.append('rising volatility')
        pos=', '.join(positives[:3]) or 'limited positive confirmation'
        neg=', '.join(negatives[:3]) or 'no major high-impact bearish confirmation'
        confidence=d.get('environmentConfidence')
        conf=f", {confidence}% confidence" if confidence is not None else ""
        assessment=f"The Nasdaq Setup is {label} ({score:+d}/100{conf}, {trend.lower()}). The current balance is {pos} on the supportive side versus {neg} as the main headwind."

        # Paragraph 3: integrate active 3-Day Watch conditions into prose instead of
        # dumping raw trigger rows in the UI.
        active=[]
        if y10 is not None and y10>5.05: active.append(f"the 10Y yield is above the 5.05% headwind threshold at {y10:.3f}%")
        if signal('Semiconductor leadership')=='negative': active.append("semiconductor leadership is lagging QQQ")
        if signal('Market breadth')=='negative': active.append("Nasdaq breadth is weak")
        if signal('Nasdaq volatility (VXN / VIX)')=='negative': active.append("volatility is rising")
        if active:
            trigger="Near-term risk is concentrated in "+", ".join(active[:3])+". Improvement in these conditions would strengthen the setup; further deterioration would reduce conviction."
        elif y10 is not None and 4.85 <= y10 <= 5.15:
            trigger="The key confirmation remains the interaction between Treasury yields and semiconductor leadership. A sustained 10Y break above roughly 5.00–5.05% alongside weakening chips would materially weaken the setup; easing yields with stronger semiconductor participation would improve it."
        else:
            trigger="The key confirmation remains the interaction between yields, semiconductor leadership and breadth. Agreement across those areas would strengthen conviction; divergence would keep the setup less reliable."
        return '\n\n'.join([x for x in [' '.join(evidence),assessment,trigger] if x])

    impact_order={'Very High':0,'High':1,'Medium':2,'Low':3}
    visible_rows=[r for r in rows if r.get('factor') not in background_factors]
    visible_rows.sort(key=lambda r:impact_order.get(r.get('currentImpact','Low'),3))
    for i,r in enumerate(visible_rows,1):
        r['displayRank']=i
        r['signalLabel']={'positive':'🟢 Positive','negative':'🔴 Negative','mixed':'🟡 Mixed'}.get(r.get('signal'),'🟡 Mixed')

    # Consolidation / Extension Risk v2. This is separate from Nasdaq direction.
    # Massive history supplies QQQ/SOXX momentum and trend extension immediately; session
    # breadth, S5FI, VXN and Earnings AVWAP add participation/crowding confirmation.
    def risk_band(v):
        return 'Very High' if v>=75 else ('High' if v>=55 else ('Medium' if v>=30 else 'Low'))
    components=[]; weighted=0.0; total_w=0.0
    MODEL_WEIGHT=100.0
    def add_component(name,score,weight,detail):
        components.append({'name':name,'score':round(score,1),'weight':weight,'detail':detail})
        return score*weight,weight
    def add_metric(name,value,weight,threshold,scale,detail):
        nonlocal_dummy=None
        if value is None: return
        score=min(100,max(0,(value-threshold)*scale))
        a,b=add_component(name,score,weight,detail); return a,b

    qctx=massive_context.get('QQQ',{}); sctx=massive_context.get('SOXX',{})
    metric_specs=[
        ('QQQ 1D return',qctx.get('return1d'),4,0.5,28),
        ('QQQ 3D return',qctx.get('return3d'),6,1.5,18),
        ('QQQ 5D return',qctx.get('return5d'),7,2.5,14),
        ('QQQ vs 20DMA',qctx.get('ma20Distance'),9,1.0,18),
        ('QQQ vs 50DMA',qctx.get('ma50Distance'),7,2.0,10),
        ('QQQ RSI14',qctx.get('rsi14'),7,55.0,3.0),
        ('SOXX 1D return',sctx.get('return1d'),4,0.75,22),
        ('SOXX 3D return',sctx.get('return3d'),6,2.0,15),
        ('SOXX 5D return',sctx.get('return5d'),7,3.0,12),
        ('SOXX vs 20DMA',sctx.get('ma20Distance'),9,1.5,15),
        ('SOXX vs 50DMA',sctx.get('ma50Distance'),7,3.0,8)
    ]
    for name,value,weight,threshold,scale in metric_specs:
        if value is None: continue
        score=min(100,max(0,(value-threshold)*scale))
        suffix='' if 'RSI' in name else '%'
        a,b=add_component(name,score,weight,f'{value:+.2f}{suffix}'); weighted+=a; total_w+=b

    br=next((r for r in rows if r['factor']=='Market breadth'),{})
    bpct=None
    try: bpct=float(br.get('latest','').rsplit('(',1)[1].split('%',1)[0])
    except (IndexError,ValueError): pass
    if bpct is not None:
        bs=min(100,max(0,(bpct-55)*2.5))
        a,b=add_component('Nasdaq daily breadth',bs,5,f'{bpct:.0f}% advancing'); weighted+=a; total_w+=b

    s5=next((r for r in rows if r['factor']=='S&P 500 50D Breadth / Oversold'),{})
    # Prefer the direct row when CNBC supplies S5FI. Otherwise probe Massive's index
    # namespace. Massive index symbols use the I: prefix; fail closed if S5FI is not
    # included in the account's supported index universe.
    if 'Awaiting S5FI' in str(s5.get('latest','')) or str(s5.get('freshness','')).startswith('STALE'):
        ms5=massive_index_latest(['I:S5FI','S5FI'])
        if ms5 and 0 <= ms5['value'] <= 100:
            s5['latest']=f"{ms5['value']:.1f}% above 50D MA"
            s5['direction']='Massive breadth reading'
            s5['signal']='positive' if ms5['value']>=60 else ('negative' if ms5['value']<40 else 'mixed')
            s5['freshness']=f"Massive index · {ms5['date']}"
            s5['source']=f"Massive Indices API · {ms5['ticker']}"
    s5m=re.search(r'([0-9.]+)% above 50D MA(?: · ([+-]?[0-9.]+) pp)?',str(s5.get('latest','')))
    if s5m:
        level=float(s5m.group(1)); change=float(s5m.group(2)) if s5m.group(2) else 0.0
        s5score=min(100,max(0,(level-55)*3 + max(change,0)*4))
        a,b=add_component('S5FI level + trend',s5score,7,f'{level:.1f}% · {change:+.1f} pp'); weighted+=a; total_w+=b

    vxmove=num(q.get('.VXN',{}).get('change_pct')) if '.VXN' in q else None
    if vxmove is not None:
        vs=min(100,max(0,-vxmove*10)) if vxmove<0 else max(0,25-vxmove*5)
        a,b=add_component('VXN behavior',vs,5,f'VXN {vxmove:+.2f}%'); weighted+=a; total_w+=b

    avvals=list(avwap_details.values())
    if avvals:
        avdist=statistics.median(x['distancePct'] for x in avvals)
        avscore=min(100,max(0,(avdist-2)*8))
        a,b=add_component('Earnings AVWAP extension',avscore,10,f'median {avdist:+.2f}% · {sum(x["above"] for x in avvals)}/{len(avvals)} above'); weighted+=a; total_w+=b

    risk_score=round(weighted/total_w) if total_w else None
    d['consolidationRisk']={'score':risk_score,'level':risk_band(risk_score) if risk_score is not None else 'Unavailable',
        'explanation':'Estimates near-term consolidation risk from a proprietary blend of market conditions.',
        'coverageWeight':round(100*total_w/MODEL_WEIGHT),'components':components,
        'historyDays':qctx.get('bars',0),'unlocked':[x['name'] for x in components],
        'note':'Higher means more extended/crowded. Missing inputs reduce model coverage rather than being guessed.'}

    # Consolidation Risk is a conviction modifier, not directional evidence.
    # High extension/crowding pulls the directional score toward zero regardless of sign,
    # rather than mechanically making an already-bearish setup even more bearish.
    conviction_reduction=0
    if risk_score is not None:
        if risk_score>=85: conviction_reduction=25
        elif risk_score>=70: conviction_reduction=15
        elif risk_score>=50: conviction_reduction=8
        elif risk_score>=30: conviction_reduction=3
    if raw_setup_score>0:
        score=max(0,raw_setup_score-conviction_reduction)
    elif raw_setup_score<0:
        score=min(0,raw_setup_score+conviction_reduction)
    else:
        score=0
    score=max(-100,min(100,score))
    d['environmentScoreRaw']=raw_setup_score
    d['consolidationPenalty']=conviction_reduction
    d['environmentScore']=score
    # The published Setup label/color is derived from the final v2 numerical score so
    # the card can never disagree with the score after consolidation-risk adjustment.
    if score>=45: setup_signal='positive'; setup_label='Strong Positive'
    elif score>=15: setup_signal='positive'; setup_label='Cautiously Positive'
    elif score>-15: setup_signal='mixed'; setup_label='Mixed / Neutral'
    elif score>-45: setup_signal='negative'; setup_label='Cautiously Negative'
    else: setup_signal='negative'; setup_label='Strong Negative'
    d['environmentSignal']=setup_signal
    d['environmentLabel']=setup_label
    for g in d.get('groups',[]):
        if g.get('name')=='NASDAQ SETUP':
            g['signal']=setup_signal
            g['label']=setup_label
    previous_score=d.get('environmentScorePrevious',score)
    d['environmentTrend']='Improving ↑' if score>previous_score else ('Deteriorating ↓' if score<previous_score else 'Stable →')
    d['environmentScorePrevious']=score

    # Opportunity Score: is a dislocation becoming investable as market internals recover?
    # This is deliberately separate from Nasdaq Setup (current environment) and
    # Consolidation Risk (vulnerability). High volatility only helps when recovery confirms.
    try:
        with open(DAILY_PATH,encoding='utf-8') as hf:
            _opp_daily=json.load(hf).get('records',{})
    except (FileNotFoundError,json.JSONDecodeError):
        _opp_daily={}
    _opp_dates=sorted(_opp_daily.keys())[-5:]
    _opp_hist=[_opp_daily[x] for x in _opp_dates]

    def _clamp100(x): return max(0.0,min(100.0,float(x)))
    def _row_latest(name):
        return str(next((r for r in rows if r.get('factor')==name),{}).get('latest',''))
    def _pct_in(text,pattern):
        m=re.search(pattern,str(text),re.I)
        return float(m.group(1)) if m else None
    def _hist_factor_latest(rec,name):
        return str(rec.get('factors',{}).get(name,{}).get('latest',''))

    # S — current Nasdaq Setup mapped from -100..+100 to 0..100.
    setup_readiness=_clamp100((score+100)/2)

    # R1 — VXN reversal from the highest observation in the prior five stored sessions.
    opp_vxn=num(q.get('.VXN',{}).get('last'))
    hist_vxn=[num(x.get('market',{}).get('.VXN',{}).get('last')) for x in _opp_hist]
    hist_vxn=[x for x in hist_vxn if x is not None]
    vxn_reversal=None
    if opp_vxn is not None and hist_vxn:
        peak=max(hist_vxn+[opp_vxn])
        vxn_reversal=_clamp100(((peak-opp_vxn)/peak)*500) if peak>0 else 0

    # R2 — breadth recovery: +12.5 percentage points over the lookback reaches 100.
    cur_breadth=_pct_in(_row_latest('Market breadth'),r'advancing\s*\(([0-9.]+)%\)')
    old_breadth=None
    for rec in _opp_hist:
        x=_pct_in(_hist_factor_latest(rec,'Market breadth'),r'advancing\s*\(([0-9.]+)%\)')
        if x is not None: old_breadth=x; break
    breadth_recovery=_clamp100(50+4*(cur_breadth-old_breadth)) if cur_breadth is not None and old_breadth is not None else None

    # R3 — semiconductor relative-leadership recovery versus QQQ.
    cur_semi=_pct_in(_row_latest('Semiconductor leadership'),r'basket vs QQQ\s*([+-]?[0-9.]+)\s*pp')
    old_semi=None
    for rec in _opp_hist:
        x=_pct_in(_hist_factor_latest(rec,'Semiconductor leadership'),r'basket vs QQQ\s*([+-]?[0-9.]+)\s*pp')
        if x is not None: old_semi=x; break
    semi_recovery=_clamp100(50+20*(cur_semi-old_semi)) if cur_semi is not None and old_semi is not None else None

    # R4 — 10Y stabilization: a 10 bp fall over the lookback scores 100; +10 bp scores 0.
    cur_y10=num(q.get('US10Y',{}).get('last'))
    old_y10=None
    for rec in _opp_hist:
        x=num(rec.get('market',{}).get('US10Y',{}).get('last'))
        if x is not None: old_y10=x; break
    yield_stabilization=_clamp100(50-500*(cur_y10-old_y10)) if cur_y10 is not None and old_y10 is not None else None

    # R5 — Setup improvement: +25 score points over the lookback reaches 100.
    old_setup=None
    for rec in _opp_hist:
        x=num(rec.get('environmentScore'))
        if x is not None: old_setup=x; break
    setup_improvement=_clamp100(50+2*(score-old_setup)) if old_setup is not None else None

    recovery_parts=[
        ('vxnReversal',vxn_reversal,0.30),('breadthRecovery',breadth_recovery,0.25),
        ('semiconductorRecovery',semi_recovery,0.20),('yieldStabilization',yield_stabilization,0.15),
        ('setupImprovement',setup_improvement,0.10)
    ]
    available=[x for x in recovery_parts if x[1] is not None]
    recovery=round(sum(v*w for _,v,w in available)/sum(w for _,v,w in available)) if available else 0

    # C — high Consolidation Risk is explicitly bad for opportunity.
    consolidation_readiness=_clamp100(100-float(d.get('consolidationRisk',{}).get('score',50)))

    # V — VXN dislocation. High fear creates capacity for opportunity; R unlocks it.
    if opp_vxn is None: volatility_dislocation=0
    elif opp_vxn<20: volatility_dislocation=0
    elif opp_vxn<23: volatility_dislocation=25
    elif opp_vxn<28: volatility_dislocation=50
    elif opp_vxn<33: volatility_dislocation=75
    else: volatility_dislocation=100
    unlocked_volatility=volatility_dislocation*(recovery/100)

    opportunity_score=round(0.40*setup_readiness+0.25*recovery+0.20*consolidation_readiness+0.15*unlocked_volatility)
    if opportunity_score>=75: opp_label='Strong Opportunity'; opp_signal='positive'
    elif opportunity_score>=60: opp_label='Attractive'; opp_signal='positive'
    elif opportunity_score>=45: opp_label='Selective'; opp_signal='mixed'
    elif opportunity_score>=25: opp_label='Limited'; opp_signal='mixed'
    else: opp_label='Poor Opportunity'; opp_signal='negative'
    d.pop('deploymentEnvironment',None)
    d['opportunityScore']={
        'score':opportunity_score,'label':opp_label,'signal':opp_signal,
        'setupReadiness':round(setup_readiness),'recoveryConfirmation':recovery,
        'consolidationReadiness':round(consolidation_readiness),
        'volatilityDislocation':round(volatility_dislocation),
        'unlockedVolatilityOpportunity':round(unlocked_volatility),
        'recoveryComponents':{name:(round(v) if v is not None else None) for name,v,_ in recovery_parts},
        'lookbackSessions':len(_opp_hist),
        'explanation':f'Opportunity Score = 40% Setup readiness + 25% Recovery Confirmation + 20% inverse Consolidation Risk + 15% volatility opportunity unlocked by recovery. Recovery is built from VXN reversal (30%), breadth recovery (25%), semiconductor recovery (20%), 10Y yield stabilization (15%) and Setup improvement (10%). Current recovery confirmation is {recovery}%.'
    }

    setup_explanation=build_setup_explanation(rows,score,d['environmentTrend'])
    if conviction_reduction:
        setup_explanation += " Elevated consolidation risk is reducing conviction in the directional setup."

    # 3-Day Watch: material-change detector for the post-open Market Analysis.
    # It mirrors the cross-market watch used for short-horizon Nasdaq monitoring:
    # rates first, then Fed repricing, semiconductor confirmation, QQQ momentum,
    # oil/inflation pressure, breadth and volatility. It only flags meaningful changes.
    watch=[]
    def watch_add(severity,title,detail):
        watch.append({'severity':severity,'title':title,'detail':detail})
    watch_by={r.get('factor'):r for r in rows}
    def watch_signal(name): return watch_by.get(name,{}).get('signal','mixed')
    def watch_latest(name): return str(watch_by.get(name,{}).get('latest',''))
    semi_sig=watch_signal('Semiconductor leadership')
    fed_sig=watch_signal('Fed expectations')
    breadth_sig=watch_signal('Market breadth')
    vol_sig=watch_signal('Nasdaq volatility (VXN / VIX)')
    oil_sig=watch_signal('Oil (WTI / Brent)')
    # Use numeric yield values from the factor rows here. Variables named y10/y2
    # elsewhere in main() may hold raw quote dictionaries and must not leak into
    # the 3-Day Watch comparisons.
    def watch_pct(name):
        m=re.search(r'([0-9]+(?:\\.[0-9]+)?)%',watch_latest(name))
        return float(m.group(1)) if m else None
    watch_y10=watch_pct('10Y Treasury Yield')
    watch_y2=watch_pct('2Y Treasury yield')
    if watch_y10 is not None:
        if watch_y10>5.05:
            watch_add('bearish','10Y above 5.05%',f'US10Y is {watch_y10:.3f}%, above the 3-Day Watch significant-headwind threshold.'+(f' US2Y is {watch_y2:.3f}%.' if watch_y2 is not None else ''))
        elif watch_y10>5.00:
            watch_add('bearish','10Y above 5.00%',f'US10Y is {watch_y10:.3f}%, in the restrictive 5.00–5.05% zone.')
        elif watch_y10<4.95:
            watch_add('bullish','10Y below 4.95%',f'US10Y is {watch_y10:.3f}%, inside the supportive 3-Day Watch zone.')
    if fed_sig=='negative':
        watch_add('bearish','Fed expectations repriced hawkishly',watch_latest('Fed expectations'))
    elif fed_sig=='positive':
        watch_add('bullish','Fed expectations eased',watch_latest('Fed expectations'))
    if semi_sig=='negative':
        watch_add('bearish','Semiconductor leadership weakened',watch_latest('Semiconductor leadership'))
    elif semi_sig=='positive':
        watch_add('bullish','Semiconductors confirm Nasdaq leadership',watch_latest('Semiconductor leadership'))
    if breadth_sig=='negative':
        watch_add('bearish','Market breadth deteriorated',watch_latest('Market breadth'))
    elif breadth_sig=='positive':
        watch_add('bullish','Market breadth broadened',watch_latest('Market breadth'))
    if vol_sig=='negative':
        watch_add('bearish','Nasdaq volatility is rising',watch_latest('Nasdaq volatility (VXN / VIX)'))
    if oil_sig=='negative':
        watch_add('bearish','Oil is adding inflation pressure',watch_latest('Oil (WTI / Brent)'))
    elif oil_sig=='positive':
        watch_add('bullish','Oil is easing inflation pressure',watch_latest('Oil (WTI / Brent)'))
    if qctx.get('return3d') is not None:
        r3=qctx['return3d']
        if r3<=-1.5: watch_add('bearish','QQQ 3-day momentum weakened',f'QQQ 3-day return is {r3:+.2f}%.')
        elif r3>=1.5: watch_add('bullish','QQQ 3-day momentum strengthened',f'QQQ 3-day return is {r3:+.2f}%.')
    bearish=sum(x['severity']=='bearish' for x in watch); bullish=sum(x['severity']=='bullish' for x in watch)
    material='bearish' if bearish>=2 and bearish>bullish else ('bullish' if bullish>=2 and bullish>bearish else 'mixed')
    d['threeDayWatch']={'status':material,'bearishTriggers':bearish,'bullishTriggers':bullish,'triggers':watch,
        'monitors':['QQQ 3-day momentum','US10Y','US2Y','Fed expectations','Semiconductor leadership vs QQQ','Market breadth','VXN/VIX','WTI/Brent'],
        'thresholds':{'US10YSupportive':'<4.95%','US10YManageable':'4.95–5.00%','US10YRestrictive':'5.00–5.05%','US10YSignificantHeadwind':'>5.05%','QQQ3dMaterialMove':'±1.5%'}}
    if material=='bearish':
        setup_explanation="⚠️ Material bearish change. "+setup_explanation
    elif material=='bullish':
        setup_explanation="Material bullish improvement. "+setup_explanation
    for g in d.get('groups',[]):
        if g.get('name')=='NASDAQ SETUP': g['explanation']=setup_explanation

    # Persist raw market observations so NasBoard builds its own historical dataset.
    # Daily records are upserted; intraday snapshots are append-only per monthly file.
    def quote_obs(sym):
        x=q.get(sym,{})
        stamp=x.get('last_timedate') or x.get('last_time')
        # Parse CNBC dates without regex backslash ambiguity. Examples:
        # "09/21/26 EDT" -> 2026-09-21; "2026-09-22 ..." -> 2026-09-22.
        obs_date=None
        for raw in (x.get('last_timedate'),x.get('last_time')):
            if not raw: continue
            txt=str(raw).strip()
            token=txt.split()[0]
            try:
                if len(token)>=8 and token.count('/')==2:
                    obs_date=datetime.datetime.strptime(token,'%m/%d/%y').date().isoformat(); break
                if len(token)>=10 and token[4]=='-' and token[7]=='-':
                    obs_date=datetime.date.fromisoformat(token[:10]).isoformat(); break
            except ValueError:
                pass
        today=now.strftime('%Y-%m-%d')
        # Time-only stamps from continuously trading instruments are current-day observations.
        if obs_date is None and stamp:
            token=str(stamp).strip().split()[0]
            try:
                datetime.datetime.strptime(token,'%H:%M')
                obs_date=today
            except ValueError:
                try:
                    datetime.datetime.strptime(token,'%I:%M')
                    obs_date=today
                except ValueError:
                    pass
        # CNBC exposes both timestamps and an explicit realTime flag. A same-day
        # timestamp alone is not proof of real-time service, so retain both dimensions.
        rt=str(x.get('realTime','')).strip().lower()
        real_time=True if rt=='true' else (False if rt=='false' else None)
        market_status=x.get('curmktstatus')
        source=x.get('source')
        provider=x.get('provider')
        if obs_date==today:
            state='live' if real_time is True else ('delayed_or_unspecified' if real_time is False else 'current_unknown_latency')
        elif obs_date:
            age=(datetime.date.fromisoformat(today)-datetime.date.fromisoformat(obs_date)).days
            state='previous_close' if 0 < age <= 3 else ('live' if age==0 else 'stale')
        else:
            state='unknown'
        return {'last':num(x.get('last')),'previousClose':num(x.get('previous_day_closing')),
                'changePct':num(x.get('change_pct')) if x.get('change_pct') not in (None,'') else pct(x),
                'timestamp':stamp,'observationDate':obs_date,'dataState':state,
                'realTime':real_time,'marketStatus':market_status,'quoteSource':source,'provider':provider}
    os.makedirs(HISTORY_DIR,exist_ok=True)
    market_symbols=['.IXIC','QQQ','.SOX','NVDA','AMD','AVGO','TSM','MU','AAPL','MSFT','AMZN','GOOGL','META','TSLA',
                    '.VXN','.VIX','US10Y','US2Y','@CL.1','@LCO.1','HYG','LQD']
    market={sym:quote_obs(sym) for sym in market_symbols if sym in q}
    # Persist a compact source/freshness audit so we can verify CNBC instrument-by-instrument
    # instead of treating every CNBC response as equally live.
    d.setdefault('diagnostics',{})['cnbcFreshness']={
        sym:{k:v for k,v in obs.items() if k in ('timestamp','observationDate','dataState','realTime','marketStatus','quoteSource','provider')}
        for sym,obs in market.items()
    }
    current_session=[sym for sym in BREADTH if sym in q and is_intraday(q[sym],now)]
    pos=sum(1 for sym in current_session if (pct(q[sym]) or 0)>0)
    breadth_obs={'valid':len(current_session),'advancers':pos,'decliners':len(current_session)-pos,
                 'positivePct':round(100*pos/len(current_session),2) if current_session else None}
    factor_state={r['factor']:{'signal':r.get('signal'),'currentImpact':r.get('currentImpact'),
                              'trend':r.get('trend'),'latest':r.get('latest')} for r in rows}
    curve_obs={'spreadBp':round(curve_2s10s,1) if curve_2s10s is not None else None,
               'changeBp':round(curve_change,1) if curve_change is not None else None,
               'shape':curve_regime} if curve_2s10s is not None else None
    # Daily model-vs-market observation for later validation. Nasdaq Composite (.IXIC)
    # is stored alongside the Environment Score so we can test same-day and, more
    # importantly, forward 1D/3D/5D/10D relationships without look-ahead bias.
    ixic=market.get('.IXIC',{})
    model_perf={'nasdaqCompositeClose':ixic.get('last'),
                'nasdaqCompositeObservationDate':ixic.get('observationDate'),
                'environmentScore':d.get('environmentScore')}
    # Store each ticker's raw earnings-AVWAP observation in history. The price is the
    # same current/session-aware CNBC quote used by the AVWAP factor at refresh time.
    # Keeping AVWAP, price and distance together makes historical reconstruction/test use simple.
    avwap_history={ticker:{
        'earningsDate':x.get('earningsDate'),'anchorDate':x.get('anchorDate'),
        'throughDate':x.get('throughDate'),'avwap':x.get('avwap'),
        'price':x.get('price'),'distancePct':x.get('distancePct'),
        'above':x.get('above'),'slope5dPct':x.get('slope5dPct'),
        'sessions':x.get('sessions')
    } for ticker,x in avwap_details.items()}
    snapshot={'schemaVersion':1,'timestampET':now.isoformat(),'market':market,'breadth':breadth_obs,
              'yieldCurve2s10s':curve_obs,'modelPerformance':model_perf,
              'environmentScore':d.get('environmentScore'),'environmentTrend':d.get('environmentTrend'),
              'earningsAvwap':avwap_history,'factors':factor_state}
    try:
        with open(DAILY_PATH,encoding='utf-8') as hf: daily=json.load(hf)
    except (FileNotFoundError,json.JSONDecodeError):
        daily={'schemaVersion':1,'records':{}}
    daily['schemaVersion']=1
    daily.setdefault('records',{})[now.strftime('%Y-%m-%d')]=snapshot
    with open(DAILY_PATH,'w',encoding='utf-8') as hf: json.dump(daily,hf,ensure_ascii=False,indent=2)
    month_path=os.path.join(HISTORY_DIR,'intraday',now.strftime('%Y-%m')+'.json')
    os.makedirs(os.path.dirname(month_path),exist_ok=True)
    try:
        with open(month_path,encoding='utf-8') as hf: intraday=json.load(hf)
    except (FileNotFoundError,json.JSONDecodeError):
        intraday={'schemaVersion':1,'snapshots':[]}
    intraday['schemaVersion']=1
    intraday.setdefault('snapshots',[]).append(snapshot)
    with open(month_path,'w',encoding='utf-8') as hf: json.dump(intraday,hf,ensure_ascii=False,indent=2)

    # Only tactical/actionable factors are published to the dashboard. Background factors
    # remain in factor_state/history above and continue contributing to Environment Score.
    d['rows']=visible_rows
    d['updatedET']=now.strftime('%b %d, %Y · %H:%M ET'); d['nextUpdateET']='09:30 / 10:30 ET on trading weekdays'
    with open(PATH,'w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)

if __name__=='__main__':main()
