#!/usr/bin/env python3
"""Capture named intraday NasDecode analysis checkpoints.

The workflow sets NASDECODE_ANALYSIS_STAGE only for the scheduled U.S. cash-session
checkpoints. This script snapshots the already-refined dashboard state and stores a
compact deterministic narrative for later validation; it performs no external fetches.
"""
import datetime as dt
import json, os, re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DASH=ROOT/'data'/'dashboard.json'
DAILY=ROOT/'data'/'history'/'daily.json'
OUT=ROOT/'data'/'history'/'session-analyses.json'
NY=ZoneInfo('America/New_York')

STAGES={
    'early_market':('Early Market Analysis','10:30 ET'),
    'mid_market':('Mid-Market Analysis','13:00 ET'),
    'near_close':('Near-Close Analysis','15:30 ET'),
}
ORDER=['early_market','mid_market','near_close']


def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError):return default

def num(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def row(d,name):return next((x for x in d.get('rows',[]) if x.get('factor')==name),{})
def parse(text,pat):
    m=re.search(pat,str(text or ''),re.I)
    return float(m.group(1)) if m else None

def fmt_pct(v):return 'unavailable' if v is None else f'{v:+.2f}%'
def fmt_score(v):return 'unavailable' if v is None else f'{v:+.0f}/100'


def main():
    stage=os.environ.get('NASDECODE_ANALYSIS_STAGE','').strip()
    if stage not in STAGES:
        print('No scheduled session-analysis stage; skipping capture.')
        return

    d=load(DASH,{})
    daily=load(DAILY,{'records':{}})
    store=load(OUT,{'schemaVersion':1,'records':{}})
    now=dt.datetime.now(NY)
    day=now.date().isoformat()
    if now.weekday()>=5:
        print('Weekend: no session checkpoint.');return
    rec=(daily.get('records') or {}).get(day,{})
    market=rec.get('market') or {}
    mc=((rec.get('validation') or {}).get('marketContext') or {})

    ns=d.get('nasdaqScore') or {}
    risk=d.get('consolidationRisk') or {}
    opp=d.get('opportunityScore') or {}
    conf=d.get('confirmationLayer') or {}
    internal=(conf.get('internalConfirmation') or {})
    semi=(conf.get('semiconductorLeadership') or {})

    nasdaq=num((market.get('.IXIC') or {}).get('changePct'))
    qqq=num((market.get('QQQ') or {}).get('changePct'))
    score=num(ns.get('score'))
    breadth=parse(row(d,'Market breadth').get('latest'),r'advancing\s*\(([0-9.]+)%\)')
    y10=num((mc.get('us10y') or {}).get('close'))
    y2=num((mc.get('us2y') or {}).get('close'))
    vxn=num((mc.get('vxn') or {}).get('close'))
    vxn_ch=num((mc.get('vxn') or {}).get('changePct'))
    giveback=num(risk.get('intradayGivebackPp'))

    today=store.setdefault('records',{}).setdefault(day,{})
    if stage in today:
        print(f'Checkpoint {stage} already exists for {day}; preserving original capture.');return
    due_hour,due_min={'early_market':(10,30),'mid_market':(13,0),'near_close':(15,30)}[stage]
    due=now.replace(hour=due_hour,minute=due_min,second=0,microsecond=0)
    delay=(now-due).total_seconds()/60
    if not 0<=delay<=40:
        print(f'Checkpoint {stage} outside capture window ({delay:.1f} minutes); skipping.');return
    if not d or not rec:
        raise RuntimeError(f'Cannot capture {stage}: current dashboard or daily market record missing')
    prior=None
    for s in ORDER:
        if s==stage:break
        if s in today:prior=today[s]
    prior_score=num((prior or {}).get('nasdaqScore'))
    score_delta=(score-prior_score) if score is not None and prior_score is not None else None

    checkpoint_path=[]
    for s in ORDER:
        if s==stage:
            checkpoint_path.append({'stage':stage,'score':score})
            break
        if s in today:checkpoint_path.append({'stage':s,'score':num(today[s].get('nasdaqScore'))})

    title,scheduled=STAGES[stage]
    move='positive' if (nasdaq or 0)>0.15 else ('negative' if (nasdaq or 0)<-0.15 else 'near flat')
    confirmation='constructive' if num(internal.get('score')) is not None and num(internal.get('score'))>=65 else ('weak' if num(internal.get('score')) is not None and num(internal.get('score'))<45 else 'mixed')
    semi_word='strong' if num(semi.get('score')) is not None and num(semi.get('score'))>=70 else ('weak' if num(semi.get('score')) is not None and num(semi.get('score'))<40 else 'mixed')

    p1=f"At {title.lower()}, Nasdaq is {fmt_pct(nasdaq)} on the session and QQQ is {fmt_pct(qqq)}. The Nasdaq Score is {fmt_score(score)}"
    if score_delta is not None:
        p1+=f", a {score_delta:+.0f}-point change from the prior stored checkpoint"
    p1+='.'

    p2=(f"Internal confirmation is {confirmation}: {internal.get('score','—')}/100 overall, semiconductor leadership is {semi_word} "
        f"({semi.get('score','—')}/100), and Nasdaq-100 breadth is {breadth:.0f}% advancing." if breadth is not None else
        f"Internal confirmation is {confirmation}: {internal.get('score','—')}/100 overall and semiconductor leadership is {semi_word} ({semi.get('score','—')}/100).")
    p2+=f" Consolidation Risk is {risk.get('score','—')}/100 and Opportunity Score is {opp.get('score','—')}/100."

    macro=[]
    if y10 is not None: macro.append(f'10Y {y10:.3f}%')
    if y2 is not None: macro.append(f'2Y {y2:.3f}%')
    if vxn is not None: macro.append(f'VXN {vxn:.2f}'+(f' ({vxn_ch:+.2f}%)' if vxn_ch is not None else ''))
    p3='Cross-asset context: '+', '.join(macro)+'.' if macro else 'Cross-asset confirmation is incomplete in this snapshot.'

    if stage=='early_market':
        p4=f"The opening move is {move}. The key question for the next checkpoint is whether breadth and semiconductor leadership confirm the initial direction rather than diverge from it."
    elif stage=='mid_market':
        rejection=(f" The market has given back about {giveback:.2f} percentage points from its best stored intraday level." if giveback is not None and giveback>=0.15 else '')
        p4=f"By midday the session is {move}.{rejection} The afternoon read should focus on whether the current move persists with improving internals or develops into a broader rejection/consolidation pattern."
    else:
        path=' → '.join(f"{x['stage'].replace('_',' ')} {x['score']:+.0f}" for x in checkpoint_path if x.get('score') is not None)
        p4=(f"Into the final half-hour, the session remains {move}. " + (f"Score path: {path}. " if path else '') +
            "The main carry signal is whether price, breadth, semiconductor leadership, volatility and rates finish in agreement; the 16:15 ET close snapshot remains the canonical final outcome.")

    snap={
        'captureDelayMinutes':round(delay,2),'captureMode':'late' if delay>10 else 'on_time',
        'version':1,'stage':stage,'label':title,'scheduledET':scheduled,'capturedET':now.isoformat(),
        'tradingDate':day,'nasdaqScore':score,'scoreChangeFromPriorCheckpoint':round(score_delta,1) if score_delta is not None else None,
        'nasdaqChangePct':round(nasdaq,3) if nasdaq is not None else None,'qqqChangePct':round(qqq,3) if qqq is not None else None,
        'consolidationRisk':num(risk.get('score')),'opportunityScore':num(opp.get('score')),
        'internalConfirmation':num(internal.get('score')),'semiconductorLeadership':num(semi.get('score')),
        'semiconductorBasis':semi.get('basis'),'breadthAdvancingPct':breadth,
        'intradayGivebackPp':giveback,'us10y':y10,'us2y':y2,'vxn':vxn,'vxnChangePct':vxn_ch,
        'checkpointPath':checkpoint_path,'paragraphs':[p1,p2,p3,p4]
    }
    today[stage]=snap
    store['latestTradingDate']=day
    store['updatedET']=now.isoformat()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(store,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'Captured {stage} analysis for {day}.')

if __name__=='__main__':main()
