#!/usr/bin/env python3
"""Reconcile the current pre-market brief with final refined dashboard scores.

refresh.py creates the deterministic/researched pre-market artifact before the
post-processing score refinements run. This script runs after refine_scores.py so
the published pre-market score references match the scorecards from the same
refresh. It only mutates today's brief before 09:30 ET; after the open the
pre-market snapshot is historical and must remain frozen.
"""
import datetime as dt
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DASH=ROOT/'data'/'dashboard.json'
PRE=ROOT/'data'/'premarket.json'
NY=ZoneInfo('America/New_York')

def load(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError):
        return {}

def signed(v):
    try:
        n=float(v)
    except (TypeError,ValueError):
        return '—'
    return f'{n:+.0f}'

def main():
    now=dt.datetime.now(NY)
    if now.hour*60+now.minute >= 9*60+30:
        print('Cash session has started; preserving frozen pre-market snapshot.')
        return
    d=load(DASH); p=load(PRE)
    if not d or not p or p.get('tradingDate') != now.date().isoformat():
        print('No current pre-market artifact to reconcile.')
        return

    ns=(d.get('nasdaqScore') or {})
    risk=(d.get('consolidationRisk') or {})
    opp=(d.get('opportunityScore') or {})
    ns_score=ns.get('score')
    risk_score=risk.get('score')
    risk_level=risk.get('level')
    opp_score=opp.get('score')

    if ns_score is not None:
        p['score']=ns_score
    p['finalScores']={
        'nasdaqScore':ns_score,
        'consolidationRisk':risk_score,
        'opportunityScore':opp_score,
        'source':'final refined dashboard scores',
        'dashboardUpdatedET':d.get('updatedET')
    }

    def reconcile(text):
        s=str(text)
        if ns_score is not None:
            s=re.sub(r'(Nasdaq Score is )[-+]?\d+(?:\.\d+)?/100',
                     lambda m:m.group(1)+signed(ns_score)+'/100',s,flags=re.I)
        if risk_score is not None:
            repl=f'Consolidation Risk is {risk_score}/100'
            if risk_level:
                repl+=f' ({risk_level})'
            s=re.sub(r'Consolidation Risk is \d+(?:\.\d+)?/100(?:\s*\([^)]*\))?',
                     repl,s,flags=re.I)
        if opp_score is not None:
            s=re.sub(r'(Opportunity Score is )\d+(?:\.\d+)?/100',
                     lambda m:m.group(1)+str(opp_score)+'/100',s,flags=re.I)
        return s

    if isinstance(p.get('paragraphs'),list):
        p['paragraphs']=[reconcile(x) for x in p['paragraphs']]
    if isinstance(p.get('summary'),list):
        p['summary']=[reconcile(x) for x in p['summary']]
    for key in ('watchIntoOpen','keyTimes','confirmation'):
        if isinstance(p.get(key),str):
            p[key]=reconcile(p[key])

    PRE.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Reconciled pre-market scores: Nasdaq {ns_score}, Risk {risk_score}, Opportunity {opp_score}.")

if __name__=='__main__':
    main()
