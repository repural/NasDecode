"""Append complete Yahoo observations to Massive for display, never canonical history."""
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.research_nvda_wavetrend import wavetrend, crossover_records

NY = ZoneInfo('America/New_York')


def developing_preview(rows, candle, hours, now):
    """Recalculate one uncommitted point from confirmed history on every refresh."""
    if not candle or candle.get('isConfirmed') is not False:
        return None
    try:
        start, end, as_of, checked, last_bar = (dt.datetime.fromisoformat(candle[k]) for k in
            ('startET', 'endET', 'asOfET', 'checkedAtET', 'lastSourceBarET'))
        if any(t.tzinfo is None for t in (start, end, as_of, checked, last_bar)):
            return None
        if (start.weekday() >= 5 or start.hour not in range(4, 20, hours)
                or start.minute or start.second or end != start + dt.timedelta(hours=hours)
                or not start <= last_bar < as_of <= checked <= now < end
                or now - as_of > dt.timedelta(minutes=30)):
            return None
        previous = dt.datetime.fromisoformat(rows[-1]['endET'])
        if start != previous:
            day = previous.date() + dt.timedelta(days=1)
            while day.weekday() >= 5:
                day += dt.timedelta(days=1)
            if previous.hour != 20 or start != dt.datetime.combine(day, dt.time(4), NY):
                return None
        if last_bar.minute % 5 or last_bar.second:
            return None
        count = int((last_bar - start).total_seconds()/300) + 1
        if candle.get('underlying5mBars') != count:
            return None
        prices = [candle[k] for k in ('open', 'high', 'low', 'close')]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in prices):
            return None
        o, h, l, c = prices
        if not l <= min(o, c) <= max(o, c) <= h:
            return None
    except (KeyError, ValueError, TypeError):
        return None
    raw = {k: candle[k] for k in ('startET', 'endET', 'open', 'high', 'low', 'close')}
    preview = wavetrend(rows + [raw])[-1]
    if not preview['isWarm'] or preview['wt1'] is None or preview['wt2'] is None:
        return None
    preview.update(isConfirmed=False, provider='Yahoo developing',
                   asOfET=as_of.isoformat(), lastSourceBarET=last_bar.isoformat(),
                   underlying5mBars=count, potentialCross=preview['cross'], cross=None)
    return preview


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
        raw_preview = shadow.get('timeframes', {}).get(tf, {}).get('developingCandle')
        series['developing'] = developing_preview(rows, raw_preview, hours, now)
        counts[tf] = len(appended)
    result['displaySource'] = 'Massive + Yahoo provisional' if any(counts.values()) else 'Massive'
    result['displayThroughET'] = max(s['latest']['endET'] for s in result['timeframes'].values())
    return result
