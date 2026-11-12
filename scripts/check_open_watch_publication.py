#!/usr/bin/env python3
"""Audit NasDecode Open Watch publication consistency, without inventing events."""
import datetime as dt
import json
from pathlib import Path

canonical=Path('data/history/market-watch-events.json')
published=Path('public/history/market-watch-events.json')
a=json.loads(canonical.read_text(encoding='utf-8'))
b=json.loads(published.read_text(encoding='utf-8'))
def index(d):
    return {e['id']: e for e in d.get('events', [])}
source=index(a); visible=index(b)
missing=sorted(set(source)-set(visible))
mismatched=sorted(k for k in source.keys() & visible.keys() if source[k]!=visible[k])
extra=sorted(set(visible)-set(source))
latest=max((e.get('eventTime','') for e in source.values()),default='')
now=dt.datetime.now(dt.timezone.utc)
try:
    age=(now-dt.datetime.fromisoformat(latest.replace('Z','+00:00'))).days
except (ValueError, TypeError):
    age=None
print(f'Canonical events: {len(source)}; public events: {len(visible)}; latest event: {latest}; age in days: {age}')
print(f'Missing: {missing}; mismatched: {mismatched}; extra: {extra}')
if age is not None and age>3:
    print('WARNING: no newly retained Open Watch event for >3 days; verify the editorial ingestion process.')
if missing or mismatched or extra:
    raise SystemExit('Open Watch publication drift: canonical and public history differ')
print('PASS: canonical event records match public archive')
