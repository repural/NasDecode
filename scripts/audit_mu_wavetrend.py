"""Validate MU research coverage before running the unchanged comparison models."""
import json
import math
from collections import Counter
from pathlib import Path


def audit(source, daily, end_date='2026-10-16'):
    if source.get('symbol') != 'MU' or source.get('fetchErrors'):
        raise ValueError('Missing or incomplete MU provider data')
    result = {'symbol': 'MU', 'evaluationEndDate': end_date, 'timeframes': {}}
    expected_days = {b['date'] for b in daily['bars']
                     if source['timeframes']['4h']['firstStartET'][:10] <= b['date'] <= end_date}
    for tf, expected in (('4h', 48), ('8h', 96)):
        rows = source['timeframes'][tf]['candles']
        keys = [c['startET'] for c in rows]
        if keys != sorted(set(keys)) or len(rows) <= 100:
            raise ValueError('Invalid timestamp/warm-up coverage: ' + tf)
        for c in rows:
            if not all(math.isfinite(c[k]) and c[k] > 0 for k in ('open', 'high', 'low', 'close')):
                raise ValueError('Invalid OHLC')
            if not c['low'] <= min(c['open'], c['close']) <= max(c['open'], c['close']) <= c['high']:
                raise ValueError('Inconsistent OHLC')
            if not 0 < c['underlying5mBars'] <= expected:
                raise ValueError('Invalid five-minute bar count')
        available = {c['startET'][:10] for c in rows}
        missing = sorted(expected_days - available)
        if missing:
            raise ValueError('Missing entire MU sessions: ' + str(missing))
        by_day = Counter(c['startET'][:10] for c in rows)
        short = {day: count for day, count in by_day.items()
                 if count != (4 if tf == '4h' else 2)}
        # Warm-up gaps are disclosed rather than filled. Require every bucket
        # during the evaluation period; the 100-observation warm-up still applies.
        unexpected = {day: count for day, count in short.items()
                      if day >= '2026-01-01'}
        if unexpected:
            raise ValueError('Unexpected missing MU timeframe buckets: ' + str(unexpected))
        first_2026 = next(c for c in rows if c['startET'][:10] >= '2026-01-01')
        if not first_2026['isWarm']:
            raise ValueError('Insufficient 2026 WT warm-up')
        result['timeframes'][tf] = {'candles': len(rows), 'firstStartET': rows[0]['startET'],
                                   'lastEndET': rows[-1]['endET'],
                                   'shortSessions': short,
                                   'warmupShortSessions': {day: count for day, count in short.items()
                                                           if day < '2026-01-01'},
                                   'evaluationMissingBuckets': unexpected,
                                   'source5mCountDistribution': dict(Counter(c['underlying5mBars'] for c in rows)),
                                   'sparseSourceCandles': sum(c['underlying5mBars'] < expected for c in rows)}
    result['notes'] = ['Provider five-minute intervals with no reported trade may be absent; no intervals or candles are fabricated.',
                       'Aggregation and end-of-bucket checks match the existing NVDA collector. Sparse source candles are counted explicitly.',
                       'Incomplete warm-up sessions are disclosed without filling gaps; evaluation sessions require all timeframe buckets and at least 100 earlier observations.']
    return result


if __name__ == '__main__':
    source = json.loads(Path('data/research/mu-wavetrend.json').read_text())
    daily = json.loads(Path('data/history/mu-daily.json').read_text())
    result = audit(source, daily)
    Path('data/research/mu-wavetrend-coverage.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
