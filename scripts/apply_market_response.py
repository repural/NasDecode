#!/usr/bin/env python3
"""Apply a bounded Market Response modifier to Nasdaq Score.

The directional model still owns the raw score. This layer only attenuates a
Rates / Macro tailwind or headwind when live price action persistently shows
that the market is responding differently from the macro impulse.

Two symmetric states are supported:
- constraint_absorption: negative macro pressure is being absorbed by strong internals.
- support_rejection: positive macro support is failing to produce healthy internals.

The modifier never flips the sign of the Rates / Macro bucket and is capped at
50% attenuation. It must persist for 15 minutes before affecting Nasdaq Score.
"""
import datetime as dt
import json, re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DASH=ROOT/'data'/'dashboard.json'
DAILY=ROOT/'data'/'history'/'daily.json'
INTRADAY=ROOT/'data'/'history'/'intraday'
NY=ZoneInfo('America/New_York')
PERSIST_MINUTES=15
MAX_ATTENUATION=0.50
EVIDENCE_TRIGGER=0.60
MACRO_TRIGGER=0.15


def load(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError): return default

def num(v):
    try: return float(v)
    except (TypeError,ValueError): return None

def clamp(v,lo=0.0,hi=1.0):
    return max(lo,min(hi,float(v)))

def scale(v,lo,hi):
    if v is None: return None
    if hi==lo: return 0.0
    return clamp((float(v)-lo)/(hi-lo))

def parse(text,pat):
    m=re.search(pat,str(text or ''),re.I)
    return float(m.group(1)) if m else None

def row(d,name):
    return next((x for x in d.get('rows',[]) if x.get('factor')==name),{})

def weighted(parts):
    usable=[(v,w) for v,w in parts if v is not None]
    if not usable: return None
    den=sum(w for _,w in usable)
    return sum(v*w for v,w in usable)/den if den else None

def label_score(s):
    if s>=45:return 'positive','Strong Positive'
    if s>=15:return 'positive','Cautiously Positive'
    if s>-15:return 'mixed','Mixed / Neutral'
    if s>-45:return 'negative','Cautiously Negative'
    return 'negative','Strong Negative'

def iso_age_minutes(value,now):
    try:
        t=dt.datetime.fromisoformat(str(value))
        if t.tzinfo is None: t=t.replace(tzinfo=NY)
        return max(0.0,(now-t.astimezone(NY)).total_seconds()/60.0)
    except (TypeError,ValueError):
        return 0.0

def evidence(d,rec):
    market=rec.get('market') or {}
    ix_ret=num((market.get('.IXIC') or {}).get('changePct'))
    vxn_ch=num((market.get('.VXN') or {}).get('changePct'))

    semi=((d.get('confirmationLayer') or {}).get('semiconductorLeadership') or {})
    rs=semi.get('relativeStrengthPp') or {}
    sox_rel=num(rs.get('soxVsNasdaqPp'))
    semi_breadth=num((semi.get('breadth') or {}).get('outperformingQqqPct'))

    breadth=parse(row(d,'Market breadth').get('latest'),r'advancing\s*\(([0-9.]+)%\)')
    mega_rel=parse(row(d,'Mega-cap leadership').get('latest'),r'(?:relative|basket vs QQQ)\s*([+-]?[0-9.]+)\s*pp')

    positive={
        'Nasdaq resilience':scale(ix_ret,0.20,1.50),
        'SOX relative strength':scale(sox_rel,0.0,1.50),
        'Market breadth':scale(breadth,50.0,70.0),
        'Falling VXN':scale(-vxn_ch if vxn_ch is not None else None,0.0,5.0),
        'Mega-cap leadership':scale(mega_rel,0.0,0.75),
        'Semiconductor breadth':scale(semi_breadth,50.0,75.0),
    }
    negative={
        'Nasdaq rejection':scale(-ix_ret if ix_ret is not None else None,0.20,1.50),
        'SOX relative weakness':scale(-sox_rel if sox_rel is not None else None,0.0,1.50),
        'Weak market breadth':scale(100.0-breadth if breadth is not None else None,50.0,70.0),
        'Rising VXN':scale(vxn_ch,0.0,5.0),
        'Mega-cap weakness':scale(-mega_rel if mega_rel is not None else None,0.0,0.75),
        'Weak semiconductor breadth':scale(100.0-semi_breadth if semi_breadth is not None else None,50.0,75.0),
    }
    weights={
        'Nasdaq resilience':.25,'SOX relative strength':.20,'Market breadth':.15,
        'Falling VXN':.15,'Mega-cap leadership':.10,'Semiconductor breadth':.15,
        'Nasdaq rejection':.25,'SOX relative weakness':.20,'Weak market breadth':.15,
        'Rising VXN':.15,'Mega-cap weakness':.10,'Weak semiconductor breadth':.15,
    }
    pos=weighted([(v,weights[k]) for k,v in positive.items()])
    neg=weighted([(v,weights[k]) for k,v in negative.items()])
    return pos,neg,positive,negative

def sync_history(now,d,mr):
    daily=load(DAILY,{'schemaVersion':4,'records':{}})
    rec=(daily.get('records') or {}).get(now.date().isoformat())
    if isinstance(rec,dict):
        rec['nasdaqScore']={k:v for k,v in (d.get('nasdaqScore') or {}).items() if k!='model'}
        rec['marketResponse']=mr
        if isinstance(rec.get('validation'),dict):
            ms=rec['validation'].setdefault('modelState',{})
            ms['nasdaqScore']=rec['nasdaqScore']
            ms['marketResponse']=mr
        if isinstance(rec.get('closeSnapshot'),dict):
            rec['closeSnapshot']['nasdaqScore']=rec['nasdaqScore']
            rec['closeSnapshot']['marketResponse']=mr
        DAILY.write_text(json.dumps(daily,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    path=INTRADAY/f'{now:%Y-%m}.json'
    intra=load(path,{'schemaVersion':4,'snapshots':[]})
    snaps=intra.get('snapshots') or []
    if snaps:
        last=snaps[-1]
        try: ts=dt.datetime.fromisoformat(str(last.get('timestampET'))).astimezone(NY)
        except (TypeError,ValueError): ts=None
        if ts and ts.date()==now.date():
            last['nasdaqScore']={k:v for k,v in (d.get('nasdaqScore') or {}).items() if k!='model'}
            last['marketResponse']=mr
            if isinstance(last.get('validation'),dict):
                ms=last['validation'].setdefault('modelState',{})
                ms['nasdaqScore']=last['nasdaqScore']; ms['marketResponse']=mr
            path.write_text(json.dumps(intra,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    d=load(DASH,{})
    ns=d.get('nasdaqScore') or {}
    model=ns.get('model') or {}
    buckets=model.get('buckets') or []
    rates=next((x for x in buckets if x.get('bucket')=='Rates / Macro'),None)
    raw_score=num(ns.get('rawScore'))
    raw_macro=num((rates or {}).get('strength'))
    now=dt.datetime.now(NY)
    mins=now.hour*60+now.minute
    in_window=now.weekday()<5 and 9*60+30<=mins<=16*60+45

    daily=load(DAILY,{'records':{}})
    rec=(daily.get('records') or {}).get(now.date().isoformat(),{})
    pos,neg,pos_parts,neg_parts=evidence(d,rec) if isinstance(rec,dict) else (None,None,{},{})

    mode=None; ev=None
    if in_window and raw_macro is not None:
        if raw_macro<=-MACRO_TRIGGER and pos is not None and pos>=EVIDENCE_TRIGGER:
            mode='constraint_absorption'; ev=pos
        elif raw_macro>=MACRO_TRIGGER and neg is not None and neg>=EVIDENCE_TRIGGER:
            mode='support_rejection'; ev=neg

    prior=d.get('marketResponse') or {}
    prior_mode=prior.get('candidateMode')
    prior_since=prior.get('candidateSince')
    prior_observed=prior.get('observedAt')
    # Persistence must be continuous within the same trading day. A stale Friday
    # candidate must never make Monday's first observation immediately active.
    prior_gap=iso_age_minutes(prior_observed,now) if prior_observed else 999.0
    try:
        prior_day=dt.datetime.fromisoformat(str(prior_since)).astimezone(NY).date() if prior_since else None
    except (TypeError,ValueError):
        prior_day=None
    continuous=(prior_mode==mode and prior_since and prior_day==now.date() and prior_gap<=12.0)
    if mode:
        candidate_since=prior_since if continuous else now.isoformat()
        persistent_minutes=iso_age_minutes(candidate_since,now)
    else:
        candidate_since=None; persistent_minutes=0.0

    active=bool(mode and persistent_minutes>=PERSIST_MINUTES)
    attenuation=0.0
    if active and ev is not None:
        # Once persistent, begin with modest attenuation and scale with evidence.
        attenuation=min(MAX_ATTENUATION,0.25+0.25*clamp((ev-EVIDENCE_TRIGGER)/(1.0-EVIDENCE_TRIGGER)))

    effective_macro=raw_macro
    effective_score=raw_score
    if active and raw_macro is not None and raw_score is not None and rates:
        effective_macro=raw_macro*(1.0-attenuation)
        num_total=0.0; den_total=0.0
        for b in buckets:
            w=num(b.get('weight')); s=num(b.get('strength'))
            if w is None or s is None: continue
            if b.get('bucket')=='Rates / Macro': s=effective_macro
            num_total+=s*w; den_total+=w
        if den_total:
            effective_score=round(100*num_total/den_total)

    if rates:
        rates['rawStrength']=round(raw_macro,3) if raw_macro is not None else None
        rates['effectiveStrength']=round(effective_macro,3) if effective_macro is not None else None
        rates['marketResponseAttenuationPct']=round(attenuation*100,1)

    if effective_score is not None:
        sig,label=label_score(effective_score)
        prev=num(ns.get('previousScore'))
        trend='Improving ↑' if prev is not None and effective_score>prev else ('Deteriorating ↓' if prev is not None and effective_score<prev else 'Stable →')
        ns['effectiveScore']=effective_score
        ns['score']=effective_score
        ns['signal']=sig; ns['label']=label; ns['trend']=trend
        model['version']=3
        ns['model']=model
        d['nasdaqScore']=ns

    status='active' if active else ('confirming' if mode else 'inactive')
    if mode=='constraint_absorption':
        summary='Rates headwind partially absorbed by strong market internals.' if active else 'Strong internals are testing whether the rates headwind is being absorbed.'
    elif mode=='support_rejection':
        summary='Rates support partially discounted because market internals are failing to confirm.' if active else 'Weak internals are testing whether supportive rates are being rejected.'
    else:
        summary='No persistent divergence between the macro impulse and live market response.'

    mr={
        'version':1,'status':status,'mode':mode,'summary':summary,'observedAt':now.isoformat(),
        'candidateMode':mode,'candidateSince':candidate_since,
        'persistenceMinutes':round(persistent_minutes,1),'requiredPersistenceMinutes':PERSIST_MINUTES,
        'evidenceScore':round(ev*100) if ev is not None else None,
        'positiveResponseScore':round(pos*100) if pos is not None else None,
        'negativeResponseScore':round(neg*100) if neg is not None else None,
        'attenuationPct':round(attenuation*100,1),
        'rawRatesMacroStrength':round(raw_macro,3) if raw_macro is not None else None,
        'effectiveRatesMacroStrength':round(effective_macro,3) if effective_macro is not None else None,
        'rawNasdaqScore':round(raw_score) if raw_score is not None else None,
        'effectiveNasdaqScore':round(effective_score) if effective_score is not None else None,
        'components':pos_parts if mode=='constraint_absorption' else (neg_parts if mode=='support_rejection' else {}),
        'note':'Market Response only attenuates an existing Rates / Macro contribution; it never reverses its sign.'
    }
    d['marketResponse']=mr
    layer=d.setdefault('confirmationLayer',{})
    layer['marketResponseApplied']=active
    layer['directionalScoreUnchanged']=not active
    macro_constraint=layer.setdefault('macroConstraint',{})
    macro_constraint['ratesMacroBucketStrength']=round(raw_macro,3) if raw_macro is not None else None
    macro_constraint['effectiveRatesMacroBucketStrength']=round(effective_macro,3) if effective_macro is not None else None
    macro_constraint['marketResponseAttenuationPct']=round(attenuation*100,1)
    DASH.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    sync_history(now,d,mr)
    print(f"Market Response: {status} {mode or 'none'} · evidence {mr['evidenceScore']} · attenuation {mr['attenuationPct']}% · Nasdaq {mr['rawNasdaqScore']} -> {mr['effectiveNasdaqScore']}")

if __name__=='__main__':
    main()
