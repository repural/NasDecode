#!/usr/bin/env python3
"""Repair 3-Day Watch Treasury trigger text from validated marketContext values.

Keeps the trigger logic untouched and only replaces malformed parsed yield display values
with the numeric observations already stored in dashboard validation data.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DASH=ROOT/'data'/'dashboard.json'

def num(v):
    try: return float(v)
    except (TypeError,ValueError): return None


def main():
    d=json.loads(DASH.read_text(encoding='utf-8'))
    watch=d.get('threeDayWatch') or {}
    triggers=watch.get('triggers') or []
    validation=d.get('validation') or {}
    mc=validation.get('marketContext') or {}
    y10=num((mc.get('us10y') or {}).get('close'))
    y2=num((mc.get('us2y') or {}).get('close'))

    if y10 is None:
        return

    for t in triggers:
        title=str(t.get('title',''))
        if title=='10Y above 5.05%':
            t['detail']=f'US10Y is {y10:.3f}%, above the 3-Day Watch significant-headwind threshold.' + (f' US2Y is {y2:.3f}%.' if y2 is not None else '')
        elif title=='10Y above 5.00%':
            t['detail']=f'US10Y is {y10:.3f}%, in the restrictive 5.00–5.05% zone.'
        elif title=='10Y below 4.95%':
            t['detail']=f'US10Y is {y10:.3f}%, inside the supportive 3-Day Watch zone.'

    DASH.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

if __name__=='__main__':
    main()
