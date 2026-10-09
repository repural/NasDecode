#!/usr/bin/env python3
"""Assert the selected session checkpoint was persisted for the actual NY date."""
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

stage=os.environ.get('NASDECODE_ANALYSIS_STAGE')
if stage:
    day=dt.datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    data=json.loads(Path('data/history/session-analyses.json').read_text())
    if stage not in data.get('records',{}).get(day,{}):
        raise SystemExit('ERROR: selected checkpoint missing from history: '+day+' '+stage)
    print('Verified checkpoint: '+day+' '+stage)
else:
    print('No checkpoint selected for this refresh')
