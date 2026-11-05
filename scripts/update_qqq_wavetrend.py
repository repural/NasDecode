"""QQQ WT archive and publication; daily bars remain owned by their collector."""
import datetime as dt
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from scripts import research_nvda_wavetrend as research
from scripts.refresh_nvda_wavetrend import refresh
from scripts.wavetrend_presentation import presentation

SOURCE = Path('data/research/qqq-wavetrend.json')
TARGET = Path('public/data/qqq-wavetrend.json')
DAILY = Path('data/history/qqq-daily.json')


def daily_averages(document, now):
    if document.get('ticker') != 'QQQ' or document.get('adjusted') is not True:
        raise ValueError('QQQ adjusted daily archive required')
    bars = [b for b in document['bars'] if b['date'] < now.date().isoformat()]
    dates = [b['date'] for b in bars]
    if dates != sorted(set(dates)) or len(bars) < 200:
        raise ValueError('Need at least 200 unique ordered completed daily sessions')
    closes = [b.get('close') for b in bars[-200:]]
    if not all(isinstance(v, (float, int)) and math.isfinite(v) and v > 0 for v in closes):
        raise ValueError('Invalid daily closes; no gap filling')
    last = closes[-1]
    result = {'timeframe': '1D', 'price': last, 'throughDate': dates[-1],
              'source': document['source'], 'method': 'Arithmetic mean of adjusted completed daily closes',
              'archiveUpdatedET': document.get('updatedET')}
    for n in (50, 200):
        value = sum(closes[-n:])/n
        result['sma'+str(n)] = round(value, 6)
        result['distanceSMA'+str(n)+'Pct'] = round(100*(last/value-1), 4)
    return result


def publish(now=None, src=SOURCE, dst=TARGET, daily=DAILY, shadow_path=None):
    now = now or dt.datetime.now(research.NY)
    original = json.loads(src.read_text())
    if original.get('symbol') != 'QQQ' or original.get('fetchErrors'):
        raise ValueError('Invalid QQQ WT archive')
    shown = presentation(original, shadow_path=shadow_path, now=now)
    result = {k: shown.get(k) for k in ('schemaVersion','symbol','generatedET',
              'historicalDataEndET','boundaryAssumption','collectionCheckedAtET','collectionStatus',
              'massiveHistoricalEndET','displaySource','displayThroughET','reconciliation')}
    result['researchOnly'] = True
    result['timeframes'] = {}
    for tf in ('4h','8h'):
        series = shown['timeframes'][tf]
        if len(series['candles']) < 148 or not all(b.get('isWarm') for b in series['candles'][-48:]):
            raise ValueError('QQQ '+tf+' needs warmed history')
        result['timeframes'][tf] = {'candleCount': series['candleCount'], 'latest': series['latest'],
            'lastCross': series['crosses'][-1] if series['crosses'] else None,
            'candles': series['candles'][-48:], 'developing': series.get('developing')}
    # Fail visibly rather than label an SMA based on an incomplete or wrong-symbol archive.
    try:
        result['movingAverages'] = daily_averages(json.loads(daily.read_text()), now)
    except (OSError, ValueError, KeyError, TypeError):
        result['movingAverages'] = None
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(result, separators=(',', ':'))+'\n')
    return result


def main():
    now = dt.datetime.now(research.NY)
    key = os.getenv('MASSIVE_API_KEY', '').strip()
    if not key:
        raise RuntimeError('MASSIVE_API_KEY unavailable')
    # Reuse the identical WT formula, five-minute fetcher, session boundaries and throttle.
    # This module runs in its own process; the provider URL cannot affect other tickers.
    research.BASE = 'https://api.massive.com/v2/aggs/ticker/QQQ/range/5/minute/'
    if not SOURCE.exists():
        candidate = research.build(days=220, now=now)
        candidate['symbol'] = 'QQQ'
        if candidate.get('fetchErrors') or any(v['latest'] is None for v in candidate['timeframes'].values()):
            raise RuntimeError('QQQ initial historical fetch incomplete')
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        SOURCE.write_text(json.dumps(candidate, separators=(',', ':'))+'\n')
    else:
        original = json.loads(SOURCE.read_text())
        last = dt.datetime.fromisoformat(original['timeframes']['4h']['latest']['endET']).date()
        prior = now.date()-dt.timedelta(days=1)
        while prior.weekday() >= 5:
            prior -= dt.timedelta(days=1)
        if last < prior:
            bars, errors = research.load_extended_bars(max(3,(now.date()-last).days+3),now.date(),key)
            if not errors:
                try:
                    candidate, advanced = refresh(original,bars,now,symbol='QQQ')
                    if advanced:
                        SOURCE.write_text(json.dumps(candidate,separators=(',', ':'))+'\n')
                except ValueError as exc:
                    print('Retaining QQQ history; historical refresh rejected:',exc)
            else:
                print('Retaining QQQ history; historical fetch incomplete:',errors)
    for module in ('shadow_nvda_yahoo_wavetrend','reconcile_nvda_yahoo_wavetrend'):
        subprocess.run([sys.executable,'-m','scripts.'+module,'--symbol','QQQ'],check=True)
    result = publish(now=now)
    print('QQQ published:', {tf:s['latest']['endET'] for tf,s in result['timeframes'].items()},
          'daily SMA as of', (result.get('movingAverages') or {}).get('throughDate'))


if __name__ == '__main__':
    main()
