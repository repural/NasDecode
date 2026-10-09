#!/usr/bin/env python3
"""Validate independent research and publish it without changing quantitative checkpoints."""
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/research/session-briefs.json'
OUT=ROOT/'public/data/session-research.json'
STAGES=('premarket','early_market','mid_market','near_close')
NY=ZoneInfo('America/New_York')
VALID_STATUSES=('published','pending','missing','failed')

def unique_pairs(pairs):
    result={}
    for k,v in pairs:
        if k in result:
            raise ValueError('Duplicate JSON key: '+k)
        result[k]=v
    return result

def holiday(day):
    # NYSE regular full-day closures; unusual emergency closures require exchange calendar updates.
    y=day.year
    def observed(d):
        return d-dt.timedelta(days=1) if d.weekday()==5 else d+dt.timedelta(days=1) if d.weekday()==6 else d
    def nth(month,weekday,n):
        d=dt.date(y,month,1)
        return d+dt.timedelta(days=(weekday-d.weekday())%7+7*(n-1))
    def last(month,weekday):
        d=dt.date(y+1,1,1)-dt.timedelta(days=1) if month==12 else dt.date(y,month+1,1)-dt.timedelta(days=1)
        return d-dt.timedelta(days=(d.weekday()-weekday)%7)
    # Meeus Gregorian Easter algorithm
    a=y%19;b=y//100;c=y%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32+2*e+2*i-h-k)%7
    m=(a+11*h+22*l)//451;month=(h+l-7*m+114)//31;dom=(h+l-7*m+114)%31+1
    easter=dt.date(y,month,dom)
    closures={observed(dt.date(y,1,1)),nth(1,0,3),nth(2,0,3),easter-dt.timedelta(days=2),
              last(5,0),observed(dt.date(y,6,19)),observed(dt.date(y,7,4)),
              nth(9,0,1),nth(11,3,4),observed(dt.date(y,12,25))}
    # New Year's Day observed on preceding Dec 31 when next year Jan 1 falls Saturday
    closures.add(observed(dt.date(y+1,1,1)))
    return day.weekday()>=5 or day in closures

def validate(store):
    if store.get('schemaVersion')!=1 or not isinstance(store.get('sessions'),dict):
        raise ValueError('Invalid research archive root')
    for day,sessions in store['sessions'].items():
        date=dt.date.fromisoformat(day)
        if date.isoformat()!=day or not isinstance(sessions,dict) or holiday(date):
            raise ValueError('Invalid or non-trading research date: '+day)
        for stage,brief in sessions.items():
            if stage not in STAGES or not isinstance(brief,dict):
                raise ValueError('Invalid session stage')
            status=brief.get('publicationStatus')
            if status not in VALID_STATUSES:
                raise ValueError('Invalid publication status')
            if status!='published':
                continue
            timestamp=dt.datetime.fromisoformat(brief['updatedET'])
            local=timestamp.astimezone(NY) if timestamp.tzinfo else None
            if local is None or (local.date()!=date and not (stage=='premarket' and local.date()==date-dt.timedelta(days=1))):
                raise ValueError('Research timestamp must be timezone-aware and correspond to the trading date')
            if not isinstance(brief.get('paragraphs'),list) or not brief['paragraphs'] or not all(isinstance(x,str) and x.strip() for x in brief['paragraphs']):
                raise ValueError('Published research requires narrative paragraphs')
            if not isinstance(brief.get('sources'),list) or not brief['sources'] or not all(isinstance(x,str) and x.strip() for x in brief['sources']):
                raise ValueError('Published research requires source references')
            # Previously migrated briefs have citation labels; require URLs on new research.
            if not brief.get('legacySource') and not all(urlparse(x).scheme=='https' and urlparse(x).netloc for x in brief['sources']):
                raise ValueError('New research requires HTTPS source URLs')
            if not isinstance(brief.get('bias'),str) or not brief['bias'].strip() or brief.get('confidence') not in ('Low','Moderate','High'):
                raise ValueError('Published research requires bias and confidence')
            if not isinstance(brief.get('catalysts',[]),list) or not isinstance(brief.get('whatToWatch',[]),list):
                raise ValueError('Invalid catalyst/watch arrays')
    return store

def main():
    archive=validate(json.loads(SOURCE.read_text(encoding='utf-8'),object_pairs_hook=unique_pairs))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(archive,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Published validated session research:',sum(len(v) for v in archive['sessions'].values()),'records')

if __name__=='__main__':
    main()
