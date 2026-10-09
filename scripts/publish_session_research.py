#!/usr/bin/env python3
"""Validate and publish independently researched session briefs without modifying engine measurements."""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/research/session-briefs.json'
OUT=ROOT/'public/data/session-research.json'
STAGES=('premarket','early_market','mid_market','near_close')
NY=ZoneInfo('America/New_York')

def validate(store):
    if store.get('schemaVersion')!=1 or not isinstance(store.get('sessions'),dict):
        raise ValueError('Invalid research archive root')
    for day,sessions in store['sessions'].items():
        if dt.date.fromisoformat(day).isoformat()!=day or not isinstance(sessions,dict):
            raise ValueError('Invalid trading date or sessions')
        for stage,brief in sessions.items():
            if stage not in STAGES or not isinstance(brief,dict):
                raise ValueError('Invalid session stage')
            status=brief.get('publicationStatus')
            if status not in ('published','pending','missing','failed'):
                raise ValueError('Invalid publication status')
            if status!='published':
                continue
            timestamp=dt.datetime.fromisoformat(brief['updatedET'])
            if timestamp.tzinfo is None or (timestamp.astimezone(NY).date().isoformat()!=day and not (stage=='premarket' and timestamp.astimezone(NY).date()==dt.date.fromisoformat(day)-dt.timedelta(days=1))):
                raise ValueError('Research timestamp must be timezone-aware and match trading day')
            if not isinstance(brief.get('paragraphs'),list) or not brief['paragraphs'] or not all(isinstance(x,str) and x.strip() for x in brief['paragraphs']):
                raise ValueError('Published research requires narrative paragraphs')
            if not isinstance(brief.get('sources'),list) or not brief['sources']:
                raise ValueError('Published research requires source references')
            if not brief.get('bias') or brief.get('confidence') not in ('Low','Moderate','High'):
                raise ValueError('Published research requires bias and confidence')
            if not isinstance(brief.get('catalysts',[]),list) or not isinstance(brief.get('whatToWatch',[]),list):
                raise ValueError('Invalid catalyst/watch arrays')
    return store

def main():
    archive=validate(json.loads(SOURCE.read_text(encoding='utf-8')))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(archive,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Published validated session research:',sum(len(v) for v in archive['sessions'].values()),'records')

if __name__=='__main__':
    main()
