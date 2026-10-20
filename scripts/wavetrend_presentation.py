"""Append complete Yahoo observations to Massive for display, never canonical history."""
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.research_nvda_wavetrend import wavetrend, crossover_records

NY = ZoneInfo('America/New_York')


def presentation(source, shadow_path=None, now=None):
    now = now or dt.datetime.now(NY)
    result = json.loads(json.dumps(source))
    path = shadow_path or Path('data/research/' + source['symbol'].lower() + '-wavetrend-yahoo-shadow.json')
    shadow = json.loads(path.read_text()) if path.exists() else {}
    if shadow and shadow.get('symbol', source['symbol']) != source['symbol']:
        raise ValueError('Yahoo symbol does not match historical archive')
    result['collectionCheckedAtET'] = shadow.get('checkedAtET')
    result['collectionStatus'] = shadow.get('status', 'historical_only')
    result['massiveHistoricalEndET'] = source['historicalDataEndET']
    result['reconciliation'] = {
        tf: {k: v for k, v in data.items() if k != 'samples'}
        for tf, data in shadow.get('reconciliation', {}).items()}
    counts = {}
    for hours in (4, 8):
        tf = str(hours) + 'h'
        history = [{**c, 'provider': 'Massive'} for c in source['timeframes'][tf]['candles']]
        candidates = dict(shadow.get('observations', {}).get(tf, {}))
        for candle in shadow.get('timeframes', {}).get(tf, {}).get('yahooCandles', []):
            candidates[candle['startET']] = candle
        end = dt.datetime.fromisoformat(history[-1]['endET'])
        appended = []
        for stamp, candle in sorted(candidates.items()):
            start = dt.datetime.fromisoformat(stamp)
            if start < end:
                continue  # Massive replaces Yahoo as soon as historical data arrives.
            if start != end:
                day = end.date() + dt.timedelta(days=1)
                while day.weekday() >= 5:
                    day += dt.timedelta(days=1)
                if end.hour != 20 or start != dt.datetime.combine(day, dt.time(4), NY):
                    break  # Never bridge missing candles.
            close_time = start + dt.timedelta(hours=hours)
            if (candle.get('endET') != close_time.isoformat()
                    or close_time + dt.timedelta(minutes=5) > now
                    or start.hour not in range(4, 20, hours) or start.minute or start.second):
                break
            prices = [candle.get(k) for k in ('open', 'high', 'low', 'close')]
            if not all(isinstance(x, (float, int)) and math.isfinite(x) and x > 0 for x in prices):
                break
            o, h, l, c = prices
            if h < max(o, c) or l > min(o, c) or h < l:
                break
            appended.append({k: candle[k] for k in ('startET', 'endET', 'open', 'high', 'low', 'close')}
                            | {'provider': 'Yahoo provisional'})
            end = close_time
        rows = wavetrend(history + appended)
        series = result['timeframes'][tf]
        series.update(candles=rows, latest=rows[-1], candleCount=len(rows),
                      lastEndET=rows[-1]['endET'], crosses=crossover_records(rows),
                      yahooCandles=len(appended))
        counts[tf] = len(appended)
    result['displaySource'] = 'Massive + Yahoo provisional' if any(counts.values()) else 'Massive'
    result['displayThroughET'] = max(s['latest']['endET'] for s in result['timeframes'].values())
    return result
