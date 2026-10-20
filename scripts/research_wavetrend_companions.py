"""Frozen single-addition experiments around 4H WT. Research only, no optimization."""
import datetime as dt
import argparse
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.compare_wavetrend_timeframes import simulate, compact, COSTS
from scripts.research_nvda_wavetrend import ema

ROOT = Path('data/research')
DESIGN = ROOT / 'wavetrend-companion-design.json'
OUTPUT = ROOT / 'wavetrend-companion-comparison.json'
REPORT = ROOT / 'wavetrend-companion-comparison.md'
NAMES = {'baseline': '4H WT alone', 'ema20': 'WT + EMA20', 'dmi14': 'WT + DMI14',
         'dmi_adx': 'WT + DMI14 + rising ADX14', 'atr_exit': 'WT + ATR14 trailing exit',
         'price_confirmation': 'WT + price confirmation'}
RULES = {
    'baseline': 'Enter while completed 4H WT1 > WT2; exit on completed 4H bearish crossover.',
    'ema20': 'Baseline entry AND completed 4H close > EMA(close,20). Baseline WT exit.',
    'dmi14': 'Baseline entry AND Wilder +DI(14) > -DI(14). Baseline WT exit.',
    'dmi_adx': 'DMI14 entry condition AND ADX(14) > its previous completed 4H value. Baseline WT exit.',
    'atr_exit': 'Baseline entries. Sell at next 4H open after either WT red cross or close < trailing stop. '
                'Stop = max(previous stop, highest completed high since entry - 2 * ATR(14)). '
                'After an ATR exit wait for a new WT green cross before re-entry; no intrabar stop execution.',
    'price_confirmation': 'Baseline entry AND close strictly above the most recent WT green crossover candle high '
                          'in the current bullish phase. Re-evaluate at each completed close; red cross cancels setup. Baseline WT exit.'}


def rma(values, length):
    """Wilder smoothing seeded with the first length valid observations' SMA."""
    out, seed, prior = [], [], None
    for value in values:
        if value is None:
            out.append(None)
            continue
        if prior is None:
            seed.append(value)
            if len(seed) == length:
                prior = sum(seed) / length
        else:
            prior = (prior * (length - 1) + value) / length
        out.append(prior)
    return out


def features(candles):
    tr, positive, negative = [], [], []
    for i, c in enumerate(candles):
        old = candles[i - 1] if i else c
        tr.append(max(c['high'] - c['low'], abs(c['high'] - old['close']), abs(c['low'] - old['close'])))
        up, down = c['high'] - old['high'], old['low'] - c['low']
        positive.append(up if up > down and up > 0 else 0)
        negative.append(down if down > up and down > 0 else 0)
    atr, plus, minus = rma(tr, 14), rma(positive, 14), rma(negative, 14)
    pdi = [100 * p / a if a else (0 if a == 0 else None) for p, a in zip(plus, atr)]
    mdi = [100 * m / a if a else (0 if a == 0 else None) for m, a in zip(minus, atr)]
    dx = [100 * abs(p - m) / (p + m) if p is not None and p + m else
          (0 if p is not None else None) for p, m in zip(pdi, mdi)]
    adx, average = rma(dx, 14), ema([c['close'] for c in candles], 20)
    output, green_high = [], None
    for i, c in enumerate(candles):
        if c.get('cross') == 'bullish':
            green_high = c['high']
        elif c.get('cross') == 'bearish':
            green_high = None
        output.append({**c, 'ema20': average[i], 'atr14': atr[i],
                       'plusDI14': pdi[i], 'minusDI14': mdi[i], 'adx14': adx[i],
                       'adx14Rising': bool(i and adx[i] is not None and adx[i - 1] is not None
                                           and adx[i] > adx[i - 1]),
                       'wtGreenHigh': green_high})
    return output


def entry_allowed(name, c, index):
    if name == 'ema20':
        return c['close'] > c['ema20']
    if name in ('dmi14', 'dmi_adx'):
        directional = c.get('plusDI14') is not None and c['plusDI14'] > c['minusDI14']
        return directional and (name != 'dmi_adx' or c['adx14Rising'])
    if name == 'price_confirmation':
        return c['wtGreenHigh'] is not None and c['close'] > c['wtGreenHigh']
    return True


def run(candles, start, end, initially_long=True, ledgers=False):
    result = {}
    for name in NAMES:
        result[name] = {}
        for label, cost in COSTS.items():
            callback = None if name in ('baseline', 'atr_exit') else lambda c, i, n=name: entry_allowed(n, c, i)
            stats = simulate(candles, start_date=start, end_date=end, cost=cost,
                             initially_long=initially_long, entry_filter=callback,
                             atr_multiplier=2 if name == 'atr_exit' else None)
            result[name][label] = stats if ledgers and label == 'cost10bps' else compact(stats)
    return result


def signed(value):
    return f'{value:+.2f}%'


def render(report):
    lines = ['# 4H WaveTrend companion experiments', '',
             f"Period: {report['startDate']}–{report['endDate']}. Frozen single-addition rules; WT 10/21/4.", '',
             'Research only. All fills use the next available 4H open. Main results include 0.10% friction per buy/sell. '
             'The identical inherited $10,000 position starts at the last completed 2025 close. '
             'No live score, signal or chart behavior is changed.', '', '## Main results', '']
    for symbol, data in report['symbols'].items():
        base = data['primary']['baseline']['cost10bps']
        lines += [f'### {symbol}', '',
                  '| Strategy | Net return | Max close drawdown | Win rate | Wins / closed trades | Profit factor | Missed/delayed rebound starts |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for name, cases in data['primary'].items():
            s = cases['cost10bps']; rebound = s['rebounds']['5']
            pf = f"{s['netProfitFactor']:.2f}" if s['netProfitFactor'] is not None else 'undefined'
            win = f"{s['winRatePct']:.2f}%" if s['winRatePct'] is not None else '—'
            lines.append(f"| {NAMES[name]} | {signed(s['returnPct'])} | {s['maxCloseDrawdownPct']:.2f}% | "
                         f"{win} | {s['winningSignalTrades']}/{s['closedSignalTrades']} | {pf} | "
                         f"{rebound['missedStarts']}/{rebound['qualifyingWindows']} |")
        lines += ['', '#### Payoff, costs and turnover', '',
                  '| Strategy | Average winner | Average loser | Mean closed-trade return | Executions | Return, no costs | Return, 0.25%/side |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for name, cases in data['primary'].items():
            s = cases['cost10bps']
            fmt = lambda x: signed(x) if x is not None else '—'
            lines.append(f"| {NAMES[name]} | {fmt(s['averageWinPct'])} | {fmt(s['averageLossPct'])} | "
                         f"{fmt(s['meanClosedTradeReturnPct'])} | {s['executions']} | "
                         f"{signed(cases['zeroCosts']['returnPct'])} | {signed(cases['cost25bps']['returnPct'])} |")
        lines += ['', '#### Period and initial-position diagnostics (0.10%/side)', '',
                  '| Strategy | Jan–Jun return | Jan–Jun win rate | Jul–Oct return | Jul–Oct win rate | Full period starting in cash |',
                  '|---|---:|---:|---:|---:|---:|']
        for name in NAMES:
            first = data['firstHalf'][name]['cost10bps']; second = data['secondHalf'][name]['cost10bps']
            cash = data['startInCash'][name]['cost10bps']
            lines.append(f"| {NAMES[name]} | {signed(first['returnPct'])} | {first['winRatePct']}% | "
                         f"{signed(second['returnPct'])} | {second['winRatePct']}% | {signed(cash['returnPct'])} |")
        both = [NAMES[k] for k, v in data['primary'].items() if k != 'baseline'
                and v['cost10bps']['returnPct'] > base['returnPct']
                and v['cost10bps']['winRatePct'] is not None
                and v['cost10bps']['winRatePct'] > base['winRatePct']]
        lines += ['', 'Variants improving both main-period return and win rate: ' + (', '.join(both) if both else 'none') + '.', '']
    lines += ['## Frozen rules', '', *[f'- **{NAMES[k]}:** {v}' for k, v in RULES.items()], '',
              '## Interpretation and limitations', '', *['- ' + text for text in report['limitations']], '',
              '## Metric definitions', '', *['- ' + text for text in report['metricDefinitions']], '',
              'The adjacent JSON contains the full primary 0.10% execution, closed-trade and equity ledgers, '
              'all three cost cases, the two subperiods and start-in-cash sensitivity.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', nargs='+', choices=('NVDA', 'SOXL', 'MU'), default=['NVDA', 'SOXL'])
    parser.add_argument('--comparison-prefix', default='wavetrend-timeframe-comparison')
    parser.add_argument('--output-prefix', default='wavetrend-companion-comparison')
    args = parser.parse_args()
    previous = json.loads((ROOT / (args.comparison_prefix + '.json')).read_text())
    design_path = ROOT / (args.output_prefix.replace('-comparison', '-design') + '.json')
    output = ROOT / (args.output_prefix + '.json')
    report_path = output.with_suffix('.md')
    start, end = previous['commonStartDate'], previous['commonEndDate']
    # Freeze parameters and definitions before any simulation, never pick a best parameter from results.
    design = {'frozenAtET': dt.datetime.now(ZoneInfo('America/New_York')).isoformat(),
              'startDate': start, 'endDate': end, 'rules': RULES,
              'WT': [10, 21, 4], 'emaLength': 20, 'wilderLength': 14,
              'atrMultiplier': 2, 'costPerSide': COSTS, 'combinationSearch': False}
    if design_path.exists():
        frozen = json.loads(design_path.read_text())
        if {k: v for k, v in frozen.items() if k != 'frozenAtET'} != {k: v for k, v in design.items() if k != 'frozenAtET'}:
            raise ValueError('Frozen design changed; use a separately versioned experiment')
        design = frozen
    else:
        design_path.write_text(json.dumps(design, indent=2) + '\n')
    report = {'schemaVersion': 1, 'researchOnly': True, 'design': design,
              'startDate': start, 'endDate': end, 'sourceCommit': previous['sourceCommit'],
              'metricDefinitions': [
                  'Win rate = positive-net-return completed signal-entry round trips / all completed signal-entry round trips. Breakevens count in the denominator. Inherited initial and still-open positions are excluded from trade statistics but included in portfolio return and drawdown.',
                  'Profit factor = sum of positive net dollar P&L / absolute sum of negative net dollar P&L over completed signal-entry trades. All entry/exit friction is included; no-loss denominator is reported as undefined, never fabricated.',
                  'Average winner/loser and mean trade return are arithmetic net percentage returns on completed signal-entry trades. Position sizes vary as portfolio wealth compounds.',
                  'Maximum drawdown uses completed 4H portfolio marks and can understate intrabar declines.',
                  'Rebounds and missed starts retain the previous comparison definition: a 4H green cross followed by at least +5% over the next 20 bars. A cash position at the first executable open is a missed/delayed start. Windows may overlap; zero baseline misses is by construction.'],
              'limitations': [
                  'All 2026 results are exploratory. The period has already been examined; the half-year diagnostics are not untouched holdouts. No claim of validated future improvement is made.',
                  'Each addition is tested alone against the same baseline. DMI plus rising ADX is a predeclared directional-strength variant; there is no search over periods, thresholds or stacked winners.',
                  'Entry gates are re-evaluated while WT remains bullish and can delay entries. Rejected setups may later enter if the gate turns favorable before WT turns bearish.',
                  'The ATR test uses completed-close breaches and next-open fills, not idealized fills at the stop. Intrabar breaches are ignored. ATR exits require a new WT green cross before re-entry.',
                  'Each subperiod is an independently initialized diagnostic with the same inherited-position convention; subperiod returns do not concatenate to the full-period result.',
                  'Historic extended-hours opens are idealized fills. Costs are fixed friction scenarios, not a full liquidity/impact model. No cash interest, dividends or taxes are modeled.',
                  'The source is the frozen adjusted Massive 4H archive used in the prior comparison. WT and companion indicator numerical equivalence to TradingView is not independently verified.'],
              'inputs': {}, 'symbols': {}}
    for symbol in args.symbols:
        path = ROOT / f'{symbol.lower()}-wavetrend.json'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != previous['inputs'][str(path)]['sha256']:
            raise ValueError('Frozen input changed: ' + str(path))
        source = json.loads(path.read_text())
        if source.get('fetchErrors'):
            raise ValueError('Incomplete source')
        rows = features(source['timeframes']['4h']['candles'])
        report['inputs'][str(path)] = {'sha256': digest}
        report['symbols'][symbol] = {
            'primary': run(rows, start, end, ledgers=True),
            'startInCash': run(rows, start, end, initially_long=False),
            'firstHalf': run(rows, start, '2026-06-30'),
            'secondHalf': run(rows, '2026-07-01', end)}
        old = previous['symbols'][symbol]['primary']['4h_alone']['cost10bps']
        new = report['symbols'][symbol]['primary']['baseline']['cost10bps']
        if any(old[k] != new[k] for k in ('finalValue', 'executions', 'maxCloseDrawdownPct')):
            raise ValueError('Baseline does not reproduce previous comparison')
    output.write_text(json.dumps(report, separators=(',', ':')) + '\n')
    report_path.write_text(render(report))
    print(report_path.read_text())


if __name__ == '__main__':
    main()
