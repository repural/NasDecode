"""Causal, research-only WT timeframe comparison. Never changes live scores or feeds.

All decisions use completed bars; all fills use the next 4H open. Higher
timeframes gate entries, while every variant exits on the same 4H red cross.
"""
import bisect
import datetime as dt
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.research_nvda_wavetrend import wavetrend

NY = ZoneInfo('America/New_York')
STRATEGIES = ('4h_alone', '4h_8h', '4h_1d')
COSTS = {'zeroCosts': 0, 'cost10bps': .001, 'cost25bps': .0025}
INITIAL = 10000
OUTPUT = Path('data/research/wavetrend-timeframe-comparison.json')
REPORT = Path('data/research/wavetrend-timeframe-comparison.md')


def stamp(value):
    return dt.datetime.fromisoformat(value).timestamp()


def daily_rows(bars):
    """Daily source bars are regular-session OHLC, known at 16:00 ET."""
    rows = []
    for b in bars:
        day = dt.date.fromisoformat(b['date'])
        # Early-close days are conservatively released at 16:00, never early.
        start = dt.datetime.combine(day, dt.time(9, 30), NY)
        rows.append({'startET': start.isoformat(),
                     'endET': dt.datetime.combine(day, dt.time(16), NY).isoformat(),
                     **{k: b[k] for k in ('open', 'high', 'low', 'close')}})
    return wavetrend(rows)


def extended_daily(four):
    grouped = defaultdict(list)
    for candle in four:
        grouped[candle['startET'][:10]].append(candle)
    output, excluded = [], []
    for day, bars in sorted(grouped.items()):
        if len(bars) != 4 or [b['startET'][11:16] for b in bars] != ['04:00', '08:00', '12:00', '16:00']:
            excluded.append(day)
            continue
        output.append({'startET': bars[0]['startET'], 'endET': bars[-1]['endET'],
                       'open': bars[0]['open'], 'high': max(b['high'] for b in bars),
                       'low': min(b['low'] for b in bars), 'close': bars[-1]['close']})
    return wavetrend(output), excluded


def bullish(candle):
    return bool(candle and candle.get('isWarm') and candle.get('wt1') is not None
                and candle.get('wt2') is not None and candle['wt1'] > candle['wt2'])


def simulate(four, higher=None, start_date='2026-01-01', end_date='9999-12-31',
             cost=.001, initially_long=True):
    if not 0 <= cost < 1:
        raise ValueError('Invalid transaction cost')
    rows = [b for b in four if b['endET'][:10] <= end_date]
    start = next((i for i, c in enumerate(rows) if c['startET'][:10] >= start_date), None)
    if start is None or start == 0 or not rows[start - 1].get('isWarm'):
        raise ValueError('Missing start/reference or warmed 4H history')
    for left, right in zip(rows, rows[1:]):
        if stamp(left['endET']) > stamp(right['startET']):
            raise ValueError('Overlapping/noncausal execution candles')
    use_higher = higher is not None
    higher = higher if higher is not None else []
    ht_ends = [stamp(c['endET']) for c in higher]
    if ht_ends != sorted(set(ht_ends)):
        raise ValueError('Higher-timeframe timestamps must be unique and ordered')
    reference = rows[start - 1]
    shares = INITIAL / reference['close'] if initially_long else 0
    cash = 0 if initially_long else INITIAL
    peak, max_dd = INITIAL, 0
    pending, entry = None, None
    executions, trades, equity, exposure, opening_equity = [], [], [], {}, {}
    for i in range(start, len(rows)):
        candle = rows[i]
        opening_equity[i] = cash + shares * candle['open']
        if pending:
            if stamp(pending['confirmedAtET']) > stamp(candle['startET']):
                raise ValueError('Execution before signal confirmation')
            price = candle['open']
            if pending['action'] == 'BUY':
                entry = {'entryAtET': candle['startET'], 'entryPrice': price,
                         'capitalBeforeEntry': cash, 'entryIndex': i}
                shares, cash = cash * (1 - cost) / price, 0
            else:
                cash, shares = shares * price * (1 - cost), 0
                if entry is not None:
                    ret = 100 * (cash / entry['capitalBeforeEntry'] - 1)
                    trades.append({**entry, 'exitAtET': candle['startET'],
                                   'exitPrice': price, 'netReturnPct': round(ret, 6),
                                   'holding4hBars': i - entry['entryIndex']})
                entry = None
            executions.append({**pending, 'executedAtET': candle['startET'],
                               'executionPrice': price})
            pending = None
        exposure[i] = shares > 0
        value = cash + shares * candle['close']
        peak = max(peak, value)
        max_dd = min(max_dd, 100 * (value / peak - 1))
        equity.append({'endET': candle['endET'], 'value': round(value, 6),
                       'heldShares': shares > 0})
        if i == len(rows) - 1:
            continue
        decision = {'confirmedAtET': candle['endET'], 'signal4hStartET': candle['startET']}
        if shares > 0 and candle.get('cross') == 'bearish':
            pending = {**decision, 'action': 'SELL'}
        elif cash > 0 and bullish(candle):
            idx = bisect.bisect_right(ht_ends, stamp(candle['endET'])) - 1
            higher_bar = higher[idx] if idx >= 0 else None
            if not use_higher or bullish(higher_bar):
                pending = {**decision, 'action': 'BUY',
                           'higherConfirmedAtET': higher_bar['endET'] if higher_bar else None}
    final = equity[-1]['value']
    buy_hold = INITIAL * rows[-1]['close'] / reference['close']
    losing = sum(t['netReturnPct'] < 0 for t in trades)
    monthly, last = {}, INITIAL
    month_end = {}
    for item in equity:
        month_end[item['endET'][:7]] = item['value']
    for month, value in month_end.items():
        monthly[month] = round(100 * (value / last - 1), 4)
        last = value
    rebound_stats, rebound_events = {}, {}
    for threshold in (2, 5, 10):
        events = []
        for i in range(start, len(rows) - 20):
            if rows[i].get('cross') != 'bullish':
                continue
            first, last_idx = i + 1, i + 20
            forward = 100 * (rows[last_idx]['close'] / rows[first]['open'] - 1)
            if forward < threshold:
                continue
            held = [exposure[j] for j in range(first, last_idx + 1)]
            delay = next((n for n, v in enumerate(held) if v), None)
            strategy_return = 100 * (equity[last_idx - start]['value'] / opening_equity[first] - 1)
            events.append({'confirmedAtET': rows[i]['endET'],
                           'entryOpportunityET': rows[first]['startET'],
                           'windowEndET': rows[last_idx]['endET'],
                           'forwardReturnPct': round(forward, 4),
                           'missedStart': not held[0],
                           'completelyMissed': not any(held),
                           'strategyNetReturnPct': round(strategy_return, 4),
                           'delay4hBars': delay})
        count = len(events)
        rebound_stats[str(threshold)] = {
            'qualifyingWindows': count,
            'missedStarts': sum(e['missedStart'] for e in events),
            'completelyMissed': sum(e['completelyMissed'] for e in events),
            'unprofitableReboundWindows': sum(e['strategyNetReturnPct'] <= 0 for e in events),
            'meanWindowStrategyNetReturnPct': round(sum(e['strategyNetReturnPct'] for e in events) / count, 4) if count else None,
            'meanWindowBuyHoldReturnPct': round(sum(e['forwardReturnPct'] for e in events) / count, 4) if count else None,
            'missedStartPct': round(100 * sum(e['missedStart'] for e in events) / count, 2) if count else None}
        rebound_events[str(threshold)] = events
    return {'referenceAtET': reference['endET'], 'referencePrice': reference['close'],
            'firstDecisionET': rows[start]['endET'], 'lastMarkET': rows[-1]['endET'],
            'initiallyLong': initially_long, 'initialValue': INITIAL,
            'costPerSidePct': round(cost * 100, 4),
            'finalValue': round(final, 2), 'returnPct': round(100 * (final / INITIAL - 1), 2),
            'maxCloseDrawdownPct': round(max_dd, 2),
            'buyAndHoldReturnPct': round(100 * (buy_hold / INITIAL - 1), 2),
            'executions': len(executions), 'closedSignalTrades': len(trades),
            'losingSignalTrades': losing,
            'falseSignalRatePct': round(100 * losing / len(trades), 2) if trades else None,
            'losingWhipsawsWithin4Bars': sum(t['netReturnPct'] < 0 and t['holding4hBars'] <= 4 for t in trades),
            'exposure4hBarsPct': round(100 * sum(exposure.values()) / len(exposure), 2),
            'finalPosition': 'shares' if shares else 'cash',
            'unclosedSignalTrade': entry is not None,
            'rebounds': rebound_stats, 'reboundEvents': rebound_events,
            'monthlyReturnPct': monthly, 'executionLedger': executions,
            'tradeLedger': trades, 'equityCurve': equity}


def compact(value):
    return {k: v for k, v in value.items()
            if k not in ('reboundEvents', 'executionLedger', 'tradeLedger', 'equityCurve')}


def evaluate(four, eight, daily, start, end, initially_long=True, include_ledgers=False):
    answer = {}
    for strategy, higher in zip(STRATEGIES, (None, eight, daily)):
        answer[strategy] = {}
        for label, cost in COSTS.items():
            r = simulate(four, higher, start, end, cost, initially_long)
            answer[strategy][label] = r if include_ledgers and label == 'cost10bps' else compact(r)
    return answer


def render_report(report):
    lines = ['# WaveTrend timeframe comparison', '',
             'Research only. WT 10/21/4; identical next-4H-open execution and costs. No thresholds optimized.', '',
             '## Main comparison', '',
             f"Common window: {report['commonStartDate']} to {report['commonEndDate']}. "
             'Daily filter uses adjusted regular-session OHLC; 4H/8H retain the existing 04:00–20:00 ET session.', '',
             'Initially invested at the last completed 2025 candle close, matching the earlier backtest. '
             'Higher timeframe gates entry only; every exit uses the same 4H bearish crossover.', '']
    names = {'4h_alone': '4H alone', '4h_8h': '4H + 8H', '4h_1d': '4H + 1D'}
    for symbol, data in report['symbols'].items():
        lines += [f'### {symbol}', '',
                  '| Strategy | Return, no costs | Return, 0.10%/side | Return, 0.25%/side | Max drawdown, 0.10% | Losing entry trades | Missed rebound starts | Fully missed rebounds |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for strategy, cases in data['primary'].items():
            r = cases['cost10bps']; rebounds = r['rebounds']['5']
            lines.append(f"| {names[strategy]} | {cases['zeroCosts']['returnPct']:+.2f}% | "
                         f"{r['returnPct']:+.2f}% | {cases['cost25bps']['returnPct']:+.2f}% | "
                         f"{r['maxCloseDrawdownPct']:.2f}% | {r['losingSignalTrades']}/{r['closedSignalTrades']} | "
                         f"{rebounds['missedStarts']}/{rebounds['qualifyingWindows']} | "
                         f"{rebounds['completelyMissed']}/{rebounds['qualifyingWindows']} |")
        hold = data['primary']['4h_alone']['cost10bps']['buyAndHoldReturnPct']
        lines += ['', f'Buy-and-hold, before costs: {hold:+.2f}%.', '',
                  '#### Start-in-cash sensitivity (0.10% per side)', '',
                  '| Strategy | Return | Max drawdown | Executions |', '|---|---:|---:|---:|']
        for strategy, cases in data['startInCash'].items():
            r = cases['cost10bps']
            lines.append(f"| {names[strategy]} | {r['returnPct']:+.2f}% | {r['maxCloseDrawdownPct']:.2f}% | {r['executions']} |")
        lines += ['', f"#### Session sensitivity: {data['sessionSensitivityStart']} to {report['commonEndDate']}", '',
                  'Same shorter period for every row. Fully warmed daily bars; extended daily is built from four complete 4H bars.', '',
                  '| Strategy | Daily session | Return, 0.10%/side | Max drawdown |', '|---|---|---:|---:|']
        for mode in ('regularDailySameWindow', 'extendedDailySameWindow'):
            for strategy, cases in data[mode].items():
                if mode == 'extendedDailySameWindow' and strategy != '4h_1d':
                    continue
                r = cases['cost10bps']
                session = 'Regular' if mode == 'regularDailySameWindow' else 'Extended'
                lines.append(f"| {names[strategy]} | {session if strategy == '4h_1d' else '—'} | "
                             f"{r['returnPct']:+.2f}% | {r['maxCloseDrawdownPct']:.2f}% |")
        lines += ['']
    lines += ['## Interpretation', '']
    for symbol, data in report['symbols'].items():
        cases = data['primary']
        best = max(STRATEGIES, key=lambda k: cases[k]['cost10bps']['returnPct'])
        pair = max(STRATEGIES[1:], key=lambda k: cases[k]['cost10bps']['returnPct'])
        rankings = {cost: max(STRATEGIES, key=lambda k: cases[k][cost]['returnPct']) for cost in COSTS}
        cash_best = max(STRATEGIES, key=lambda k: data['startInCash'][k]['cost10bps']['returnPct'])
        lines += [f"{symbol}: {names[best]} has the highest main-test net return at 0.10% per side. "
                  f"The best pair by return is {names[pair]}. "
                  f"Cost-scenario winners: {', '.join(cost + ': ' + names[k] for cost, k in rankings.items())}. "
                  f"Starting in cash, the winner is {names[cash_best]}.", '']
        a, b = cases['4h_alone']['cost10bps'], cases['4h_1d']['cost10bps']
        lines += [f"{symbol} daily-filter trade-off versus 4H alone: "
                  f"{b['returnPct'] - a['returnPct']:+.2f} percentage points of return and "
                  f"{b['maxCloseDrawdownPct'] - a['maxCloseDrawdownPct']:+.2f} points of signed maximum drawdown "
                  '(a positive drawdown difference means a shallower decline).', '']
    lines += ['Fewer losing trades in absolute numbers can simply reflect fewer entries. '
              'Compare losing trades as a proportion of completed signal trades. '
              'Missed rebound starts include delayed entries and do not imply the entire rebound was untraded. '
              'Rebound windows are defined from 4H green crosses, so zero missed starts for 4H alone is by construction.', '',
              'These are tests of a specific higher-timeframe entry gate, with unchanged 4H exits. '
              'They do not measure every possible way to combine timeframes or establish universal predictive superiority. '
              'Session-matched and initial-position sensitivity results above show how dependent the findings are on those assumptions.', '',
              '## Definitions and limitations', '', *['- ' + text for text in report['definitions'].values()], '',
              *['- ' + text for text in report['limitations']], '',
              'Full execution, trade and equity ledgers for the primary 0.10% cases are retained in the adjacent JSON.']
    return '\n'.join(lines) + '\n'


def main():
    inputs, datasets = {}, {}
    for symbol in ('NVDA', 'SOXL'):
        paths = [Path(f'data/research/{symbol.lower()}-wavetrend.json'),
                 Path(f'data/history/{symbol.lower()}-daily.json')]
        intraday, daily = [json.loads(p.read_text()) for p in paths]
        if intraday.get('fetchErrors') or not daily.get('adjusted'):
            raise ValueError('Invalid or unadjusted source')
        for p in paths:
            inputs[str(p)] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        four = intraday['timeframes']['4h']['candles']
        eight = intraday['timeframes']['8h']['candles']
        one_day = daily_rows(daily['bars'])
        ext, excluded = extended_daily(four)
        datasets[symbol] = {'four': four, 'eight': eight, 'daily': one_day,
                            'extended': ext, 'excluded': excluded,
                            'intradayEndET': four[-1]['endET'], 'dailyEndET': one_day[-1]['endET']}
    end = min(min(d['dailyEndET'][:10], d['intradayEndET'][:10]) for d in datasets.values())
    ext_warm = max(next(c['endET'][:10] for c in d['extended'] if c['isWarm']) for d in datasets.values())
    sensitivity_start = (dt.date.fromisoformat(ext_warm) + dt.timedelta(days=1)).isoformat()
    report = {'schemaVersion': 1, 'researchOnly': True,
              'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'generatedET': dt.datetime.now(NY).isoformat(),
              'commonStartDate': '2026-01-01', 'commonEndDate': end,
              'parameters': {'WT': [10, 21, 4], 'warmupCandles': 100,
                             'initialValue': INITIAL, 'costPerSide': COSTS,
                             'primaryReboundThresholdPct': 5, 'reboundForward4hBars': 20},
              'definitions': {
                  'entry': '4H alone: bullish 4H while in cash. Pairs: bullish 4H AND last completed higher-timeframe WT bullish. If the higher timeframe confirms later while 4H remains bullish, entry is then allowed.',
                  'exit': 'All variants sell on a confirmed 4H bearish crossover. A higher-timeframe bearish turn alone does not trigger an exit.',
                  'timing': 'Decide at 4H close using only higher candles whose end timestamp is at or before that close; execute at the next available 4H open, never on the signal close.',
                  'costs': 'Apply identical friction to each buy and sell: 0%, 0.10%, or 0.25% per side. Initial inherited position and final open position are not forced-liquidated or charged entry/exit fees.',
                  'drawdown': 'Largest peak-to-trough portfolio decline measured at completed 4H closes, including initial capital. Does not capture intrabar drawdown.',
                  'falseSignals': 'Operational proxy: completed signal-entry trades with a negative net round-trip return. Excludes the inherited initial position and still-open trades; report losses/count, not just number of losses.',
                  'whipsaw': 'Subset of losing signal trades exited within four 4H bars of entry.',
                  'rebounds': 'For each 4H green cross with 20 subsequent bars available, label a rebound when close after those 20 bars is at least 5% above the next-bar open. Missed start: cash at that open. Completely missed: no held position during the entire window. Also report windows with nonpositive net strategy returns, and retain 2% and 10% threshold sensitivity. These labels never influence trades.',
                  'sessions': 'Main daily WT uses Massive adjusted regular-session OHLC released conservatively at 16:00 ET. Existing 4H/8H bars use extended hours. A separate same-window test compares regular and extended daily aggregation.'},
              'limitations': [
                  'Retrospective 2026 comparison, not an untouched prospective holdout or proof of predictive advantage. No rule, threshold or WT parameter was selected by maximizing returns.',
                  'The daily archive ends October 16 although intraday history reaches October 19. All variants stop October 16 for a common fully covered period.',
                  'Daily regular-session and extended intraday histories are different session definitions; the shorter session-matched sensitivity isolates this issue.',
                  'Extended-hours opens are idealized fills. Friction scenarios do not model varying spreads, market impact, liquidity, dividends, taxes or cash interest. SOXL leverage is embedded in its price series.',
                  'Rebound windows can overlap and are descriptive event counts, not independent statistical trials. A missed start may be entered later; complete misses are shown separately.',
                  'TradingView candle alignment and numerical equivalence remain unverified. Only fully completed stored bars are used.'],
              'inputs': inputs, 'symbols': {}}
    for symbol, d in datasets.items():
        args = d['four'], d['eight']
        report['symbols'][symbol] = {
            'coverage': {'intradayEndET': d['intradayEndET'], 'regularDailyEndET': d['dailyEndET'],
                         'regularDailyWarmupFirstEndET': next(c['endET'] for c in d['daily'] if c['isWarm']),
                         'extendedDailyWarmupFirstEndET': next(c['endET'] for c in d['extended'] if c['isWarm']),
                         'excludedIncompleteExtendedDailyDates': d['excluded']},
            'primary': evaluate(*args, d['daily'], '2026-01-01', end, include_ledgers=True),
            'startInCash': evaluate(*args, d['daily'], '2026-01-01', end, initially_long=False),
            'sessionSensitivityStart': sensitivity_start,
            'regularDailySameWindow': evaluate(*args, d['daily'], sensitivity_start, end),
            'extendedDailySameWindow': evaluate(*args, d['extended'], sensitivity_start, end)}
    OUTPUT.write_text(json.dumps(report, separators=(',', ':')) + '\n')
    REPORT.write_text(render_report(report))
    print(REPORT.read_text())


if __name__ == '__main__':
    main()
