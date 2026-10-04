#!/usr/bin/env python3
"""NasDecode v3 secondary-score refinement.

Keeps three outputs orthogonal:
- Nasdaq Score: directional environment (raw setup score, no consolidation penalty).
- Consolidation Risk: 1-3 session vulnerability to fade/consolidation.
- Opportunity Score: quality of a *long* entry now.

The script runs immediately after refresh.py and overwrites only the derived public scores;
raw observations and the original model components remain in history for calibration.
"""
import datetime as dt
import json, math, os, re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DASH=ROOT/'data'/'dashboard.json'
DAILY=ROOT/'data'/'history'/'daily.json'
INTRADAY=ROOT/'data'/'history'/'intraday'
NY=ZoneInfo('America/New_York')


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError):
        return default

def num(v):
    try: return float(v)
    except (TypeError,ValueError): return None

def clamp(v,lo=0,hi=100): return max(lo,min(hi,float(v)))
def avg(vals):
    vals=[v for v in vals if v is not None]
    return sum(vals)/len(vals) if vals else None

def scale(v,lo,hi):
    if v is None: return None
    if hi==lo: return 50
    return clamp(100*(v-lo)/(hi-lo))

def row(d,name): return next((x for x in d.get('rows',[]) if x.get('factor')==name),{})
def parse(text,pat):
    m=re.search(pat,str(text or ''),re.I)
    return float(m.group(1)) if m else None

def score_label(s):
    if s>=45:return 'positive','Strong Positive'
    if s>=15:return 'positive','Cautiously Positive'
    if s>-15:return 'mixed','Mixed / Neutral'
    if s>-45:return 'negative','Cautiously Negative'
    return 'negative','Strong Negative'

def signal100(sig): return 100 if sig=='positive' else (0 if sig=='negative' else 50)


def main():
    d=load(DASH,{})
    daily=load(DAILY,{'schemaVersion':4,'records':{}})
    now=dt.datetime.now(NY)
    day=now.date().isoformat()
    rec=(daily.get('records') or {}).get(day,{})
    market=rec.get('market') or {}
    validation=rec.get('validation') or {}
    mc=validation.get('marketContext') or {}

    # --- Keep Nasdaq Score directional and preserve the bounded Market Response layer. ---
    # rawScore is the unmodified multi-factor model. effectiveScore, when present, is
    # the same directional model after persistent macro-response attenuation.
    ns=d.get('nasdaqScore') or {}
    raw=num(ns.get('rawScore'))
    effective=num(ns.get('effectiveScore'))
    directional=effective if effective is not None else raw
    if directional is not None:
        final=int(round(directional))
        sig,label=score_label(final)
        prev=num(ns.get('previousScore'))
        trend='Improving ↑' if prev is not None and final>prev else ('Deteriorating ↓' if prev is not None and final<prev else 'Stable →')
        ns.update({'score':final,'signal':sig,'label':label,'trend':trend})
        d['nasdaqScore']=ns
        d.pop('legacyConsolidationAdjustedScore',None)
        d['consolidationPenalty']=0

    # Current market observations.
    ix=market.get('.IXIC') or {}
    qqq=market.get('QQQ') or {}
    ix_ret=num(ix.get('changePct'))
    qqq_ret=num(qqq.get('changePct'))
    qqq_ctx=(d.get('historicalContext') or {}).get('QQQ') or {}
    soxx_ctx=(d.get('historicalContext') or {}).get('SOXX') or {}

    # Intraday high-water giveback from stored snapshots (more robust than relying on
    # a quote-provider session-high field). This measures deterioration of the tape.
    intraday_file=INTRADAY/f'{now:%Y-%m}.json'
    intra=load(intraday_file,{'snapshots':[]}).get('snapshots',[])
    ix_path=[]; qqq_path=[]
    for s in intra:
        try:
            ts=dt.datetime.fromisoformat(str(s.get('timestampET'))).astimezone(NY)
        except (TypeError,ValueError):
            continue
        if ts.date()!=now.date() or ts.hour*60+ts.minute<9*60+30: continue
        sm=s.get('market') or {}
        a=num((sm.get('.IXIC') or {}).get('changePct'))
        b=num((sm.get('QQQ') or {}).get('changePct'))
        if a is not None: ix_path.append(a)
        if b is not None: qqq_path.append(b)
    if ix_ret is not None: ix_path.append(ix_ret)
    if qqq_ret is not None: qqq_path.append(qqq_ret)
    ix_giveback=max(ix_path)-ix_ret if ix_path and ix_ret is not None else None
    qqq_giveback=max(qqq_path)-qqq_ret if qqq_path and qqq_ret is not None else None
    giveback=max([x for x in (ix_giveback,qqq_giveback) if x is not None],default=None)

    # ---------------- Consolidation Risk v3 ----------------
    # 1) Price extension (20%). A stretched tape is vulnerable, but extension alone
    # no longer dominates the score.
    extension=avg([
        scale(num(qqq_ctx.get('return3d')),0.5,4.0),
        scale(num(qqq_ctx.get('return5d')),1.0,6.0),
        scale(num(qqq_ctx.get('ma20Distance')),1.0,6.0),
        scale(num(qqq_ctx.get('rsi14')),55,75),
        scale(num(soxx_ctx.get('ma20Distance')),2.0,10.0)
    ])

    # 2) Intraday rejection (25%). A 1.25pp giveback from the best observed level
    # reaches maximum risk. Small givebacks are normal and score near zero.
    rejection=scale(giveback,0.15,1.25) if giveback is not None else None

    # 3) Breadth divergence (20%). Weak breadth under a positive index is much more
    # dangerous than weak breadth when the index is already falling.
    br=row(d,'Market breadth')
    breadth=parse(br.get('latest'),r'advancing\s*\(([0-9.]+)%\)')
    s5=row(d,'S&P 500 50D Breadth / Oversold')
    s5_level=parse(s5.get('latest'),r'([0-9.]+)% above 50D')
    s5_ch=parse(s5.get('latest'),r'([+-]?[0-9.]+) pp')
    breadth_weak=scale(50-(breadth or 50),0,20)
    divergence_bonus=25 if ix_ret is not None and ix_ret>0.35 and breadth is not None and breadth<50 else 0
    s5_weak=scale(40-(s5_level or 40),0,20)
    s5_deterioration=scale(-(s5_ch or 0),0,3)
    breadth_div=clamp(0.55*(breadth_weak or 0)+0.20*(s5_weak or 0)+0.10*(s5_deterioration or 0)+divergence_bonus)

    # 4) Leadership divergence (15%). Use the confirmation layer because it is now
    # current-session aware during cash hours.
    conf=(d.get('confirmationLayer') or {})
    semi=(conf.get('semiconductorLeadership') or {})
    rs=(semi.get('relativeStrengthPp') or {})
    sox_rs=num(rs.get('soxVsNasdaqPp')); soxx_rs=num(rs.get('soxxVsNasdaqPp')); smh_rs=num(rs.get('smhVsNasdaqPp'))
    mega=row(d,'Mega-cap leadership')
    mega_rel=parse(mega.get('latest'),r'(?:relative|basket vs QQQ)\s*([+-]?[0-9.]+)\s*pp')
    leadership_div=avg([
        scale(-(sox_rs or 0),0,1.0),scale(-(soxx_rs or 0),0,1.0),
        scale(-(smh_rs or 0),0,1.0),scale(-(mega_rel or 0),0,0.8)
    ])

    # 5) Stress confirmation (15%). Rising vol/rates while Nasdaq is positive is a
    # classic fragile-rally signature.
    vxn_ch=num(((mc.get('vxn') or {}).get('changePct')))
    y10_bp=num(((mc.get('us10y') or {}).get('changeBp')))
    y2_bp=num(((mc.get('us2y') or {}).get('changeBp')))
    stress=avg([scale(vxn_ch,0,6),scale(y10_bp,0,8),scale(y2_bp,0,8)])
    if ix_ret is not None and ix_ret>0.25 and avg([x for x in (vxn_ch,y10_bp) if x is not None]) not in (None,):
        if (vxn_ch or 0)>0 and (y10_bp or 0)>0: stress=clamp((stress or 0)+20)

    # 6) Event/catalyst risk (5%). Pending high-read-through events raise near-term
    # consolidation/gap risk but cannot dominate the score.
    catalyst=(d.get('catalystMomentum') or (semi.get('catalystMomentum') or {}))
    events=[]
    if isinstance(catalyst,dict):
        if catalyst.get('active'): events.append(catalyst.get('active'))
        events.extend(catalyst.get('recent') or [])
    pending_high=any(x and x.get('status')=='Pending' and 'high' in str((x.get('event') or {}).get('expectedReadThrough','')).lower() for x in events)
    event_risk=100 if pending_high else 25 if any(x and x.get('status')=='Pending' for x in events) else 0

    risk_components=[
        ('Price extension',extension,0.20),('Intraday rejection',rejection,0.25),
        ('Breadth divergence',breadth_div,0.20),('Leadership divergence',leadership_div,0.15),
        ('Volatility / rates stress',stress,0.15),('Event risk',event_risk,0.05)
    ]
    available=[x for x in risk_components if x[1] is not None]
    risk=round(sum(v*w for _,v,w in available)/sum(w for _,v,w in available)) if available else 50
    if risk>=75:risk_level='High'
    elif risk>=55:risk_level='Elevated'
    elif risk>=35:risk_level='Moderate'
    else:risk_level='Low'
    risk_sorted=sorted(((n,round(v)) for n,v,_ in available),key=lambda x:x[1],reverse=True)
    drivers=[f'{n} {v}' for n,v in risk_sorted[:3]]
    d['consolidationRisk']={
        'version':3,'score':risk,'level':risk_level,
        'horizon':'1–3 sessions',
        'components':{n:round(v) if v is not None else None for n,v,_ in risk_components},
        'intradayGivebackPp':round(giveback,2) if giveback is not None else None,
        'dominantDrivers':drivers,
        'explanation':f"1–3 session fade/consolidation risk is {risk_level.lower()} ({risk}/100). Main drivers: "+', '.join(drivers)+'. It measures extension plus live rejection/divergence; it does not change the directional Nasdaq Score.',
        'note':'Higher means the current move is more vulnerable to a fade or sideways reset; it is not a bearish-direction forecast.'
    }

    # ---------------- Opportunity Score v3 ----------------
    # A long-entry quality score. Avoid circular dependence on Consolidation Risk itself;
    # every component is computed directly from market observations.
    direction=_clamp=clamp((num((d.get('nasdaqScore') or {}).get('score')) or 0)*1.25+50)

    # Entry quality: better near/under the 20DMA or after a modest pullback; poor when
    # already stretched. VXN dislocation adds optionality but not if internals are broken.
    ma20=num(qqq_ctx.get('ma20Distance')); r5=num(qqq_ctx.get('return5d')); rsi=num(qqq_ctx.get('rsi14'))
    entry=avg([
        clamp(75-12*(ma20 or 0)),
        clamp(65-7*(r5 or 0)),
        clamp(75-2.5*((rsi or 50)-50))
    ])
    vxn=num(((mc.get('vxn') or {}).get('close')))
    if vxn is not None and 22<=vxn<=32: entry=clamp((entry or 50)+10)

    # Recovery/participation: live internal confirmation plus direction of breadth,
    # semiconductors, mega-caps and volatility.
    internal=num(((conf.get('internalConfirmation') or {}).get('score')))
    recovery=avg([
        internal,
        signal100(row(d,'Market breadth').get('signal')),
        signal100(row(d,'Semiconductor leadership').get('signal')),
        signal100(row(d,'Mega-cap leadership').get('signal')),
        signal100(row(d,'Nasdaq volatility (VXN / VIX)').get('signal'))
    ])

    # Macro tailwind: current changes matter more than absolute levels for entry timing.
    fed=row(d,'Fed expectations'); fed_rep=num(fed.get('fedRepricingScore'))
    oil=row(d,'Oil (WTI / Brent)')
    macro=avg([
        clamp(50-(y10_bp or 0)*6),clamp(50-(y2_bp or 0)*6),
        clamp(50+(fed_rep or 0)*0.5),signal100(oil.get('signal'))
    ])

    # Catalyst asymmetry. Observed positive persistent catalysts help; high pending risk
    # reduces entry quality until price confirms.
    catalyst_score=50
    for x in events:
        if not x: continue
        rt=str(x.get('readThrough') or '').lower(); ps=str(x.get('persistence') or '').lower()
        if x.get('status')=='Pending':
            catalyst_score-=15 if 'high' in str((x.get('event') or {}).get('expectedReadThrough','')).lower() else 5
        elif 'positive' in rt: catalyst_score+=15 if 'persist' in ps else 8
        elif 'negative' in rt: catalyst_score-=15
    catalyst_score=clamp(catalyst_score)

    opp_components=[('Directional edge',direction,0.25),('Entry quality',entry,0.25),
                    ('Recovery confirmation',recovery,0.25),('Macro timing',macro,0.15),
                    ('Catalyst asymmetry',catalyst_score,0.10)]
    opp_available=[x for x in opp_components if x[1] is not None]
    opp=round(sum(v*w for _,v,w in opp_available)/sum(w for _,v,w in opp_available)) if opp_available else 50

    # Behavioral gates: a falling tape with no internal recovery should not score as an
    # attractive long merely because it is cheap/oversold. Severe rejection also limits
    # entry quality until confirmation returns.
    if (direction or 0)<40 and (recovery or 0)<50: opp=min(opp,44)
    if risk>=75 and (recovery or 0)<70: opp=min(opp,49)
    if pending_high: opp=min(opp,64)

    if opp>=75: label='Strong Long Opportunity'; sig='positive'
    elif opp>=60: label='Attractive'; sig='positive'
    elif opp>=45: label='Selective'; sig='mixed'
    elif opp>=30: label='Wait for Confirmation'; sig='mixed'
    else: label='Poor Long Opportunity'; sig='negative'
    if (recovery or 0)>=65 and (entry or 0)>=60 and (direction or 0)<60: opp_type='Recovery / dip entry'
    elif (direction or 0)>=60 and (recovery or 0)>=60: opp_type='Trend continuation'
    elif (recovery or 0)<45: opp_type='Wait for confirmation'
    else: opp_type='Selective / mixed'
    opp_sorted=sorted(((n,round(v)) for n,v,_ in opp_available),key=lambda x:x[1],reverse=True)
    weak_sorted=sorted(((n,round(v)) for n,v,_ in opp_available),key=lambda x:x[1])
    d['opportunityScore']={
        'version':3,'score':opp,'label':label,'signal':sig,'type':opp_type,
        'components':{n:round(v) if v is not None else None for n,v,_ in opp_components},
        'strongestDrivers':[f'{n} {v}' for n,v in opp_sorted[:2]],
        'weakestDrivers':[f'{n} {v}' for n,v in weak_sorted[:2]],
        'explanation':f"Long-entry quality is {label.lower()} ({opp}/100; {opp_type}). Strongest inputs: "+', '.join(f'{n} {v}' for n,v in opp_sorted[:2])+'. Weakest: '+', '.join(f'{n} {v}' for n,v in weak_sorted[:2])+'.',
        'note':'This is an entry-quality score, not a forecast of the next session return.'
    }


    # ---------------- SOXL Buy Score v1 ----------------
    # Tactical 1-5 session entry score for the 3x daily semiconductor ETF. This is
    # intentionally separate from the broader Opportunity Score: semiconductor trend
    # and SOXL's own entry quality dominate, while leverage-sensitive risk can hard-cap it.
    soxl_ctx=(d.get('historicalContext') or {}).get('SOXL') or {}
    soxl_obs=market.get('SOXL') or {}
    soxl_last=num(soxl_obs.get('last')); soxl_change=num(soxl_obs.get('changePct'))

    # Intraday SOXL giveback from the best observed regular-session return.
    soxl_path=[]
    for s in intra:
        try:
            ts=dt.datetime.fromisoformat(str(s.get('timestampET'))).astimezone(NY)
        except (TypeError,ValueError):
            continue
        if ts.date()!=now.date() or ts.hour*60+ts.minute<9*60+30: continue
        v=num(((s.get('market') or {}).get('SOXL') or {}).get('changePct'))
        if v is not None: soxl_path.append(v)
    if soxl_change is not None: soxl_path.append(soxl_change)
    soxl_giveback=(max(soxl_path)-soxl_change) if soxl_path and soxl_change is not None else None

    # 1) Semiconductor trend / leadership (30%).
    semi_score=num(semi.get('score'))
    semi_trend=avg([
        semi_score,
        scale(sox_rs,-1.5,1.5) if sox_rs is not None else None,
        scale(soxx_rs,-1.5,1.5) if soxx_rs is not None else None,
        scale(smh_rs,-1.5,1.5) if smh_rs is not None else None
    ])

    # 2) SOXL entry quality (25%). Reward a controlled pullback/normal extension,
    # not a falling knife and not a chase after an already extreme leveraged run.
    sx_ma20=num(soxl_ctx.get('ma20Distance')); sx_r5=num(soxl_ctx.get('return5d'))
    sx_rsi=num(soxl_ctx.get('rsi14')); sx_highdist=num(soxl_ctx.get('distanceFromWindowHighPct'))
    ma_entry=clamp(85-8*max(sx_ma20 or 0,0)-5*max(-(sx_ma20 or 0),0)) if sx_ma20 is not None else None
    r5_entry=clamp(78-5*max((sx_r5 or 0)-4,0)-4*max(-(sx_r5 or 0)-3,0)) if sx_r5 is not None else None
    rsi_entry=clamp(88-3*abs((sx_rsi or 55)-55)) if sx_rsi is not None else None
    high_entry=clamp(82-5*abs((sx_highdist or -4)+4)) if sx_highdist is not None else None
    intraday_entry=clamp(100-25*soxl_giveback) if soxl_giveback is not None else None
    soxl_entry=avg([ma_entry,r5_entry,rsi_entry,high_entry,intraday_entry])

    # 3) Broader market confirmation (15%).
    market_confirmation=avg([
        internal,
        direction,
        signal100(row(d,'Market breadth').get('signal')),
        signal100(row(d,'Mega-cap leadership').get('signal'))
    ])

    # 4) Volatility / leverage risk (15%). High consolidation risk and a volatility
    # expansion are especially costly for a daily 3x instrument.
    leverage_risk=avg([
        100-risk,
        signal100(row(d,'Nasdaq volatility (VXN / VIX)').get('signal')),
        clamp(50-(vxn_ch or 0)*6) if vxn_ch is not None else None
    ])

    # 5) Rates / macro timing (10%), including the verified release-surprise mix.
    release_mix=row(d,'Inflation · Labor · Growth')
    soxl_macro=avg([
        clamp(50-(y10_bp or 0)*6), clamp(50-(y2_bp or 0)*6),
        clamp(50+(fed_rep or 0)*0.5), signal100(release_mix.get('signal')),
        signal100(oil.get('signal'))
    ])

    # 6) Semiconductor catalyst asymmetry (5%).
    soxl_catalyst=catalyst_score

    sx_components=[
        ('Semiconductor trend',semi_trend,0.30),('SOXL entry quality',soxl_entry,0.25),
        ('Market confirmation',market_confirmation,0.15),('Volatility / leverage risk',leverage_risk,0.15),
        ('Rates / macro',soxl_macro,0.10),('Catalyst asymmetry',soxl_catalyst,0.05)
    ]
    sx_available=[x for x in sx_components if x[1] is not None]
    soxl_score=round(sum(v*w for _,v,w in sx_available)/sum(w for _,v,w in sx_available)) if sx_available else 50
    gates=[]

    # Hard gates stop cheap/oversold readings from becoming false buy signals.
    if semi_trend is not None and semi_trend<40:
        soxl_score=min(soxl_score,45); gates.append('Weak semiconductor trend caps score at 45')
    rs_vals=[x for x in (sox_rs,soxx_rs,smh_rs) if x is not None]
    if len(rs_vals)>=2 and all(x<0 for x in rs_vals):
        soxl_score=min(soxl_score,50); gates.append('Broad semiconductor underperformance caps score at 50')
    if risk>=75:
        soxl_score=min(soxl_score,45); gates.append('High consolidation risk caps score at 45')
    if sx_ma20 is not None and sx_ma20>8:
        soxl_score=min(soxl_score,55); gates.append('SOXL >8% above 20DMA caps chase entry at 55')
    if vxn_ch is not None and y10_bp is not None and vxn_ch>8 and y10_bp>5:
        soxl_score=min(soxl_score,45); gates.append('Volatility + yield shock caps score at 45')
    if pending_high:
        soxl_score=min(soxl_score,64); gates.append('Pending high-impact semiconductor catalyst caps score at 64')

    if soxl_score>=85: sx_label='Exceptional Tactical Entry'; sx_sig='positive'
    elif soxl_score>=70: sx_label='Attractive'; sx_sig='positive'
    elif soxl_score>=55: sx_label='Selective / Starter'; sx_sig='mixed'
    elif soxl_score>=40: sx_label='Wait'; sx_sig='mixed'
    elif soxl_score>=25: sx_label='Poor Entry'; sx_sig='negative'
    else: sx_label='Avoid Long'; sx_sig='negative'

    sx_sorted=sorted(((n,round(v)) for n,v,_ in sx_available),key=lambda x:x[1],reverse=True)
    sx_weak=sorted(((n,round(v)) for n,v,_ in sx_available),key=lambda x:x[1])
    d['soxlBuyScore']={
        'version':1,'score':soxl_score,'label':sx_label,'signal':sx_sig,'horizon':'1–5 sessions',
        'instrument':'SOXL','last':soxl_last,'changePct':soxl_change,
        'components':{n:round(v) if v is not None else None for n,v,_ in sx_components},
        'gates':gates,'intradayGivebackPp':round(soxl_giveback,2) if soxl_giveback is not None else None,
        'technicalContext':{
            'ma20DistancePct':round(sx_ma20,2) if sx_ma20 is not None else None,
            'return5dPct':round(sx_r5,2) if sx_r5 is not None else None,
            'rsi14':round(sx_rsi,1) if sx_rsi is not None else None,
            'distanceFromWindowHighPct':round(sx_highdist,2) if sx_highdist is not None else None
        },
        'strongestDrivers':[f'{n} {v}' for n,v in sx_sorted[:2]],
        'weakestDrivers':[f'{n} {v}' for n,v in sx_weak[:2]],
        'explanation':f"SOXL tactical entry quality is {sx_label.lower()} ({soxl_score}/100) for a 1–5 session horizon. "
                      +('Active gates: '+ '; '.join(gates)+'. ' if gates else '')
                      +'Strongest inputs: '+', '.join(f'{n} {v}' for n,v in sx_sorted[:2])+'. Weakest: '+', '.join(f'{n} {v}' for n,v in sx_weak[:2])+'.',
        'note':'Experimental tactical score for a daily 3x leveraged ETF. It measures entry quality, not expected return or position size.'
    }

    DASH.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    # Keep today's history synchronized with the refined public scores.
    rec=(daily.setdefault('records',{})).get(day)
    if isinstance(rec,dict):
        rec['nasdaqScore']={k:v for k,v in d.get('nasdaqScore',{}).items() if k!='model'}
        rec['consolidationRisk']=d['consolidationRisk']
        rec['opportunityScore']=d['opportunityScore']
        rec['soxlBuyScore']=d['soxlBuyScore']
        if isinstance(rec.get('validation'),dict):
            ms=rec['validation'].setdefault('modelState',{})
            ms['nasdaqScore']=rec['nasdaqScore']; ms['consolidationRisk']=d['consolidationRisk']; ms['opportunityScore']=d['opportunityScore']; ms['soxlBuyScore']=d['soxlBuyScore']
        if isinstance(rec.get('closeSnapshot'),dict):
            rec['closeSnapshot']['nasdaqScore']=rec['nasdaqScore']
            rec['closeSnapshot']['consolidationRisk']=d['consolidationRisk']
            rec['closeSnapshot']['opportunityScore']=d['opportunityScore']
            rec['closeSnapshot']['soxlBuyScore']=d['soxlBuyScore']
        DAILY.write_text(json.dumps(daily,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    print(f'v3 scores: Nasdaq {d.get("nasdaqScore",{}).get("score"):+} | Consolidation {risk} ({risk_level}) | Opportunity {opp} ({label}) | SOXL Buy {soxl_score} ({sx_label})')

if __name__=='__main__': main()
