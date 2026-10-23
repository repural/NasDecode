"""Audit GOOGL candles against the existing US exchange session calendar."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


def audit(source, calendar, end='2026-10-16'):
    if source.get('symbol')!='GOOGL' or source.get('fetchErrors'):
        raise ValueError('Incomplete or wrong-symbol GOOGL source')
    days={b['date'] for b in calendar['bars'] if '2026-01-01'<=b['date']<=end}
    if not days or max(days)!=end:
        raise ValueError('Reference exchange calendar is incomplete')
    result={'symbol':'GOOGL','evaluationStartDate':'2026-01-01','evaluationEndDate':end,
            'calendarDescription':'US stock trading dates from existing adjusted NVDA daily archive; NVDA prices are never used in GOOGL indicators or returns.',
            'timeframes':{}}
    for tf,per_day,max_count in [('4h',4,48),('8h',2,96)]:
        rows=source['timeframes'][tf]['candles'];keys=[c['startET'] for c in rows]
        if keys!=sorted(set(keys)) or len(rows)<=100:
            raise ValueError('Invalid GOOGL timestamp coverage: '+tf)
        for left,right in zip(rows,rows[1:]):
            if left['endET']>right['startET']:
                raise ValueError('Overlapping GOOGL candles')
        for c in rows:
            if not all(math.isfinite(c[k]) and c[k]>0 for k in ['open','high','low','close']):
                raise ValueError('Invalid OHLC')
            if not c['low']<=min(c['open'],c['close'])<=max(c['open'],c['close'])<=c['high']:
                raise ValueError('Inconsistent OHLC')
            if not 0<c['underlying5mBars']<=max_count:
                raise ValueError('Invalid source interval count')
        counts=Counter(c['startET'][:10] for c in rows)
        missing={day:counts.get(day,0) for day in days if counts.get(day,0)!=per_day}
        if missing:raise ValueError('Missing GOOGL evaluation buckets: '+str(missing))
        if not next(c for c in rows if c['startET'][:10]>='2026-01-01')['isWarm']:
            raise ValueError('Insufficient 2026 warm-up')
        result['timeframes'][tf]={'candles':len(rows),'firstStartET':rows[0]['startET'],'lastEndET':rows[-1]['endET'],
            'evaluationSessions':len(days),'evaluationMissingBuckets':missing,
            'warmupShortSessions':{day:n for day,n in counts.items() if day<'2026-01-01' and n!=per_day},
            'sparseSourceCandles':sum(c['underlying5mBars']<max_count for c in rows),
            'source5mCountDistribution':dict(Counter(c['underlying5mBars'] for c in rows))}
    result['notes']=['No missing intervals or candles are synthesized. Sparse five-minute source intervals are disclosed.',
                     'Only completed candles are emitted using the existing end-of-bucket rule. Warm-up gaps are disclosed; all evaluation sessions must have every bucket.',
                     'GOOGL is Alphabet Class A; no GOOG prices are substituted.']
    return result


if __name__=='__main__':
    p=Path('data/research/googl-wavetrend.json');calendar=Path('data/history/nvda-daily.json')
    result=audit(json.loads(p.read_text()),json.loads(calendar.read_text()))
    result['inputSha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    result['calendarSha256']=hashlib.sha256(calendar.read_bytes()).hexdigest()
    Path('data/research/googl-wavetrend-coverage.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
