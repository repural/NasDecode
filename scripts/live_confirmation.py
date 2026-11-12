#!/usr/bin/env python3
"""Replace stale previous-close semiconductor confirmation with live session evidence.

The main refresh intentionally leaves sessionLevels close-to-close returns empty until the
cash session is complete. That is correct for historical close storage, but it previously
caused the independent confirmation layer to fall back to the prior session intraday.
This post-pass uses current CNBC percentage moves during 09:30-16:00 ET once enough live
coverage exists, while leaving the directional Nasdaq Score untouched.
"""

import datetime
import json
import os
from zoneinfo import ZoneInfo

from refresh import CNBC_BASE, SEMI_BREADTH, cnbc_quotes, is_intraday, num, pct

ROOT=os.path.dirname(os.path.dirname(__file__))
DASHBOARD=os.path.join(ROOT,'data','dashboard.json')
DAILY=os.path.join(ROOT,'data','history','daily.json')
INTRADAY_DIR=os.path.join(ROOT,'data','history','intraday')
NY=ZoneInfo('America/New_York')
CORE=['.IXIC','QQQ','.SOX','SOX','SOXX','SMH']


def signal100(rows,name):
    row=next((x for x in rows if x.get('factor')==name),{})
    sig=row.get('signal')
    return 100 if sig=='positive' else (0 if sig=='negative' else 50)


def rs_score(v):
    if v is None: return 50
    if v>=0.50: return 100
    if v>=0.20: return 75
    if v>-0.20: return 50
    if v>-0.50: return 25
    return 0


def label(score):
    return 'Strong' if score>=75 else ('Positive' if score>=60 else ('Mixed' if score>=40 else 'Weak'))


def current_quotes(now):
    symbols=list(dict.fromkeys(CORE+SEMI_BREADTH))
    q=cnbc_quotes(symbols)
    live={s:v for s,v in q.items() if is_intraday(v,now) and pct(v) is not None}
    return q,live


def compute(now):
    q,live=current_quotes(now)
    nasdaq=pct(live.get('.IXIC',{})) if '.IXIC' in live else None
    qqq=pct(live.get('QQQ',{})) if 'QQQ' in live else None
    sox_sym='.SOX' if '.SOX' in live else ('SOX' if 'SOX' in live else None)
    sox=pct(live.get(sox_sym,{})) if sox_sym else None
    soxx=pct(live.get('SOXX',{})) if 'SOXX' in live else None
    smh=pct(live.get('SMH',{})) if 'SMH' in live else None
    members={s:pct(live[s]) for s in SEMI_BREADTH if s in live and pct(live[s]) is not None}

    # Require genuine same-session coverage before replacing prior-close confirmation.
    # Core indexes must be live and at least one-third of the 30-member SOX universe
    # must have same-session quotes. This avoids switching on a sparse/partial feed.
    if None in (nasdaq,qqq,sox,soxx,smh) or len(members)<10:
        return None

    outperform=sum(1 for v in members.values() if v>qqq)
    positive=sum(1 for v in members.values() if v>0)
    breadth_pct=100*outperform/len(members)
    if breadth_pct>=70: breadth_score=100
    elif breadth_pct>=55: breadth_score=75
    elif breadth_pct>=45: breadth_score=50
    elif breadth_pct>=30: breadth_score=25
    else: breadth_score=0

    sox_rs=sox-nasdaq
    soxx_rs=soxx-nasdaq
    smh_rs=smh-nasdaq
    # SOX is the primary leadership signal. SOXX/SMH and the full SOX-member
    # breadth universe confirm it; the former five-stock basket is excluded.
    score=round(.55*rs_score(sox_rs)+.15*rs_score(soxx_rs)+.10*rs_score(smh_rs)+.20*breadth_score)
    broad=bool(sox_rs>=0.50 and soxx_rs>0 and smh_rs>0)
    if broad: score=max(75,score)

    return {
        'score':score,
        'label':label(score),
        'broadLeadershipTrigger':broad,
        'relativeStrengthPp':{
            'soxVsNasdaqPp':round(sox_rs,4),
            'soxxVsNasdaqPp':round(soxx_rs,4),
            'smhVsNasdaqPp':round(smh_rs,4),
            'smhVsQqqPp':round(smh-qqq,4),
            'basis':'current_session',
            'observationDate':now.date().isoformat()
        },
        'breadth':{
            'universeSize':len(SEMI_BREADTH),
            'available':len(members),
            'positive':positive,
            'outperformingQqq':outperform,
            'outperformingQqqPct':round(breadth_pct,1),
            'score':breadth_score
        },
        'weights':{'SOX':55,'SOXX':15,'SMH':10,'semiconductorBreadth':20},
        'sessionReturnsPct':{'SOX':round(sox,4),'Nasdaq':round(nasdaq,4),'SOXX':round(soxx,4),'SMH':round(smh,4)},
        'basis':'current_session',
        'observationDate':now.date().isoformat(),
        'liveCoverage':{'core':5,'soxMembers':len(members),'minimumSoxMembers':10}
    }


def apply_confirmation(d,semi):
    rows=d.get('rows',[])
    layer=d.setdefault('confirmationLayer',{})
    old=layer.get('semiconductorLeadership',{})
    # Preserve non-price catalyst context and acceleration metadata from the main model.
    for key in ('catalystMomentum','accelerationFromOpenPoints'):
        if key in old and key not in semi: semi[key]=old[key]
    layer['semiconductorLeadership']=semi

    # Keep the visible scorecard row aligned with the SOX-first confirmation layer.
    sr=semi.get('sessionReturnsPct',{})
    rs=semi.get('relativeStrengthPp',{})
    sox_rel=rs.get('soxVsNasdaqPp'); soxx_rel=rs.get('soxxVsNasdaqPp'); smh_rel=rs.get('smhVsNasdaqPp')
    row=next((x for x in rows if x.get('factor')=='Semiconductor leadership'),None)
    if row is not None and sox_rel is not None:
        if sox_rel>0.25 and (soxx_rel or 0)>=-0.20 and (smh_rel or 0)>=-0.20:
            sig='positive'; direction='Confirmed leadership' if ((soxx_rel or 0)>0.20 or (smh_rel or 0)>0.20) else 'SOX leading Nasdaq'
        elif sox_rel<-0.25 and (soxx_rel or 0)<=0.20 and (smh_rel or 0)<=0.20:
            sig='negative'; direction='Confirmed weakness' if ((soxx_rel or 0)<-0.20 or (smh_rel or 0)<-0.20) else 'SOX lagging Nasdaq'
        else:
            sig='mixed'; direction='Mixed confirmation'
        row['latest']=(f"Live · SOX {sr.get('SOX',0):+.2f}% | Nasdaq {sr.get('Nasdaq',0):+.2f}% | "
                       f"SOX vs Nasdaq {sox_rel:+.2f} pp | SOXX vs Nasdaq {soxx_rel:+.2f} pp | "
                       f"SMH vs Nasdaq {smh_rel:+.2f} pp")
        row['signal']=sig; row['direction']=direction
        row['freshness']='Live CNBC quote'
        row['source']='CNBC quotes; SOX relative strength vs Nasdaq is primary, confirmed by SOXX/SMH and broad SOX-member participation'
        row['explanation']=(row['latest']+'. SOX is the primary semiconductor leadership reference; '
                            'SOXX, SMH and full-universe semiconductor breadth are confirmation layers.')

    breadth=signal100(rows,'Market breadth')
    vol=signal100(rows,'Nasdaq volatility (VXN / VIX)')
    mega=signal100(rows,'Mega-cap leadership')
    internal=round(.35*breadth+.35*semi['score']+.20*vol+.10*mega)
    layer['internalConfirmation']={
        'score':internal,
        'label':'Positive' if internal>=60 else ('Mixed' if internal>=40 else 'Weak'),
        'components':{'breadth':breadth,'semiconductorLeadership':semi['score'],'volatility':vol,'megaCapLeadership':mega},
        'weights':{'breadth':35,'semiconductorLeadership':35,'volatility':20,'megaCapLeadership':10}
    }
    layer['directionalScoreUnchanged']=True
    return layer


def update_history(now,layer):
    day=now.date().isoformat()
    try:
        with open(DAILY,encoding='utf-8') as f: daily=json.load(f)
        rec=daily.get('records',{}).get(day)
        if isinstance(rec,dict):
            rec['confirmationLayer']=layer
            if isinstance(rec.get('validation'),dict):
                rec['validation'].setdefault('modelState',{})['confirmationLayer']=layer
                rec['validation']['relativeStrengthPp']=layer['semiconductorLeadership'].get('relativeStrengthPp',{})
            with open(DAILY,'w',encoding='utf-8') as f: json.dump(daily,f,ensure_ascii=False,indent=2)
    except (OSError,json.JSONDecodeError):
        pass

    path=os.path.join(INTRADAY_DIR,now.strftime('%Y-%m')+'.json')
    try:
        with open(path,encoding='utf-8') as f: intraday=json.load(f)
        snaps=intraday.get('snapshots',[])
        if snaps:
            last=snaps[-1]
            try:
                ts=datetime.datetime.fromisoformat(str(last.get('timestampET',''))).astimezone(NY)
            except (TypeError,ValueError): ts=None
            if ts and ts.date()==now.date():
                last['confirmationLayer']=layer
                if isinstance(last.get('validation'),dict):
                    last['validation'].setdefault('modelState',{})['confirmationLayer']=layer
                    last['validation']['relativeStrengthPp']=layer['semiconductorLeadership'].get('relativeStrengthPp',{})
                with open(path,'w',encoding='utf-8') as f: json.dump(intraday,f,ensure_ascii=False,indent=2)
    except (OSError,json.JSONDecodeError):
        pass


def main():
    now=datetime.datetime.now(NY)
    mins=now.hour*60+now.minute
    if now.weekday()>=5 or not (9*60+30<=mins<16*60):
        print('Live confirmation: outside regular session; leaving main model basis unchanged')
        return
    semi=compute(now)
    if not semi:
        print('Live confirmation: insufficient same-session coverage; retaining previous basis')
        return
    with open(DASHBOARD,encoding='utf-8') as f: d=json.load(f)
    layer=apply_confirmation(d,semi)
    with open(DASHBOARD,'w',encoding='utf-8') as f: json.dump(d,f,ensure_ascii=False,indent=2)
    update_history(now,layer)
    print(f"Live confirmation: {semi['score']} {semi['label']} · {semi['breadth']['available']}/{len(SEMI_BREADTH)} SOX members · current_session")

if __name__=='__main__':
    main()
