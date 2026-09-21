import json, urllib.request, urllib.parse, datetime, os, re, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT=os.path.dirname(os.path.dirname(__file__))
PATH=os.path.join(ROOT,'data','dashboard.json')
NY=ZoneInfo('America/New_York')
CNBC_BASE='https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol'
MEGACAPS=['AAPL','MSFT','AMZN','GOOGL','META','NVDA','TSLA']
BREADTH=['NVDA','AAPL','MU','MSFT','AMD','AMZN','TSLA','GOOGL','INTC','GOOG','AVGO','META','AMAT','WMT','LRCX','CSCO','COST','KLAC','SNDK','NFLX','PANW','TXN','PLTR','MRVL','LIN','WDC','STX','AMGN','QCOM','CRWD','ADI','PEP','ASML','TMUS','APP','GILD','ARM','ISRG','SHOP','BKNG','VRTX','SBUX','FTNT','CDNS','MAR','MNST','CEG','ADP','CSX','CMCSA','DDOG','MELI','SNPS','ADBE','ALAB','ORLY','DASH','TER','AEP','MDLZ','INTU','NXPI','HON','HONA','ROST','CTAS','MPWR','WBD','LITE','REGN','RBLX','NBIS','ABNB','RKLB','FAST','BKR','PDD','XEL','FANG','MCHP','FER','EXC','TTWO','AXON','ODFL','CCEP','CRWV','KDP','IDXX','ADSK','ALNY','PYPL','PAYX','ROP','TRI','GEHC','MSTR','KHC','CPRT','DXCM','WDAY','SPCX']
SYMBOLS=list(dict.fromkeys(['US10Y','US2Y','QQQ','NVDA','AMD','AVGO','TSM','.VIX','.VXN','.DXY','@CL.1','@LCO.1','HYG','LQD','S5FI']+MEGACAPS+BREADTH))

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
    v=num(q.get('last')); p=num(q.get('previous_day_closing'))
    return ((v/p)-1)*100 if v is not None and p not in (None,0) else None

def fresh(q):
    t=q.get('last_time') or q.get('last_timedate') or 'timestamp unavailable'
    # CNBC sometimes returns only YYYY-MM-DD for equities outside their active quote session.
    return ('CNBC previous close · '+t) if len(str(t))==10 else ('CNBC intraday · '+str(t))

def is_intraday(q,now):
    t=str(q.get('last_time') or q.get('last_timedate') or '')
    return len(t)>10 and t[:10]==now.strftime('%Y-%m-%d')

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
        if n=='10Y nominal yield' or n=='2Y Treasury yield':
            level=tone(r)
            move='supportive because yields fell' if r.get('changeSignal')=='positive' else ('a headwind because yields rose' if r.get('changeSignal')=='negative' else 'roughly neutral')
            other='2Y Treasury yield' if n=='10Y nominal yield' else '10Y nominal yield'
            confirm=''
            if live(other):
                od=by[other].get('changeSignal','mixed')
                confirm=(' The other key Treasury maturity is also falling, confirming near-term easing in rate pressure.' if od==r.get('changeSignal')=='positive' else (' The other key Treasury maturity is also rising, confirming broader near-term rate pressure.' if od==r.get('changeSignal')=='negative' else ' The two Treasury maturities are not giving a fully aligned change signal.'))
            real=f" The 10Y real yield is {latest('10Y real yield')}, so the real discount-rate backdrop remains {tone(by['10Y real yield'])}." if n=='10Y nominal yield' and live('10Y real yield') else ''
            r['explanation']=f'{x}. Level: {level}. Latest change: {move}.{confirm}{real}'
        elif n=='10Y real yield':
            extra=f" Nominal 10Y is {latest('10Y nominal yield')}, reinforcing the valuation message." if live('10Y nominal yield') and signal('10Y nominal yield')=='negative' else ''
            r['explanation']=f'{x}. This inflation-adjusted long-term discount rate is {d.lower()} and {t} for long-duration Nasdaq valuations because future earnings are discounted at a higher real rate.{extra}'
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
            if live('10Y nominal yield') and live('2Y Treasury yield'):
                context=f" Rate levels remain {tone(by['10Y nominal yield'])} at the 10Y and {tone(by['2Y Treasury yield'])} at the 2Y."
            r['explanation']=f'{x}. {interp} Overall volatility signal: {t}.{context}'
        elif n=='Credit conditions':
            vol=f" Volatility is also {direction('Nasdaq volatility (VXN / VIX)')}, providing {'consistent risk-on confirmation' if signal('Nasdaq volatility (VXN / VIX)')=='positive' and r.get('signal')=='positive' else 'a separate cross-check on risk appetite'}." if live('Nasdaq volatility (VXN / VIX)') else ''
            r['explanation']=f'{x}. HYG versus LQD is a liquid credit-risk proxy: stronger high-yield relative performance suggests easier/risk-on conditions, while underperformance suggests tightening. Credit is {d.lower()} and {t}.{vol}'
        elif n=='U.S. Dollar (DXY)':
            oil=f" Oil is {direction('Oil (WTI / Brent)')} ({latest('Oil (WTI / Brent)')}), another input into inflation/financial conditions." if live('Oil (WTI / Brent)') else ''
            r['explanation']=f'{x}. The dollar is {d.lower()}. A rapidly stronger dollar can tighten global financial conditions and pressure multinational technology earnings; a weaker dollar reduces that pressure. The present move is {t}. {oil}'.strip()
        elif n=='Oil (WTI / Brent)':
            rates=f" The 10Y yield is {latest('10Y nominal yield')}; oil matters for Nasdaq mainly through inflation expectations and the rate path." if live('10Y nominal yield') else ''
            r['explanation']=f'{x}. Oil is {d.lower()}. Large energy moves can alter inflation expectations and therefore Treasury yields/Fed expectations. Current implication: {t}.{rates}'
        elif n=='Options positioning / sentiment':
            vol=f" VXN/VIX are {direction('Nasdaq volatility (VXN / VIX)')} ({latest('Nasdaq volatility (VXN / VIX)')}), so options positioning and implied volatility together {'lean toward improving risk appetite' if signal('Nasdaq volatility (VXN / VIX)')=='positive' and r.get('signal')=='positive' else 'do not currently give the same strong directional signal'}." if live('Nasdaq volatility (VXN / VIX)') else ''
            r['explanation']=f'{x}. Equity put/call is compared with its 5-session baseline; Index and Total P/C add context because index puts often reflect institutional hedging. Positioning is {d.lower()} and {t}; this is not dealer gamma. {vol}'.strip()
        elif n=='Fed path / rate expectations':
            yields=f" Current rate-market context: 2Y {latest('2Y Treasury yield')} and 10Y {latest('10Y nominal yield')}." if live('2Y Treasury yield') and live('10Y nominal yield') else ''
            r['explanation']=f'{x}. This row tracks the next scheduled Fed catalyst rather than market-implied cut/hike probabilities. The event creates policy-rate risk for Nasdaq. {yields}'.strip()
        elif n=='Economic / inflation data':
            yields=f" With 2Y at {latest('2Y Treasury yield')} and 10Y at {latest('10Y nominal yield')}, a surprise that shifts inflation/Fed expectations could feed quickly into Nasdaq discount rates." if live('2Y Treasury yield') and live('10Y nominal yield') else ''
            r['explanation']=f'{x}. This is the next scheduled macro release capable of changing growth/inflation expectations, Treasury yields and the Fed path. Event status is {d.lower()}. {yields}'.strip()
        else:
            r['explanation']=f'Current reading: {x}. Direction: {d}. NasBoard currently classifies this factor as {t}. This row will become more specific as its underlying live/research source is automated.'

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
    now=datetime.datetime.now(NY); rows=d['rows']
    try:
        q=cnbc_quotes(SYMBOLS)
        # S5FI probe: S&P 500 stocks above 50-day moving average breadth index.
        # Keep this as a source test until CNBC symbol availability is verified in a real Action run.
        if 'S5FI' in q:
            sx=q['S5FI']
            print('S5FI CNBC probe:', json.dumps({k:sx.get(k) for k in ['symbol','name','last','previous_day_closing','last_time','last_timedate','code']}))
        else:
            print('S5FI CNBC probe: symbol not returned')

        # Treasury yields
        for sym,name in [('US10Y','10Y nominal yield'),('US2Y','2Y Treasury yield')]:
            x=q[sym]; v=num(x.get('last')); p=num(x.get('previous_day_closing')); bp=(v-p)*100 if v is not None and p is not None else None
            sig='negative' if v>=4.5 else ('mixed' if v>=4.0 else 'positive')
            setrow(rows,name,f'{v:.3f}%'+(f' ({bp:+.1f} bp vs prev close)' if bp is not None else ''),'Rising' if bp and bp>0 else ('Falling' if bp and bp<0 else 'Flat'),sig,fresh(x),'CNBC / Tradeweb quote feed')
            rr=next(z for z in rows if z['factor']==name)
            rr['levelSignal']=sig
            rr['changeSignal']='negative' if bp is not None and bp>1 else ('positive' if bp is not None and bp<-1 else 'mixed')

        # Leadership calculations only run when CNBC supplies current-session equity timestamps.
        semis=['NVDA','AMD','AVGO','TSM']
        equity_live='QQQ' in q and is_intraday(q['QQQ'],now)
        if equity_live and all(sym in q and is_intraday(q[sym],now) for sym in semis):
            moves={sym:pct(q[sym]) for sym in semis}; qqq=pct(q['QQQ'])
            valid=[v for v in moves.values() if v is not None]
            if valid and qqq is not None:
                avg=sum(valid)/len(valid); rel=avg-qqq
                sig='positive' if rel>0.25 else ('negative' if rel<-0.25 else 'mixed')
                direction='Leading QQQ' if rel>0.25 else ('Lagging QQQ' if rel<-0.25 else 'In line with QQQ')
                text=' | '.join(f'{k} {v:+.2f}%' for k,v in moves.items())+f' | QQQ {qqq:+.2f}% | basket vs QQQ {rel:+.2f} pp'
                setrow(rows,'Semiconductor leadership',text,direction,sig,fresh(q['QQQ']),'CNBC quotes; equal-weight NVDA/AMD/AVGO/TSM vs QQQ calculation')
        else:
            stamp=(q.get('QQQ',{}).get('last_time') or q.get('QQQ',{}).get('last_timedate') or 'unavailable')
            setrow(rows,'Semiconductor leadership',f'Awaiting current-session equity quotes — latest equity stamp {stamp}','Awaiting session','mixed',fresh(q['QQQ']) if 'QQQ' in q else 'STALE — QQQ unavailable','CNBC quotes; calculation suppressed when only previous-close data are available')

        # Mega-cap leadership: equal-weight basket versus QQQ, current session only.
        if equity_live:
            mm={sym:pct(q[sym]) for sym in MEGACAPS if sym in q and is_intraday(q[sym],now)}
            vals=[v for v in mm.values() if v is not None]; qqq=pct(q['QQQ'])
            if len(vals)>=5 and qqq is not None:
                avg=sum(vals)/len(vals); rel=avg-qqq; pos=sum(v>0 for v in vals)
                sig='positive' if rel>0.20 and pos>=4 else ('negative' if rel<-0.20 and pos<=3 else 'mixed')
                direction='Leading QQQ' if rel>0.20 else ('Lagging QQQ' if rel<-0.20 else 'In line with QQQ')
                setrow(rows,'Mega-cap leadership',f'{len(vals)}-stock basket {avg:+.2f}% | {pos}/{len(vals)} positive | QQQ {qqq:+.2f}% | relative {rel:+.2f} pp',direction,sig,fresh(q['QQQ']),'CNBC quotes; equal-weight AAPL/MSFT/AMZN/GOOGL/META/NVDA/TSLA basket vs QQQ')
        else:
            setrow(rows,'Mega-cap leadership','Awaiting current-session mega-cap quotes','Awaiting session','mixed',fresh(q['QQQ']) if 'QQQ' in q else 'STALE — QQQ unavailable','CNBC quotes; calculation suppressed outside current equity session')

        # Nasdaq-100 day breadth using the current constituent set. Multiple share classes mean the quote count can exceed 100.
        if equity_live:
            bm={sym:pct(q[sym]) for sym in BREADTH if sym in q and is_intraday(q[sym],now)}
            vals=[v for v in bm.values() if v is not None]
            if len(vals)>=80:
                adv=sum(v>0 for v in vals); dec=sum(v<0 for v in vals); flat=len(vals)-adv-dec; ratio=adv/len(vals)*100
                sig='positive' if ratio>=65 else ('negative' if ratio<=35 else 'mixed')
                direction='Broadening' if ratio>=65 else ('Weakening' if ratio<=35 else 'Mixed')
                setrow(rows,'Market breadth',f'Nasdaq-100 breadth: {adv}/{len(vals)} advancing ({ratio:.0f}%) · {dec} declining · {flat} flat',direction,sig,fresh(q['QQQ']),'CNBC quotes; Nasdaq-100 constituent day breadth')
        else:
            setrow(rows,'Market breadth','Awaiting current-session quotes for Nasdaq-100 breadth','Awaiting session','mixed',fresh(q['QQQ']) if 'QQQ' in q else 'STALE — QQQ unavailable','CNBC quotes; Nasdaq-100 constituent breadth; calculation suppressed outside current equity session')

        # Volatility: VXN is Nasdaq-specific; VIX is included as confirmation.
        vx=q.get('.VXN'); vi=q.get('.VIX')
        if vx and vi:
            vxn=num(vx.get('last')); vix=num(vi.get('last')); vxnp=pct(vx); vixp=pct(vi)
            sig='positive' if (vxnp is not None and vxnp<-2 and vixp is not None and vixp<-2) else ('negative' if (vxnp is not None and vxnp>2 and vixp is not None and vixp>2) else 'mixed')
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
        for name in ('10Y nominal yield','2Y Treasury yield','Semiconductor leadership','Nasdaq volatility (VXN / VIX)','U.S. Dollar (DXY)','Oil (WTI / Brent)'):
            next(x for x in rows if x['factor']==name)['freshness']='STALE — CNBC refresh failed'

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
        esig='negative' if hours<=24 else 'mixed'
        setrow(rows,'Economic / inflation data',f'Next: {name} · {et.strftime("%b %d, %H:%M ET")}',urgency,esig,f'Official calendar · checked {now.strftime("%Y-%m-%d %H:%M ET")}',f'{agency} official release calendar')
    fomc=[e for e in events if e[2]=='Federal Reserve' and e[0]>now]
    if fomc:
        et,name,_=min(fomc,key=lambda e:e[0])
        setrow(rows,'Fed path / rate expectations',f'Next Fed catalyst: {name} · {et.strftime("%b %d, %H:%M ET")}','Event risk','mixed',f'Federal Reserve calendar · checked {now.strftime("%Y-%m-%d %H:%M ET")}','Federal Reserve FOMC calendar; market-implied rate probabilities not yet connected')

    # Official Treasury TIPS par real yield curve: daily, not intraday.
    real=next(x for x in rows if x['factor']=='10Y real yield')
    try:
        rd,rv=treasury_10y_real(now.year)
        real.update(latest=f'{rv:.2f}%',direction='Elevated' if rv>=2.0 else ('Moderate' if rv>=1.0 else 'Low'),signal='negative' if rv>=2.0 else ('mixed' if rv>=1.0 else 'positive'),freshness=f'U.S. Treasury daily · {rd.isoformat()}',source='U.S. Department of the Treasury — Daily Treasury Par Real Yield Curve Rates (10Y TIPS)')
    except Exception as e:
        print('Treasury real-yield refresh failed:',repr(e))
        real['freshness']='STALE — U.S. Treasury daily feed refresh failed'
        real['source']='U.S. Department of the Treasury — Daily Treasury Par Real Yield Curve Rates (10Y TIPS)'
    # Current impact = magnitude of the factor's present Nasdaq effect, not its structural importance.
    # It is intentionally based on current observations/freshness and can change each refresh.
    for r in rows:
        n=r['factor']; imp='Medium'
        if 'Awaiting' in r.get('latest','') or str(r.get('freshness','')).startswith('STALE'):
            imp='Low'
        elif n in ('10Y nominal yield','2Y Treasury yield'):
            # High absolute yields remain important; a meaningful daily move raises immediate relevance.
            m=re.search(r'\(([+-]?[0-9.]+) bp',r.get('latest',''))
            bp=abs(float(m.group(1))) if m else 0
            imp='Very High' if bp>=5 else ('High' if bp>=2 else 'Medium')
        elif n=='10Y real yield':
            try: rv=float(r.get('latest','0').replace('%',''))
            except: rv=0
            imp='High' if rv>=2 else ('Medium' if rv>=1 else 'Low')
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
        elif n in ('Fed path / rate expectations','Economic / inflation data','Technology earnings calendar'):
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
                # Promote one tier on strong corroborating reaction; promote to Very High on exceptional reaction.
                rank={'Low':0,'Medium':1,'High':2,'Very High':3}; names=['Low','Medium','High','Very High']
                if reaction_score>=3: imp='Very High'
                elif reaction_score>=2: imp=names[min(3,rank[imp]+1)]
                r['impactReason']=f"Calendar: {days:.1f} days to event; market-reaction score {reaction_score}/4" if days is not None else f"Market-reaction score {reaction_score}/4"
            elif n=='Fed path / rate expectations':
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

    explain_current_rows(rows)
    d['updatedET']=now.strftime('%b %d, %Y · %H:%M ET'); d['nextUpdateET']='09:30 / 10:30 ET on trading weekdays'
    with open(PATH,'w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)

if __name__=='__main__':main()
