#!/usr/bin/env python3
"""Select a due quantitative checkpoint from actual NY time, without backdating observations."""
import datetime as dt
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

NY=ZoneInfo('America/New_York')
STAGES=(('early_market',10,30),('mid_market',13,0),('near_close',15,30))
ROOT=Path(__file__).resolve().parents[1]
HISTORY=ROOT/'data/history/session-analyses.json'

def resolve(now, records, max_delay=40):
    day=now.date().isoformat()
    if now.weekday()>=5:
        return None
    today=records.get(day,{})
    for name,hour,minute in STAGES:
        due=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
        delay=(now-due).total_seconds()/60
        if 0<=delay<=max_delay and name not in today:
            return name
    return None

def main():
    now=dt.datetime.now(NY)
    try:
        records=json.loads(HISTORY.read_text()).get('records',{})
    except (FileNotFoundError,json.JSONDecodeError):
        records={}
    stage=resolve(now,records)
    if stage:
        print(stage)
        print(f'Quantitative checkpoint due: {stage} at {now.isoformat()}',file=sys.stderr)
    else:
        print(f'No due checkpoint at {now.isoformat()}',file=sys.stderr)

if __name__=='__main__':
    main()
