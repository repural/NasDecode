import json, urllib.request, urllib.parse, datetime, os, re, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT=os.path.dirname(os.path.dirname(__file__))
PATH=os.path.join(ROOT,'data','dashboard.json')
HISTORY_DIR=os.path.join(ROOT,'data','history')
DAILY_PATH=os.path.join(HISTORY_DIR,'daily.json')
NY=ZoneInfo('America/New_York')
CNBC_BASE='https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol'
MEGACAPS=['AAPL','MSFT','AMZN','GOOGL','META','NVDA','TSLA']
BREADTH=['NVDA','AAPL','MU','MSFT','AMD','AMZN','TSLA','GOOGL','INTC','GOOG','AVGO','META','AMAT','WMT','LRCX','CSCO','COST','KLAC','SNDK','NFLX','PANW','TXN','PLTR','MRVL','LIN','WDC','STX','AMGN','QCOM','CRWD','ADI','PEP','ASML','TMUS','APP','GILD','ARM','ISRG','SHOP','BKNG','VRTX','SBUX','FTNT','CDNS','MAR','MNST','CEG','ADP','CSX','CMCSA','DDOG','MELI','SNPS','ADBE','ALAB','ORLY','DASH','TER','AEP','MDLZ','INTU','NXPI','HON','HONA','ROST','CTAS','MPWR','WBD','LITE','REGN','RBLX','NBIS','ABNB','RKLB','FAST','BKR','PDD','XEL','FANG','MCHP','FER','EXC','TTWO','AXON','ODFL','CCEP','CRWV','KDP','IDXX','ADSK','ALNY','PYPL','PAYX','ROP','TRI','GEHC','MSTR','KHC','CPRT','DXCM','WDAY','SPCX']
SYMBOLS=list(dict.fromkeys(['US10Y','US2Y','ZQU6','ZQV6','ZQX6','ZQZ6','ZQF7','ZQG7','ZQH7','QQQ','NVDA','AMD','AVGO','TSM','.VIX','.VXN','@CL.1','@LCO.1','HYG','LQD','S5FI','.SOX','SOX']+MEGACAPS+BREADTH))

def cnbc_quotes(symbols):
    params={'symbols':'|'.join(symbols),'requestMethod':'itv','noform':'1','partnerId':'2','fund':'1','exthrs':'1','output':'json','events':'1'}
    url=CNBC_BASE+'?'+urllib.parse.urlencode(params,safe='|@.')
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/plain,*/*','Referer':'https://www.cnbc.com/'})
    with urllib.request.urlopen(req,timeout=20) as r: raw=r.read().decode('utf-8',errors='replace')
    data=json.loads(raw); qs=data.get('FormattedQuoteResult',{}).get('FormattedQuote',[])
    if isinstance(qs,dict): qs=[qs]
    return {q.get('symbol'):q for q in qs if q.get('symbol') and q.get('code')==0}

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
            r['explanation']=f'{x}. Level: {level}. Latest change: {move}.{confirm}{real}'
        elif n=='Semiconductor leadership':
            breadth=f" Market breadth is {direction('Market breadth')} ({latest('Market breadth')})." if live('Market breadth') else ''
            mega=f" Mega-cap leadership is {direction('Mega-cap leadership')}." if live('Mega-cap leadership') else ''
            r['explanation']=f'{x}. Semiconductors are {d.lower()}. Chips are a major Nasdaq/AI leadership group, so relative strength versus QQQ is an important risk-appetite confirmation. Current implication: {t}.{breadth}{mega}'
        elif n=='Mega-cap leadership':
            breadth=f" Breadth is {direction('Market breadth')}; {'broad participation confirms the move' if signal('Market breadth')=='positive' else 'the wider market is not giving equally strong confirmation' if signal('Market breadth')=='negative' else 'the wider market is giving only partial confirmation'}." if live('Market breadth') else ''
            semi=f" Semiconductor leadership is {direction('Semiconductor leadership')}." if live('Semiconductor leadership') else ''
            r['explanation']=f'{x}. The mega-cap basket is {d.lower()}. Nasdaq is more durable when its largest weights participate rather than the index being carried by a narrow subset. Current implication: {t}.{breadth}{semi}'
        elif n=='Market breadth':
            leaders=[]
            if live('Semiconductor leadership'): leaders.append('semiconductors are '+direction('Semiconductor leadership'))
            if live('Mega-cap leadership'): leaders.append('mega-caps are '+direction('Mega-cap leadership'))
            context=(' At the same time, '+ ' and '.join(leaders)+'.') if leaders else ''
            r['explanation']=f'{x}. Breadth is {d.lower()}. A larger share of advancing Nasdaq-100 constituents means wider participation; weak participation makes index strength less robust. Current implication: {t}.{context}'
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
            r['explanation']=f'{x}. {interp} Overall volatility signal: {t}.{context}'
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
            yields=f" With 2Y at {latest('2Y Treasury yield')} and 10Y at {latest('10Y nominal yield')}, a surprise that shifts inflation/Fed expectations could feed quickly into Nasdaq discount rates." if live('2Y Treasury yield') and live('10Y nominal yield') else ''
            r['explanation']=f'{x}. This is the next scheduled macro release capable of changing growth/inflation expectations, Treasury yields and the Fed path. Event status is {d.lower()}. {yields}'.strip()
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
            sig=change_sig if change_sig!='mixed' else level_sig
            setrow(rows,name,f'{v:.3f}%'+(f' ({bp:+.1f} bp vs prev close)' if bp is not None else ''),'Rising' if bp and bp>0 else ('Falling' if bp and bp<0 else 'Flat'),sig,fresh(x),'CNBC / Tradeweb quote feed')
            rr=next(z for z in rows if z['factor']==name)
            rr['levelSignal']=level_sig
            rr['changeSignal']=change_sig

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
        semis=['NVDA','AMD','AVGO','TSM']
        session=equity_session(now)
        session_label={'regular':'Live','afterhours':'After-hours','premarket':'Premarket','closed':'Closed'}[session]
        equity_available='QQQ' in q and equity_quote_available(q['QQQ'],session)

        if equity_available and all(sym in q and equity_quote_available(q[sym],session) for sym in semis):
            moves={sym:quoted_move(q[sym],session) for sym in semis}; qqq=quoted_move(q['QQQ'],session)
            valid=[v for v in moves.values() if v is not None]
            if valid and qqq is not None:
                avg=sum(valid)/len(valid); rel=avg-qqq
                sig='positive' if rel>0.25 else ('negative' if rel<-0.25 else 'mixed')
                direction='Leading QQQ' if rel>0.25 else ('Lagging QQQ' if rel<-0.25 else 'In line with QQQ')
                txt=session_label+' · '+' | '.join(f'{k} {v:+.2f}%' for k,v in moves.items())+f' | QQQ {qqq:+.2f}% | basket vs QQQ {rel:+.2f} pp'
                setrow(rows,'Semiconductor leadership',txt,direction,sig,session_label+' CNBC quote','CNBC quotes; session-aware equal-weight NVDA/AMD/AVGO/TSM vs QQQ calculation')
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

        # Volatility: VXN is Nasdaq-specific; VIX is included as confirmation.
        vx=q.get('.VXN'); vi=q.get('.VIX')
        if vx and vi:
            vxn=num(vx.get('last')); vix=num(vi.get('last')); vxnp=pct(vx); vixp=pct(vi)
            # VXN is the Nasdaq-specific gauge and is primary; VIX is confirmation.
            # Do not hide a large VXN move merely because broad-market VIX has not crossed the same threshold.
            if vxnp is not None and vxnp>=2:
                sig='mixed' if vixp is not None and vixp<=-2 else 'negative'
            elif vxnp is not None and vxnp<=-2:
                sig='mixed' if vixp is not None and vixp>=2 else 'positive'
            else:
                sig='mixed'
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

    # Scheduled macro/Fed event risk from official 2026 calendars. This is event timing, not a market-implied probability model.
    events=[
      (datetime.datetime(2026,9,29,10,0,tzinfo=NY),'JOLTS (Aug)','BLS'),
      (datetime.datetime(2026,9,30,8,30,tzinfo=NY),'PCE / Personal Income & Outlays (Aug)','BEA'),
      (datetime.datetime(2026,10,2,8,30,tzinfo=NY),'Employment Situation (Sep)','BLS'),
      (datetime.datetime(2026,10,7,14,0,tzinfo=NY),'FOMC Minutes (Sep 15–16 meeting)','Federal Reserve'),
      (datetime.datetime(2026,10,14,8,30,tzinfo=NY),'CPI (Sep)','BLS'),
      (datetime.datetime(2026,10,15,8,30,tzinfo=NY),'PPI (Sep)','BLS'),
      (datetime.datetime(2026,10,27,0,0,tzinfo=NY),'FOMC meeting begins (Oct 27–28)','Federal Reserve'),
      (datetime.datetime(2026,10,28,14,0,tzinfo=NY),'FOMC decision / press conference','Federal Reserve'),
      (datetime.datetime(2026,10,29,8,30,tzinfo=NY),'GDP advance Q3 + PCE (Sep)','BEA'),
      (datetime.datetime(2026,10,30,8,30,tzinfo=NY),'Employment Cost Index Q3','BLS')
    ]
    future=[e for e in events if e[0]>now]
    if future:
        et,name,agency=min(future,key=lambda e:e[0]); hours=(et-now).total_seconds()/3600
        urgency='High event risk' if hours<=24 else ('Event approaching' if hours<=72 else 'Scheduled')
        # Proximity raises impact/uncertainty but does not predict the sign of the surprise.
        esig='mixed'
        setrow(rows,'Economic / inflation data',f'Next: {name} · {et.strftime("%b %d, %H:%M ET")}',urgency,esig,f'Official calendar · checked {now.strftime("%Y-%m-%d %H:%M ET")}',f'{agency} official release calendar')
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
        '10Y nominal yield','2Y Treasury yield','Semiconductor leadership','Market breadth',
        'Nasdaq volatility (VXN / VIX)','Mega-cap leadership','Credit conditions',
        'Oil (WTI / Brent)','Options positioning / sentiment'
    }
    for r in rows:
        n=r['factor']
        impulse=r.get('changeSignal') if n in ('10Y nominal yield','2Y Treasury yield') else (r.get('signal') if n in dynamic_trend_factors else 'mixed')
        if impulse=='positive':
            r['trend']='Improving ↑'
        elif impulse=='negative':
            r['trend']='Deteriorating ↓'
        else:
            r['trend']='Stable →'

    # Composite Nasdaq Environment Score: direction x current impact x freshness.
    # Low/stale observations still contribute slightly but cannot dominate live high-impact signals.
    impact_w={'Very High':4,'High':3,'Medium':2,'Low':1}
    def freshness_w(r):
        f=str(r.get('freshness','')).lower()
        if f.startswith('stale') or 'research snapshot' in f or 'official data lag' in f: return 0.35
        if 'previous close' in f: return 0.70
        return 1.0
    numerator=0.0; denominator=0.0
    for r in rows:
        w=impact_w.get(r.get('currentImpact','Low'),1)*freshness_w(r)
        numerator += sig_score.get(r.get('signal','mixed'),0)*w
        denominator += w
    score=round(100*numerator/denominator) if denominator else 0
    d['environmentScore']=score
    d['environmentTrend']='Improving ↑' if score>d.get('environmentScorePrevious',score) else ('Deteriorating ↓' if score<d.get('environmentScorePrevious',score) else 'Stable →')
    d['environmentScorePrevious']=score

    explain_current_rows(rows)

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
        sig=all_signal if g.get('name')=='NASDAQ ENVIRONMENT' else group_signal(group_members.get(g.get('name'),[]))
        g['signal']=sig; g['label']=labels[sig]

    # Public presentation metadata is generated here so the browser remains a dumb renderer.
    group_explanations={
        'NASDAQ ENVIRONMENT':'Weighted composite of all 14 Nasdaq factors. Positive values indicate more supportive conditions; negative values indicate more headwinds. The trend shows the current directional impulse.',
        'Rates / Macro':'Combines Fed policy, Treasury yields and economic/inflation data. Falling yields or easier policy expectations are generally more supportive for growth stocks.',
        'Semiconductors':'Tracks semiconductor leadership relative to QQQ. Strong chip participation often confirms Nasdaq technology momentum.',
        'Breadth':'Measures how broadly Nasdaq-100 constituents participate. Broad participation generally makes index moves more robust.',
        'Risk / Credit':'Combines volatility and credit conditions. Rising VXN/VIX or weaker high-yield credit can indicate increasing market stress.',
        'AI / Fundamentals':'Summarizes earnings revisions, AI capex/monetization and technology earnings-event risk.'
    }
    for g in d.get('groups',[]):
        g['explanation']=group_explanations.get(g.get('name'),'Summary of the latest signals in this category.')
    impact_order={'Very High':0,'High':1,'Medium':2,'Low':3}
    rows.sort(key=lambda r:impact_order.get(r.get('currentImpact','Low'),3))
    for i,r in enumerate(rows,1):
        r['displayRank']=i
        r['signalLabel']={'positive':'🟢 Positive','negative':'🔴 Negative','mixed':'🟡 Mixed'}.get(r.get('signal'),'🟡 Mixed')

    # Consolidation / Extension Risk v1. This is intentionally separate from the
    # directional Nasdaq Environment score: a supportive tape can still be overextended.
    # Components progressively unlock as self-owned daily observations accumulate.
    try:
        with open(DAILY_PATH,encoding='utf-8') as hf: hist_for_risk=json.load(hf)
    except (FileNotFoundError,json.JSONDecodeError):
        hist_for_risk={'records':{}}
    hist_records=hist_for_risk.get('records',{})
    def hist_series(sym):
        out=[]
        seen=set()
        for day,rec in sorted(hist_records.items()):
            o=rec.get('market',{}).get(sym,{})
            od=o.get('observationDate') or day
            last=o.get('last')
            if last is not None and od not in seen:
                seen.add(od); out.append((od,float(last)))
        return out
    def risk_band(v):
        return 'Very High' if v>=75 else ('High' if v>=55 else ('Medium' if v>=30 else 'Low'))
    components=[]; weighted=0.0; total_w=0.0
    MODEL_WEIGHT=100.0
    def add_component(name,score,weight,detail):
        nonlocal_dummy=None
        components.append({'name':name,'score':round(score,1),'weight':weight,'detail':detail})
        return score*weight,weight

    # Current-day QQQ stretch: available immediately.
    qmove=quoted_move(q.get('QQQ',{}),equity_session(now)) if 'QQQ' in q else None
    if qmove is None and 'QQQ' in q: qmove=num(q['QQQ'].get('change_pct'))
    if qmove is not None:
        qs=min(100,max(0,(abs(qmove)-0.5)*28)) if qmove>0 else min(45,max(0,abs(qmove)*12))
        a,b=add_component('QQQ 1D stretch',qs,20,f'QQQ {qmove:+.2f}%'); weighted+=a; total_w+=b

    # SOX extension is especially relevant to Nasdaq/AI leadership.
    smove=num(q.get('.SOX',{}).get('change_pct')) if '.SOX' in q else None
    if smove is not None:
        ss=min(100,max(0,(abs(smove)-0.75)*22)) if smove>0 else min(45,max(0,abs(smove)*10))
        a,b=add_component('SOX 1D extension',ss,15,f'SOX {smove:+.2f}%'); weighted+=a; total_w+=b

    # Broad one-sided participation can indicate a short-term crowded impulse.
    br=next((r for r in rows if r['factor']=='Market breadth'),{})
    # Parse the displayed breadth percentage without regex escaping fragility.
    latest_breadth=br.get('latest','')
    bpct=None
    try:
        marker=latest_breadth.rsplit('(',1)[1].split('%',1)[0]
        bpct=float(marker)
    except (IndexError,ValueError):
        pass
    if bpct is not None:
        bs=min(100,max(0,(bpct-55)*2.5))
        a,b=add_component('Breadth intensity',bs,10,f'{bpct:.0f}% advancing'); weighted+=a; total_w+=b

    # Volatility behavior: falling vol into a strong rally adds complacency/extension risk;
    # rising vol offsets it rather than being treated as bullish/bearish direction.
    vxmove=num(q.get('.VXN',{}).get('change_pct')) if '.VXN' in q else None
    if vxmove is not None:
        vs=min(100,max(0,-vxmove*10)) if vxmove<0 else max(0,30-vxmove*5)
        a,b=add_component('Volatility behavior',vs,10,f'VXN {vxmove:+.2f}%'); weighted+=a; total_w+=b

    # Historical components unlock only when enough distinct observation dates exist.
    qhist=hist_series('QQQ')
    current_q=num(q.get('QQQ',{}).get('last')) if 'QQQ' in q else None
    if current_q is not None:
        # Use the quote's actual observation date. During premarket CNBC may still be
        # showing the previous cash session, which must not create a fake new history day.
        cq=q.get('QQQ',{})
        raw=str(cq.get('last_timedate') or cq.get('last_time') or '').strip()
        qdate=None
        token=raw.split()[0] if raw else ''
        try:
            if token.count('/')==2: qdate=datetime.datetime.strptime(token,'%m/%d/%y').date().isoformat()
            elif len(token)>=10 and token[4]=='-' and token[7]=='-': qdate=datetime.date.fromisoformat(token[:10]).isoformat()
        except ValueError:
            qdate=None
        if qdate:
            qhist=[x for x in qhist if x[0]!=qdate]
            qhist.append((qdate,current_q)); qhist.sort(key=lambda x:x[0])
    closes=[v for _,v in qhist]
    unlocked=[]
    if len(closes)>=4:
        r3=(closes[-1]/closes[-4]-1)*100; sc=min(100,max(0,(r3-1.5)*18))
        a,b=add_component('QQQ 3D return',sc,10,f'3D {r3:+.2f}%'); weighted+=a; total_w+=b; unlocked.append('3D')
    if len(closes)>=6:
        r5=(closes[-1]/closes[-6]-1)*100; sc=min(100,max(0,(r5-2.5)*14))
        a,b=add_component('QQQ 5D return',sc,10,f'5D {r5:+.2f}%'); weighted+=a; total_w+=b; unlocked.append('5D')
    if len(closes)>=5:
        ma5=sum(closes[-5:])/5; dist=(closes[-1]/ma5-1)*100; sc=min(100,max(0,(dist-1)*25))
        a,b=add_component('QQQ MA extension',sc,10,f'{dist:+.2f}% vs 5DMA'); weighted+=a; total_w+=b; unlocked.append('MA5')
    if len(closes)>=15:
        gains=[]; losses=[]
        for x,y in zip(closes[-15:-1],closes[-14:]):
            ch=y-x; gains.append(max(ch,0)); losses.append(max(-ch,0))
        ag=sum(gains)/14; al=sum(losses)/14
        rsi=100 if al==0 else 100-(100/(1+ag/al))
        sc=min(100,max(0,(rsi-55)*3))
        a,b=add_component('RSI14 stretch',sc,10,f'RSI14 {rsi:.1f}'); weighted+=a; total_w+=b; unlocked.append('RSI14')
    risk_score=round(weighted/total_w) if total_w else None
    d['consolidationRisk']={'score':risk_score,'level':risk_band(risk_score) if risk_score is not None else 'Unavailable',
        'explanation':'Measures short-term market extension and pullback/consolidation risk, not Nasdaq direction. The score blends QQQ and SOX stretch, breadth, volatility and, when enough history is available, multi-day returns, moving-average extension and RSI. Model coverage shows how much of the full 100-point model currently has usable data.',
        'coverageWeight':round(100*total_w/MODEL_WEIGHT),'components':components,'historyDays':len(closes),
        'unlocked':unlocked,'note':'Short-term extension risk, not a directional Nasdaq forecast. Historical components unlock as NasBoard history grows.'}

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
        if obs_date==today:
            state='live'
        elif obs_date:
            age=(datetime.date.fromisoformat(today)-datetime.date.fromisoformat(obs_date)).days
            state='previous_close' if 0 < age <= 3 else ('live' if age==0 else 'stale')
        else:
            state='unknown'
        return {'last':num(x.get('last')),'previousClose':num(x.get('previous_day_closing')),
                'changePct':num(x.get('change_pct')) if x.get('change_pct') not in (None,'') else pct(x),
                'timestamp':stamp,'observationDate':obs_date,'dataState':state}
    os.makedirs(HISTORY_DIR,exist_ok=True)
    market_symbols=['QQQ','.SOX','NVDA','AMD','AVGO','TSM','MU','AAPL','MSFT','AMZN','GOOGL','META','TSLA',
                    '.VXN','.VIX','US10Y','US2Y','@CL.1','@LCO.1','HYG','LQD']
    market={sym:quote_obs(sym) for sym in market_symbols if sym in q}
    current_session=[sym for sym in BREADTH if sym in q and is_intraday(q[sym],now)]
    pos=sum(1 for sym in current_session if (pct(q[sym]) or 0)>0)
    breadth_obs={'valid':len(current_session),'advancers':pos,'decliners':len(current_session)-pos,
                 'positivePct':round(100*pos/len(current_session),2) if current_session else None}
    factor_state={r['factor']:{'signal':r.get('signal'),'currentImpact':r.get('currentImpact'),
                              'trend':r.get('trend'),'latest':r.get('latest')} for r in rows}
    snapshot={'schemaVersion':1,'timestampET':now.isoformat(),'market':market,'breadth':breadth_obs,
              'environmentScore':d.get('environmentScore'),'environmentTrend':d.get('environmentTrend'),
              'factors':factor_state}
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

    d['updatedET']=now.strftime('%b %d, %Y · %H:%M ET'); d['nextUpdateET']='09:30 / 10:30 ET on trading weekdays'
    with open(PATH,'w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)

if __name__=='__main__':main()
