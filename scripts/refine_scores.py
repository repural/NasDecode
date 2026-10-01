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

    # --- Make Nasdaq Score directional again: no consolidation-risk penalty. ---
    ns=d.get('nasdaqScore') or {}
    raw=num(ns.get('rawScore'))
    if raw is not None:
        old_final=num(ns.get('score'))
        final=int(round(raw))
        sig,label=score_label(final)
        prev=num(ns.get('previousScore'))
        trend='Improving ↑' if prev is not None and final>prev else ('Deteriorating ↓' if prev is not None and final<prev else 'Stable →')
        ns.update({'score':final,'signal':sig,'label':label,'trend':trend})
        d['nasdaqScore']=ns
        d['legacyConsolidationAdjustedScore']=old_final
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

    DASH.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    # Keep today's history synchronized with the refined public scores.
    rec=(daily.setdefault('records',{})).get(day)
    if isinstance(rec,dict):
        rec['nasdaqScore']={k:v for k,v in d.get('nasdaqScore',{}).items() if k!='model'}
        rec['consolidationRisk']=d['consolidationRisk']
        rec['opportunityScore']=d['opportunityScore']
        if isinstance(rec.get('validation'),dict):
            ms=rec['validation'].setdefault('modelState',{})
            ms['nasdaqScore']=rec['nasdaqScore']; ms['consolidationRisk']=d['consolidationRisk']; ms['opportunityScore']=d['opportunityScore']
        if isinstance(rec.get('closeSnapshot'),dict):
            rec['closeSnapshot']['nasdaqScore']=rec['nasdaqScore']
            rec['closeSnapshot']['consolidationRisk']=d['consolidationRisk']
            rec['closeSnapshot']['opportunityScore']=d['opportunityScore']
        DAILY.write_text(json.dumps(daily,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    print(f'v3 scores: Nasdaq {d.get("nasdaqScore",{}).get("score"):+} | Consolidation {risk} ({risk_level}) | Opportunity {opp} ({label})')

if __name__=='__main__': main()
