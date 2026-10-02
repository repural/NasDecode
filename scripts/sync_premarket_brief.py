#!/usr/bin/env python3
"""Keep the researched pre-market brief authoritative across refreshes.

The daily research writer may publish the rich brief directly to
public/data/premarket.json using its research schema (updated/summary/events).
The quantitative refresh writes data/premarket.json using the dashboard schema.
This bridge normalizes a same/newer researched public brief back into the
canonical data file before publication, so a later market-data refresh cannot
silently replace the researched analysis.
"""
import json
import os
import re

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(ROOT,'data','premarket.json')
PUBLIC=os.path.join(ROOT,'public','data','premarket.json')


def load(path):
    try:
        with open(path,encoding='utf-8') as f:
            return json.load(f)
    except (OSError,json.JSONDecodeError):
        return {}


def brief_date(d):
    value=d.get('tradingDate') or d.get('updated') or d.get('updatedET') or ''
    m=re.search(r'\b(20\d{2}-\d{2}-\d{2})\b',str(value))
    return m.group(1) if m else None


def is_researched(d):
    return bool(
        d.get('researchBrief') is True
        or (d.get('bias') and isinstance(d.get('summary'),list) and d.get('summary'))
    )


def normalize(src, fallback_score=None):
    date=brief_date(src)
    if not date:
        return None
    paragraphs=src.get('paragraphs') or src.get('summary') or []
    catalysts=src.get('catalysts') or src.get('events') or []
    return {
        'version': 1,
        'tradingDate': date,
        'stage': 'premarket',
        'updatedET': src.get('updatedET') or src.get('updated') or '',
        'score': src.get('score', fallback_score),
        'paragraphs': paragraphs,
        'catalysts': catalysts,
        'confirmation': src.get('confirmation'),
        'baseline': src.get('baseline') or {},
        'researchBrief': True,
        'bias': src.get('bias'),
        'confidence': src.get('confidence'),
        'eventRisk': src.get('eventRisk'),
        'watchIntoOpen': src.get('watchIntoOpen'),
        'keyTimes': src.get('keyTimes'),
        'sources': src.get('sources') or [],
    }


def main():
    public=load(PUBLIC)
    data=load(DATA)
    if not is_researched(public):
        print('No researched public pre-market brief to synchronize.')
        return
    pdate=brief_date(public)
    ddate=brief_date(data)
    if not pdate or (ddate and pdate < ddate):
        print(f'Researched public brief is stale ({pdate}); canonical data is {ddate}.')
        return
    normalized=normalize(public, data.get('score'))
    if not normalized:
        return
    os.makedirs(os.path.dirname(DATA),exist_ok=True)
    with open(DATA,'w',encoding='utf-8') as f:
        json.dump(normalized,f,ensure_ascii=False,indent=2)
        f.write('\n')
    # Normalize the deployable copy too. This makes both schemas converge and
    # removes any dependency on frontend inference after the next refresh.
    with open(PUBLIC,'w',encoding='utf-8') as f:
        json.dump(normalized,f,ensure_ascii=False,indent=2)
        f.write('\n')
    print(f'Synchronized researched pre-market brief for {pdate}.')


if __name__=='__main__':
    main()
