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

def piecewise(v,points):
    """Piecewise-linear interpolation over sorted (x,y) points."""
    if v is None: return None
    if v<=points[0][0]: return float(points[0][1])
    if v>=points[-1][0]: return float(points[-1][1])
    for (x0,y0),(x1,y1) in zip(points,points[1:]):
        if x0<=v<=x1:
            return float(y0)+(float(y1)-float(y0))*(float(v)-float(x0))/(float(x1)-float(x0))
    return float(points[-1][1])


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

    # ---------------- Consolidation Risk v4 ----------------
    # Separate latent structural extension from confirmation that a consolidation
    # is actually beginning. Being at a high is not bearish by itself; being near
    # a high while stretched above the 20DMA and overbought creates baseline risk.

    qqq_ma20=num(qqq_ctx.get('ma20Distance'))
    qqq_rsi=num(qqq_ctx.get('rsi14'))
    qqq_r3=num(qqq_ctx.get('return3d'))
    qqq_r5=num(qqq_ctx.get('return5d'))
    qqq_highdist=num(qqq_ctx.get('distanceFrom20dHighPct'))
    soxx_ma20=num(soxx_ctx.get('ma20Distance'))
    soxx_rsi=num(soxx_ctx.get('rsi14'))
    soxx_highdist=num(soxx_ctx.get('distanceFrom20dHighPct'))

    # Core extension readings. QQQ uses tighter thresholds than SOXX because
    # semiconductor indices normally carry more volatility.
    qqq_ma_risk=scale(qqq_ma20,1.0,6.0) if qqq_ma20 is not None else None
    qqq_rsi_risk=scale(qqq_rsi,60,80) if qqq_rsi is not None else None
    qqq_momentum_risk=avg([
        scale(qqq_r3,0.5,4.0) if qqq_r3 is not None else None,
        scale(qqq_r5,1.0,6.0) if qqq_r5 is not None else None
    ])
    soxx_ma_risk=scale(soxx_ma20,2.0,10.0) if soxx_ma20 is not None else None
    soxx_rsi_risk=scale(soxx_rsi,60,85) if soxx_rsi is not None else None

    # High proximity only matters when extension already exists. At the 20-day
    # high proximity=100; it fades to zero once price is >=2% below that high.
    # This avoids an arbitrary ATH penalty: a high near the 20DMA is healthy,
    # while a high far above the 20DMA with elevated RSI is structurally fragile.
    qqq_high_proximity=scale(2-abs(qqq_highdist),0,2) if qqq_highdist is not None else None
    soxx_high_proximity=scale(2-abs(soxx_highdist),0,2) if soxx_highdist is not None else None
    qqq_extension_pressure=avg([qqq_ma_risk,qqq_rsi_risk])
    soxx_extension_pressure=avg([soxx_ma_risk,soxx_rsi_risk])
    qqq_high_interaction=(qqq_extension_pressure*qqq_high_proximity/100
                          if qqq_extension_pressure is not None and qqq_high_proximity is not None else None)
    soxx_high_interaction=(soxx_extension_pressure*soxx_high_proximity/100
                           if soxx_extension_pressure is not None and soxx_high_proximity is not None else None)

    structural_parts=[
        ('QQQ vs 20DMA',qqq_ma_risk,0.20),
        ('QQQ RSI14',qqq_rsi_risk,0.15),
        ('QQQ 3D/5D acceleration',qqq_momentum_risk,0.10),
        ('QQQ high × extension',qqq_high_interaction,0.15),
        ('SOXX vs 20DMA',soxx_ma_risk,0.15),
        ('SOXX RSI14',soxx_rsi_risk,0.10),
        ('SOXX high × extension',soxx_high_interaction,0.15)
    ]
    structural_available=[x for x in structural_parts if x[1] is not None]
    structural_extension=(sum(v*w for _,v,w in structural_available)/sum(w for _,v,w in structural_available)
                          if structural_available else None)

    # Structural extension establishes a floor rather than a full forecast.
    # 65% of structural pressure becomes latent consolidation risk; live
    # rejection/divergence can then consume the remaining headroom.
    structural_floor=clamp((structural_extension or 0)*0.65) if structural_extension is not None else 0

    # 2) Intraday rejection. A 1.25pp giveback from the best observed regular-
    # session Nasdaq/QQQ level reaches maximum confirmation risk.
    rejection=scale(giveback,0.15,1.25) if giveback is not None else None

    # 3) Breadth divergence. Weak breadth under a positive index is more dangerous
    # than weak breadth when the index is already falling.
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

    # 4) Leadership divergence.
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

    # 5) Volatility/rates stress.
    vxn_ch=num(((mc.get('vxn') or {}).get('changePct')))
    y10_bp=num(((mc.get('us10y') or {}).get('changeBp')))
    y2_bp=num(((mc.get('us2y') or {}).get('changeBp')))
    stress=avg([scale(vxn_ch,0,6),scale(y10_bp,0,8),scale(y2_bp,0,8)])
    if ix_ret is not None and ix_ret>0.25 and avg([x for x in (vxn_ch,y10_bp) if x is not None]) not in (None,):
        if (vxn_ch or 0)>0 and (y10_bp or 0)>0: stress=clamp((stress or 0)+20)

    # 6) Event/catalyst risk.
    catalyst=(d.get('catalystMomentum') or (semi.get('catalystMomentum') or {}))
    events=[]
    if isinstance(catalyst,dict):
        if catalyst.get('active'): events.append(catalyst.get('active'))
        events.extend(catalyst.get('recent') or [])
    pending_high=any(x and x.get('status')=='Pending' and 'high' in str((x.get('event') or {}).get('expectedReadThrough','')).lower() for x in events)
    event_risk=100 if pending_high else 25 if any(x and x.get('status')=='Pending' for x in events) else 0

    # Confirmation does not erase structural extension. Instead it raises risk
    # from the structural floor toward 100 as actual deterioration appears.
    confirmation_parts=[
        ('Intraday rejection',rejection,0.30),
        ('Breadth divergence',breadth_div,0.25),
        ('Leadership divergence',leadership_div,0.20),
        ('Volatility / rates stress',stress,0.20),
        ('Event risk',event_risk,0.05)
    ]
    confirmation_available=[x for x in confirmation_parts if x[1] is not None]
    confirmation_risk=(sum(v*w for _,v,w in confirmation_available)/sum(w for _,v,w in confirmation_available)
                       if confirmation_available else 0)
    risk=round(structural_floor+(100-structural_floor)*(confirmation_risk/100))

    if risk>=75:risk_level='High'
    elif risk>=55:risk_level='Elevated'
    elif risk>=35:risk_level='Moderate'
    else:risk_level='Low'

    # Coverage is explicit so the UI never prints an undefined value.
    structural_weight=sum(w for _,v,w in structural_parts if v is not None)
    confirmation_weight=sum(w for _,v,w in confirmation_parts if v is not None)
    coverage_weight=round(100*(structural_weight+confirmation_weight)/2)
    history_days=min([int(x.get('bars')) for x in (qqq_ctx,soxx_ctx) if x.get('bars') is not None] or [0])

    component_values=[
        ('Structural extension',structural_extension),
        ('Structural floor',structural_floor),
        ('Confirmation risk',confirmation_risk),
        ('Intraday rejection',rejection),
        ('Breadth divergence',breadth_div),
        ('Leadership divergence',leadership_div),
        ('Volatility / rates stress',stress),
        ('Event risk',event_risk)
    ]
    risk_sorted=sorted(((n,round(v)) for n,v in component_values if v is not None and n!='Structural floor'),
                       key=lambda x:x[1],reverse=True)
    drivers=[f'{n} {v}' for n,v in risk_sorted[:3]]

    d['consolidationRisk']={
        'version':4,'score':risk,'level':risk_level,
        'horizon':'1–3 sessions',
        'coverageWeight':coverage_weight,
        'historyDays':history_days,
        'structuralFloor':round(structural_floor),
        'components':{n:round(v) if v is not None else None for n,v in component_values},
        'structuralComponents':{n:round(v) if v is not None else None for n,v,_ in structural_parts},
        'technicalContext':{
            'qqqMa20DistancePct':round(qqq_ma20,2) if qqq_ma20 is not None else None,
            'qqqRsi14':round(qqq_rsi,1) if qqq_rsi is not None else None,
            'qqqDistanceFrom20dHighPct':round(qqq_highdist,2) if qqq_highdist is not None else None,
            'soxxMa20DistancePct':round(soxx_ma20,2) if soxx_ma20 is not None else None,
            'soxxRsi14':round(soxx_rsi,1) if soxx_rsi is not None else None,
            'soxxDistanceFrom20dHighPct':round(soxx_highdist,2) if soxx_highdist is not None else None
        },
        'intradayGivebackPp':round(giveback,2) if giveback is not None else None,
        'dominantDrivers':drivers,
        'explanation':f"1–3 session fade/consolidation risk is {risk_level.lower()} ({risk}/100). Structural extension creates a {round(structural_floor)}/100 baseline; live confirmation risk is {round(confirmation_risk)}/100. Main drivers: "+', '.join(drivers)+'. A high near the 20DMA is not penalized by itself; high proximity matters when QQQ/SOXX are also stretched or overbought.',
        'note':'Higher means the current move is more vulnerable to a fade or sideways reset; it is not a bearish-direction forecast.'
    }

    # ---------------- Opportunity Score v4 ----------------
    # General long-entry quality. Direction/recovery tell us whether the tape is
    # constructive; Entry Quality tells us whether the current PRICE LOCATION is
    # attractive enough to initiate exposure. Consolidation Risk is used only as
    # a final sanity gate so its extension inputs are not double-counted as a sixth
    # weighted component.
    direction=clamp((num((d.get('nasdaqScore') or {}).get('score')) or 0)*1.25+50)

    # Entry Quality v4: explicitly price-location aware.
    # QQQ is the primary Nasdaq entry instrument/context. SOXX is included because
    # semiconductor extension matters materially to a semiconductor-led Nasdaq.
    ma20=num(qqq_ctx.get('ma20Distance'))
    r5=num(qqq_ctx.get('return5d'))
    rsi=num(qqq_ctx.get('rsi14'))

    qqq_ma_entry=clamp(75-12*(ma20 or 0)) if ma20 is not None else None
    qqq_rsi_entry=clamp(75-2.5*((rsi or 50)-50)) if rsi is not None else None
    qqq_r5_entry=clamp(65-7*(r5 or 0)) if r5 is not None else None

    # Invert the extension-aware high interaction from Consolidation Risk v4.
    # Being at a high near the 20DMA is not penalized much; being at a high while
    # stretched/overbought is a poor entry location.
    qqq_high_entry=(100-qqq_high_interaction) if qqq_high_interaction is not None else None

    # SOXX structural extension combines trend distance, RSI and high x extension.
    # It is inverted for entry quality: extreme semiconductor extension reduces the
    # attractiveness of initiating broad Nasdaq exposure even when leadership is strong.
    soxx_structural_extension=avg([soxx_ma_risk,soxx_rsi_risk,soxx_high_interaction])
    soxx_extension_entry=(100-soxx_structural_extension) if soxx_structural_extension is not None else None

    entry_parts=[
        ('QQQ vs 20DMA',qqq_ma_entry,0.30),
        ('QQQ RSI14',qqq_rsi_entry,0.20),
        ('QQQ 5D return',qqq_r5_entry,0.15),
        ('QQQ high × extension',qqq_high_entry,0.20),
        ('SOXX structural extension',soxx_extension_entry,0.15)
    ]
    entry_available=[x for x in entry_parts if x[1] is not None]
    entry=(sum(v*w for _,v,w in entry_available)/sum(w for _,v,w in entry_available)
           if entry_available else None)

    # Tradable volatility can improve optionality, but only when price location is
    # not already structurally extreme. It must never turn a poor chase into a good one.
    vxn=num(((mc.get('vxn') or {}).get('close')))
    vxn_entry_bonus=10 if (vxn is not None and 22<=vxn<=32 and
                           (structural_extension or 0)<70 and (entry or 0)>=35) else 0
    if entry is not None and vxn_entry_bonus:
        entry=clamp(entry+vxn_entry_bonus)

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

    opp_components=[('Directional edge',direction,0.20),('Entry quality',entry,0.35),
                    ('Recovery confirmation',recovery,0.20),('Macro timing',macro,0.15),
                    ('Catalyst asymmetry',catalyst_score,0.10)]
    opp_available=[x for x in opp_components if x[1] is not None]
    opp_raw=round(sum(v*w for _,v,w in opp_available)/sum(w for _,v,w in opp_available)) if opp_available else 50
    opp=opp_raw
    opp_gates=[]

    # Behavioral gates. Consolidation Risk is deliberately a gate rather than a
    # weighted input: the same 20DMA/RSI/high-location data already contributes to
    # Entry Quality. The gate simply prevents strong recovery/catalysts from relabeling
    # a stretched entry as Attractive.
    if (direction or 0)<40 and (recovery or 0)<50:
        opp=min(opp,44)
        opp_gates.append('Weak direction + weak recovery caps opportunity at 44')
    if risk>=35 and risk<55 and (entry or 0)<45:
        opp=min(opp,59)
        opp_gates.append('Moderate consolidation risk + weak entry quality caps opportunity at 59')
    elif risk>=55 and risk<75 and (entry or 0)<50:
        opp=min(opp,54)
        opp_gates.append('Elevated consolidation risk + weak entry quality caps opportunity at 54')
    elif risk>=75:
        if (entry or 0)<50 or (recovery or 0)<70:
            opp=min(opp,44)
            opp_gates.append('High consolidation risk without a strong reset/recovery entry caps opportunity at 44')
        else:
            opp=min(opp,49)
            opp_gates.append('High consolidation risk caps opportunity at 49 pending stronger confirmation')
    if pending_high:
        opp=min(opp,64)
        opp_gates.append('Pending high-impact catalyst caps opportunity at 64')

    if opp>=75: label='Strong Long Opportunity'; sig='positive'
    elif opp>=60: label='Attractive'; sig='positive'
    elif opp>=45: label='Selective'; sig='mixed'
    elif opp>=30: label='Wait for Confirmation'; sig='mixed'
    else: label='Poor Long Opportunity'; sig='negative'

    if (recovery or 0)>=65 and (entry or 0)>=60 and (direction or 0)<60:
        opp_type='Recovery / dip entry'
    elif (direction or 0)>=60 and (recovery or 0)>=60 and (entry or 0)>=50:
        opp_type='Trend continuation'
    elif (recovery or 0)<45:
        opp_type='Wait for confirmation'
    else:
        opp_type='Selective / mixed'

    opp_sorted=sorted(((n,round(v)) for n,v,_ in opp_available),key=lambda x:x[1],reverse=True)
    weak_sorted=sorted(((n,round(v)) for n,v,_ in opp_available),key=lambda x:x[1])
    d['opportunityScore']={
        'version':4,'score':opp,'rawScore':opp_raw,'label':label,'signal':sig,'type':opp_type,
        'components':{n:round(v) if v is not None else None for n,v,_ in opp_components},
        'entryQualityComponents':{n:round(v) if v is not None else None for n,v,_ in entry_parts},
        'entryQualityVxnBonus':vxn_entry_bonus,
        'consolidationRiskContext':risk,
        'gates':opp_gates,
        'strongestDrivers':[f'{n} {v}' for n,v in opp_sorted[:2]],
        'weakestDrivers':[f'{n} {v}' for n,v in weak_sorted[:2]],
        'explanation':f"Long-entry quality is {label.lower()} ({opp}/100; {opp_type}). Raw weighted score {opp_raw}/100. Strongest inputs: "+', '.join(f'{n} {v}' for n,v in opp_sorted[:2])+'. Weakest: '+', '.join(f'{n} {v}' for n,v in weak_sorted[:2])+('. Active gate: '+opp_gates[-1]+'.' if opp_gates else '.'),
        'note':'This is an entry-quality score, not a forecast of the next session return. Strong internals can support the trend without making an extended price a good new entry.'
    }


    # ---------------- SOXL Buy Score v3.3 ----------------
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
    soxl_obs_date=str(soxl_obs.get('observationDate') or '')
    current_soxl_session=(now.weekday()<5 and soxl_obs_date==now.date().isoformat() and now.hour*60+now.minute>=9*60+30)
    if current_soxl_session and soxl_change is not None: soxl_path.append(soxl_change)
    soxl_giveback=(max(soxl_path)-soxl_change) if current_soxl_session and soxl_path and soxl_change is not None else None

    # 1) Semiconductor Trend v2 (30% of SOXL score).
    # Mix a persistent SOXX technical trend with current-session relative leadership
    # and breadth. This avoids double-counting the nested Semiconductor Leadership score.
    soxx_trend_ma=piecewise(soxx_ma20,[(-10,0),(-5,25),(0,50),(5,75),(10,100)]) if soxx_ma20 is not None else None
    soxx_r5=num(soxx_ctx.get('return5d'))
    soxx_trend_r5=piecewise(soxx_r5,[(-5,0),(-2.5,25),(0,50),(2.5,75),(5,100)]) if soxx_r5 is not None else None
    soxx_trend_rsi=piecewise(soxx_rsi,[
        (0,0),(35,0),(40,20),(45,35),(50,50),(55,65),(60,80),
        (65,90),(70,100),(80,100),(100,95)
    ]) if soxx_rsi is not None else None
    soxx_adx=num(soxx_ctx.get('adx14')); soxx_plus_di=num(soxx_ctx.get('plusDI14')); soxx_minus_di=num(soxx_ctx.get('minusDI14'))
    adx_strength=piecewise(soxx_adx,[(0,50),(15,50),(20,65),(25,80),(35,95),(45,100),(100,100)]) if soxx_adx is not None else None
    if adx_strength is not None and soxx_plus_di is not None and soxx_minus_di is not None:
        soxx_directional_adx=adx_strength if soxx_plus_di>=soxx_minus_di else 100-adx_strength
    else:
        soxx_directional_adx=None
    soxx_technical_parts=[
        ('SOXX vs 20DMA',soxx_trend_ma,0.30),
        ('SOXX 5D momentum',soxx_trend_r5,0.25),
        ('SOXX RSI14 trend',soxx_trend_rsi,0.25),
        ('SOXX ADX/DMI trend strength',soxx_directional_adx,0.20)
    ]
    soxx_technical_available=[x for x in soxx_technical_parts if x[1] is not None]
    soxx_technical_trend=(sum(v*w for _,v,w in soxx_technical_available)/sum(w for _,v,w in soxx_technical_available)
                          if soxx_technical_available else None)

    semi_breadth=num(((semi.get('breadth') or {}).get('score')))
    semi_trend_parts=[
        ('SOXX technical trend',soxx_technical_trend,0.30),
        ('SOX relative strength',scale(sox_rs,-1.5,1.5) if sox_rs is not None else None,0.25),
        ('SOXX relative strength',scale(soxx_rs,-1.5,1.5) if soxx_rs is not None else None,0.15),
        ('SMH relative strength',scale(smh_rs,-1.5,1.5) if smh_rs is not None else None,0.10),
        ('Semiconductor breadth',semi_breadth,0.20)
    ]
    semi_trend_available=[x for x in semi_trend_parts if x[1] is not None]
    semi_trend=(sum(v*w for _,v,w in semi_trend_available)/sum(w for _,v,w in semi_trend_available)
                if semi_trend_available else None)

    # 2) SOXL entry quality (25%). Reward a controlled pullback/normal extension,
    # not a falling knife and not a chase after an already extreme leveraged run.
    sx_ma20=num(soxl_ctx.get('ma20Distance')); sx_r5=num(soxl_ctx.get('return5d'))
    sx_rsi=num(soxl_ctx.get('rsi14')); sx_highdist=num(soxl_ctx.get('distanceFrom20dHighPct'))

    # SOXL Entry Quality v3. RSI is deliberately momentum-aware: a leveraged
    # semiconductor ETF can remain healthy at RSI 55-65, while RSI >75 increasingly
    # represents overheating. RSI remains 20% of Entry Quality; the separate
    # RSI x 20DMA penalty below handles only genuinely extreme combinations.
    ma_entry=clamp(85-8*max(sx_ma20 or 0,0)-5*max(-(sx_ma20 or 0),0)) if sx_ma20 is not None else None
    r5_entry=clamp(78-5*max((sx_r5 or 0)-4,0)-4*max(-(sx_r5 or 0)-3,0)) if sx_r5 is not None else None
    rsi_entry=piecewise(sx_rsi,[
        (0,20),(40,40),(45,55),(50,70),(55,85),(60,100),(65,95),
        (70,80),(75,60),(80,35),(85,10),(90,0),(100,0)
    ]) if sx_rsi is not None else None

    # Recent-high distance is regime-aware. When SOX/semiconductor leadership is
    # strong, a controlled SOXL pullback from a recent high is an improving entry
    # rather than a weakness signal. The reward peaks around a 12% pullback, then
    # falls as a deeper drawdown increasingly resembles breakdown/divergence.
    sox_ret=num((market.get('.SOX') or {}).get('changePct'))
    sox_strong=(semi_trend is not None and semi_trend>=70 and
                ((sox_ret is not None and sox_ret>0) or (sox_rs is not None and sox_rs>0)))
    if sx_highdist is not None and sox_strong:
        pullback=max(0,-sx_highdist)
        high_entry=piecewise(pullback,[
            (0,25),(2,40),(4,55),(6,70),(8,82),(10,90),(12,95),
            (15,75),(20,35),(25,10)
        ])
        high_entry=clamp(high_entry)
    else:
        # Without confirmed SOX strength, keep the conservative mean-reversion
        # profile: distance from the high is not automatically treated as a bargain.
        high_entry=clamp(82-5*abs(sx_highdist+4)) if sx_highdist is not None else None
    intraday_entry=clamp(100-25*soxl_giveback) if soxl_giveback is not None else None
    entry_parts=[
        ('20DMA distance',ma_entry,0.30),('5D return',r5_entry,0.20),('RSI14',rsi_entry,0.20),
        ('20D-high distance',high_entry,0.20),('Intraday giveback',intraday_entry,0.10)
    ]
    entry_available=[x for x in entry_parts if x[1] is not None]
    soxl_entry=(sum(v*w for _,v,w in entry_available)/sum(w for _,v,w in entry_available)) if entry_available else None

    # 3) Broader market confirmation (15%).
    market_confirmation=avg([
        internal,
        direction,
        signal100(row(d,'Market breadth').get('signal')),
        signal100(row(d,'Mega-cap leadership').get('signal'))
    ])

    # 4) Volatility / leverage risk (15%). Add SOXL's own realized-volatility
    # regime rather than relying only on market-level VXN. ATR% is displayed, while
    # the score uses relative ATR regime (60-session percentile + ATR14/ATR50 expansion)
    # so SOXL is judged against its own naturally high-volatility history.
    sx_atr_pct=num(soxl_ctx.get('atr14Pct'))
    sx_atr_percentile=num(soxl_ctx.get('atr14PctPercentile60'))
    sx_atr_ratio=num(soxl_ctx.get('atr14Vs50'))
    sx_atr_percentile_safety=clamp(100-sx_atr_percentile) if sx_atr_percentile is not None else None
    sx_atr_expansion_safety=piecewise(sx_atr_ratio,[
        (0,100),(0.8,100),(1.0,80),(1.2,55),(1.5,25),(1.8,0),(3.0,0)
    ]) if sx_atr_ratio is not None else None
    sx_atr_regime_safety=avg([sx_atr_percentile_safety,sx_atr_expansion_safety])
    leverage_parts=[
        ('Consolidation safety',100-risk,0.35),
        ('VXN condition',signal100(row(d,'Nasdaq volatility (VXN / VIX)').get('signal')),0.25),
        ('VXN daily change',clamp(50-(vxn_ch or 0)*6) if vxn_ch is not None else None,0.15),
        ('SOXL ATR regime',sx_atr_regime_safety,0.25)
    ]
    leverage_available=[x for x in leverage_parts if x[1] is not None]
    leverage_risk=(sum(v*w for _,v,w in leverage_available)/sum(w for _,v,w in leverage_available)
                   if leverage_available else None)

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
    soxl_raw=round(sum(v*w for _,v,w in sx_available)/sum(w for _,v,w in sx_available)) if sx_available else 50

    # Continuous extension treatment replaces v2's 8/12/18% hard cliffs.
    # The penalty rises smoothly with distance above the 20DMA. Strong confirmed
    # semiconductor regimes can reduce (never reverse) this extension penalty.
    base_extension_penalty=piecewise(sx_ma20,[
        (-100,0),(8,0),(12,4),(18,12),(24,24),(30,35),(100,35)
    ]) if sx_ma20 is not None else 0
    if semi_trend is not None and semi_trend>=85 and market_confirmation is not None and market_confirmation>=60:
        extension_regime_multiplier=0.65
        extension_regime='Strong semiconductor trend + market confirmation'
    elif semi_trend is not None and semi_trend>=75:
        extension_regime_multiplier=0.80
        extension_regime='Strong semiconductor trend'
    else:
        extension_regime_multiplier=1.00
        extension_regime='No extension relief'
    extension_penalty=base_extension_penalty*extension_regime_multiplier

    # RSI x 20DMA overheating penalty. This is intentionally NOT granted the full
    # semiconductor-regime relief: strong SOX can justify trend extension, but it
    # does not make an RSI in the mid/high-80s harmless for a daily 3x ETF.
    rsi_heat_penalty=piecewise(sx_rsi,[
        (0,0),(75,0),(80,10),(85,20),(90,30),(100,30)
    ]) if sx_rsi is not None else 0
    extension_amplifier=piecewise(sx_ma20,[
        (-100,0.25),(8,0.25),(15,0.50),(20,0.80),(25,1.00),(100,1.00)
    ]) if sx_ma20 is not None else 0.25
    extreme_extension_penalty=rsi_heat_penalty*extension_amplifier

    soxl_pre_gate=max(0,round(soxl_raw-extension_penalty-extreme_extension_penalty))
    soxl_score=soxl_pre_gate
    gates=[]

    # Keep genuine regime/event vetoes. Price extension itself is no longer a hard
    # gate; it is represented by the continuous penalties above.
    if semi_trend is not None and semi_trend<40:
        soxl_score=min(soxl_score,45); gates.append('Weak semiconductor trend caps score at 45')
    rs_vals=[x for x in (sox_rs,soxx_rs,smh_rs) if x is not None]
    if len(rs_vals)>=2 and all(x<0 for x in rs_vals):
        soxl_score=min(soxl_score,50); gates.append('Broad semiconductor underperformance caps score at 50')
    if risk>=75:
        soxl_score=min(soxl_score,45); gates.append('High consolidation risk caps score at 45')
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

    # Snapshot-friendly indicator interpretations. Keep the raw value, plain-English
    # meaning and the exact subscore together so later validation can test not only
    # the overall SOXL score but whether RSI/ATR interpretation itself was useful.
    if sx_rsi is None:
        sx_rsi_meaning='Unavailable'
    elif sx_rsi>=80:
        sx_rsi_meaning='Overheated'
    elif sx_rsi>=70:
        sx_rsi_meaning='Strong / Extended'
    elif sx_rsi>=55:
        sx_rsi_meaning='Healthy Bullish Momentum'
    elif sx_rsi>=45:
        sx_rsi_meaning='Neutral'
    elif sx_rsi>=35:
        sx_rsi_meaning='Weak Momentum'
    else:
        sx_rsi_meaning='Oversold / Weak'

    sx_stoch_k=num(soxl_ctx.get('stochK9'))
    sx_stoch_d=num(soxl_ctx.get('stochD6'))
    if sx_stoch_k is None:
        sx_stoch_meaning='Unavailable'
    else:
        if sx_stoch_k>=80:
            sx_stoch_zone='Overbought'
        elif sx_stoch_k<=20:
            sx_stoch_zone='Oversold'
        else:
            sx_stoch_zone='Neutral'
        if sx_stoch_d is None:
            sx_stoch_momentum='signal unavailable'
        elif sx_stoch_k>=sx_stoch_d+2:
            sx_stoch_momentum='bullish momentum'
        elif sx_stoch_k<=sx_stoch_d-2:
            sx_stoch_momentum='bearish momentum'
        else:
            sx_stoch_momentum='flat momentum'
        sx_stoch_meaning=f'{sx_stoch_zone} · {sx_stoch_momentum}'

    if sx_atr_pct is None:
        sx_atr_meaning='Unavailable'
    elif (sx_atr_ratio is not None and sx_atr_ratio>=1.20) or (sx_atr_percentile is not None and sx_atr_percentile>=75):
        sx_atr_meaning='Expanding / High Leverage Risk'
    elif (sx_atr_ratio is not None and sx_atr_ratio<=0.95) and (sx_atr_percentile is not None and sx_atr_percentile<=35):
        sx_atr_meaning='Contracting / Favorable'
    elif (sx_atr_ratio is not None and sx_atr_ratio>1.05) or (sx_atr_percentile is not None and sx_atr_percentile>=55):
        sx_atr_meaning='Elevated'
    else:
        sx_atr_meaning='Normal'

    sx_sorted=sorted(((n,round(v)) for n,v,_ in sx_available),key=lambda x:x[1],reverse=True)
    sx_weak=sorted(((n,round(v)) for n,v,_ in sx_available),key=lambda x:x[1])
    d['soxlBuyScore']={
        'version':3.3,'score':soxl_score,'rawScore':soxl_raw,'preGateScore':soxl_pre_gate,
        'label':sx_label,'signal':sx_sig,'horizon':'1–5 sessions',
        'instrument':'SOXL','last':soxl_last,'changePct':soxl_change,
        'components':{n:round(v) if v is not None else None for n,v,_ in sx_components},
        'semiconductorTrend':{
            'version':2.1,
            'score':round(semi_trend) if semi_trend is not None else None,
            'components':{n:round(v) if v is not None else None for n,v,_ in semi_trend_parts},
            'weights':{n:int(w*100) for n,_,w in semi_trend_parts},
            'availableWeightPct':round(100*sum(w for _,v,w in semi_trend_available)),
            'soxxTechnicalTrend':{
                'score':round(soxx_technical_trend) if soxx_technical_trend is not None else None,
                'components':{n:round(v) if v is not None else None for n,v,_ in soxx_technical_parts},
                'weights':{n:int(w*100) for n,_,w in soxx_technical_parts},
                'context':{
                    'ma20DistancePct':round(soxx_ma20,2) if soxx_ma20 is not None else None,
                    'return5dPct':round(soxx_r5,2) if soxx_r5 is not None else None,
                    'rsi14':round(soxx_rsi,1) if soxx_rsi is not None else None,
                    'adx14':round(soxx_adx,1) if soxx_adx is not None else None,
                    'plusDI14':round(soxx_plus_di,1) if soxx_plus_di is not None else None,
                    'minusDI14':round(soxx_minus_di,1) if soxx_minus_di is not None else None
                }
            }
        },
        'gates':gates,'intradayGivebackPp':round(soxl_giveback,2) if soxl_giveback is not None else None,
        'indicatorSnapshot':{
            'RSI14':{
                'value':round(sx_rsi,1) if sx_rsi is not None else None,
                'meaning':sx_rsi_meaning,
                'entryScore':round(rsi_entry) if rsi_entry is not None else None,
                'role':'SOXL entry-quality momentum / overheating input'
            },
            'STOCH96':{
                'k':round(sx_stoch_k,1) if sx_stoch_k is not None else None,
                'd':round(sx_stoch_d,1) if sx_stoch_d is not None else None,
                'meaning':sx_stoch_meaning,
                'scored':False,
                'role':'Observational SOXL momentum / overbought-oversold context only'
            },
            'ATR14':{
                'valuePct':round(sx_atr_pct,2) if sx_atr_pct is not None else None,
                'meaning':sx_atr_meaning,
                'regimeSafetyScore':round(sx_atr_regime_safety) if sx_atr_regime_safety is not None else None,
                'percentile60':round(sx_atr_percentile,1) if sx_atr_percentile is not None else None,
                'atr14Vs50':round(sx_atr_ratio,2) if sx_atr_ratio is not None else None,
                'role':'SOXL realized-volatility / leverage-risk input'
            }
        },
        'volatilityLeverageRisk':{
            'score':round(leverage_risk) if leverage_risk is not None else None,
            'components':{n:round(v) if v is not None else None for n,v,_ in leverage_parts},
            'weights':{n:int(w*100) for n,_,w in leverage_parts},
            'soxlAtr':{
                'atr14Pct':round(sx_atr_pct,2) if sx_atr_pct is not None else None,
                'atr14PctPercentile60':round(sx_atr_percentile,1) if sx_atr_percentile is not None else None,
                'atr14Vs50':round(sx_atr_ratio,2) if sx_atr_ratio is not None else None,
                'regimeSafetyScore':round(sx_atr_regime_safety) if sx_atr_regime_safety is not None else None
            }
        },
        'entryQuality':{
            'score':round(soxl_entry) if soxl_entry is not None else None,
            'factorScores':{n:round(v) if v is not None else None for n,v,_ in entry_parts},
            'factorWeights':{n:int(w*100) for n,_,w in entry_parts},
            'availableWeightPct':round(100*sum(w for _,v,w in entry_available)),
            'method':'Weighted available factors; RSI uses a momentum-aware nonlinear curve. Intraday giveback is excluded when there is no current-session SOXL observation.'
        },
        'extensionAdjustment':{
            'base20dMaPenalty':round(base_extension_penalty,1),
            'regimeMultiplier':extension_regime_multiplier,
            'regime':extension_regime,
            'applied20dMaPenalty':round(extension_penalty,1),
            'rsiHeatPenalty':round(rsi_heat_penalty,1),
            'rsiExtensionAmplifier':round(extension_amplifier,2),
            'extremeRsi20dMaPenalty':round(extreme_extension_penalty,1),
            'totalPenalty':round(extension_penalty+extreme_extension_penalty,1)
        },
        'technicalContext':{
            'ma20DistancePct':round(sx_ma20,2) if sx_ma20 is not None else None,
            'return5dPct':round(sx_r5,2) if sx_r5 is not None else None,
            'rsi14':round(sx_rsi,1) if sx_rsi is not None else None,
            'distanceFrom20dHighPct':round(sx_highdist,2) if sx_highdist is not None else None
        },
        'strongestDrivers':[f'{n} {v}' for n,v in sx_sorted[:2]],
        'weakestDrivers':[f'{n} {v}' for n,v in sx_weak[:2]],
        'explanation':f"SOXL tactical entry quality is {sx_label.lower()} ({soxl_score}/100) for a 1–5 session horizon. "
                      +f"Raw score {soxl_raw}; extension/overheating penalty {round(extension_penalty+extreme_extension_penalty,1)}. "
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

    # refresh.py appends the intraday snapshot before this refinement pass. Enrich the
    # newest same-day snapshot with the final SOXL score so every refresh is backtestable.
    intraday_path=INTRADAY/f'{now:%Y-%m}.json'
    intraday_doc=load(intraday_path,{'schemaVersion':4,'snapshots':[]})
    snaps=intraday_doc.get('snapshots') or []
    if snaps:
        latest=snaps[-1]
        try:
            latest_ts=dt.datetime.fromisoformat(str(latest.get('timestampET'))).astimezone(NY)
        except (TypeError,ValueError):
            latest_ts=None
        if latest_ts is not None and latest_ts.date()==now.date():
            latest['soxlBuyScore']=d['soxlBuyScore']
            if isinstance(latest.get('validation'),dict):
                latest['validation'].setdefault('modelState',{})['soxlBuyScore']=d['soxlBuyScore']
            intraday_path.write_text(json.dumps(intraday_doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    print(f'v3 scores: Nasdaq {d.get("nasdaqScore",{}).get("score"):+} | Consolidation {risk} ({risk_level}) | Opportunity {opp} ({label}) | SOXL Buy {soxl_score} ({sx_label})')

if __name__=='__main__': main()
