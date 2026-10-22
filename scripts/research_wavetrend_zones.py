"""Frozen 4H/8H zone-cross experiment on the prior NVDA/SOXL input snapshots."""
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.compare_wavetrend_timeframes import COSTS, compact, simulate

ROOT = Path('data/research')
PREFIX = 'wavetrend-zone-cross-comparison'
RULES = {'baseline': None, 'near45': 45, 'strict53': 53}


def run(four, signal, start, end, initially_long=True, ledgers=False):
    result = {}
    for name, level in RULES.items():
        result[name] = {}
        for label, cost in COSTS.items():
            r = simulate(four, signal=signal, start_date=start, end_date=end,
                         initially_long=initially_long, cost=cost, zone_threshold=level)
            result[name][label] = r if ledgers and label == 'cost10bps' else compact(r)
    return result


def pct(x):
    return '—' if x is None else f'{x:+.2f}%'


def render(report):
    lines = ['# WaveTrend zone-cross simulation', '',
             'Fixed evaluation window: January 2–October 16, 2026. Prior adjusted Massive input snapshots; no parameter optimization.', '',
             'Baseline uses the prior bullish-state entry and red-cross exit. Zone rules require a NEW green cross with WT1 ≤ −45 (strict: −53) to buy, and a NEW red cross with WT1 ≥ +45 (strict: +53) to sell. Crosses outside these zones are ignored; positions persist until an eligible opposite cross. More extreme readings qualify. WT1 is measured at the completed crossover candle close.', '',
             'All variants start with the same inherited $10,000 stock position at the last completed 2025 close. Decisions use completed 4H or 8H candles; execute at the next available 4H open with 0.10% friction each side. Final positions are marked, not forced liquidated.', '']
    names = {'baseline':'Original WT','near45':'Zone ±45','strict53':'Zone ±53'}
    for symbol, data in report['symbols'].items():
        lines += [f'## {symbol}', '',
                  '| Timeframe | Rule | Net return | Max close drawdown | Win rate | Wins/closed | Losing trades | Missed/delayed rebound starts | Fully missed rebounds | Final position |',
                  '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
        for tf, cases in data.items():
            for name, costs in cases['primary'].items():
                r=costs['cost10bps']; b=r['rebounds']['5']; n=b['qualifyingWindows']
                lines.append(f"| {tf.upper()} | {names[name]} | {pct(r['returnPct'])} | {pct(r['maxCloseDrawdownPct'])} | {pct(r['winRatePct'])} | {r['winningSignalTrades']}/{r['closedSignalTrades']} | {r['losingSignalTrades']} | {b['missedStarts']}/{n} | {b['completelyMissed']}/{n} | {r['finalPosition']} |")
        lines += ['', 'Open signal-entry positions at the final mark (entry cost included; no hypothetical exit cost):', '']
        for tf, cases in data.items():
            for name, costs in cases['primary'].items():
                position=costs['cost10bps'].get('openPositionAtFinalMark')
                if position:
                    lines.append(f"- {tf.upper()} {names[name]}: entered {position['entryAtET']}, marked return {pct(position['netMarkReturnPct'])}. Included in portfolio return/drawdown, excluded from completed-trade win rate.")
        lines += ['', '### Cost and initial-position sensitivity', '',
                  '| Timeframe | Rule | No costs | 0.25%/side | Start in cash, 0.10%/side | Jan–Jun return | Jul–Oct return | Exposure |',
                  '|---|---|---:|---:|---:|---:|---:|---:|']
        for tf, cases in data.items():
            for name, costs in cases['primary'].items():
                r=costs['cost10bps']
                lines.append(f"| {tf.upper()} | {names[name]} | {pct(costs['zeroCosts']['returnPct'])} | {pct(costs['cost25bps']['returnPct'])} | {pct(cases['startInCash'][name]['cost10bps']['returnPct'])} | {pct(cases['firstHalf'][name]['cost10bps']['returnPct'])} | {pct(cases['secondHalf'][name]['cost10bps']['returnPct'])} | {r['exposure4hBarsPct']:.2f}% |")
        hold=data['4h']['primary']['baseline']['cost10bps']['buyAndHoldReturnPct']
        lines += ['', f'Buy and hold before costs: {pct(hold)}.', '']
    lines += ['## Definitions and limitations', '',
              '- Win rate and losing trades use completed signal-entry round trips after costs. The inherited initial position and still-open trades affect portfolio results but are excluded from trade statistics. Small samples can make win rates misleading.',
              '- Maximum drawdown is measured at 4H portfolio closes, so intrabar declines can be larger.',
              '- A rebound is a 4H green cross followed by at least 5% from next open to close 20 bars later. Missed starts include delays; windows can overlap. Original 4H has zero missed starts by construction.',
              '- Subperiods are independently initialized with inherited positions. They are exploratory diagnostics, not holdouts or concatenating segments.',
              '- Ignoring red crosses outside the upper zone can keep a position invested through deep declines. Ignoring green crosses outside the lower zone can leave cash uninvested during rallies.',
              '- Extended-hours 04:00–20:00 ET candles and next-open fills are retained from the prior experiment. Fixed cost scenarios do not model varying spreads, impact, taxes, dividends or cash interest. TradingView numerical equivalence is unverified.',
              '- These are retrospective 2026 results using the frozen earlier comparison period, not current live signals. No thresholds were selected after inspecting these results.', '',
              'The adjacent JSON retains input/code hashes, all three costs, full primary execution/trade/equity ledgers, initial-position sensitivities and independent half-year diagnostics.', '']
    return '\n'.join(lines)


def main():
    previous=json.loads((ROOT/'wavetrend-timeframe-comparison.json').read_text())
    design={'startDate':'2026-01-01','endDate':'2026-10-16','zoneThresholds':[45,53],
            'zoneMeasure':'WT1 at confirmed crossover close; inclusive one-sided zones',
            'entry':'fresh bullish crossover AND WT1 <= -threshold',
            'exit':'fresh bearish crossover AND WT1 >= threshold',
            'timeframes':['4h','8h'],'symbols':['NVDA','SOXL'],
            'costPerSide':COSTS,'execution':'next available 4H open','optimization':False}
    path=ROOT/'wavetrend-zone-cross-design.json'
    if path.exists():
        assert json.loads(path.read_text())==design, 'Frozen design changed'
    else:path.write_text(json.dumps(design,indent=2)+'\n')
    report={'design':design,'researchOnly':True,'generatedUTC':dt.datetime.now(dt.timezone.utc).isoformat(),
            'inputs':{},'codeHashes':{},'symbols':{}}
    for p in [Path(__file__),Path('scripts/compare_wavetrend_timeframes.py')]:
        report['codeHashes'][str(p.name)]=hashlib.sha256(p.read_bytes()).hexdigest()
    for symbol in design['symbols']:
        path=ROOT/f'{symbol.lower()}-wavetrend.json'
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest==previous['inputs'][str(path)]['sha256'], 'Previous input snapshot changed'
        source=json.loads(path.read_text());assert not source.get('fetchErrors')
        report['inputs'][str(path)]={'sha256':digest}
        four=source['timeframes']['4h']['candles'];report['symbols'][symbol]={}
        for tf in design['timeframes']:
            signal=source['timeframes'][tf]['candles']
            cases={'primary':run(four,signal,design['startDate'],design['endDate'],ledgers=True),
                   'startInCash':run(four,signal,design['startDate'],design['endDate'],initially_long=False),
                   'firstHalf':run(four,signal,design['startDate'],'2026-06-30'),
                   'secondHalf':run(four,signal,'2026-07-01',design['endDate'])}
            last_close=next(c['close'] for c in reversed(four) if c['endET'][:10]<=design['endDate'])
            source_by_end={c['endET']:c for c in signal}
            for name,level in RULES.items():
                if level is None:continue
                for execution in cases['primary'][name]['cost10bps']['executionLedger']:
                    candle=source_by_end[execution['signalConfirmedAtET']]
                    buying=execution['action']=='BUY'
                    assert candle['cross']==('bullish' if buying else 'bearish')
                    assert candle['wt1']<=-level if buying else candle['wt1']>=level
                    assert dt.datetime.fromisoformat(candle['endET'])<=dt.datetime.fromisoformat(execution['executedAtET'])
            for costs in cases['primary'].values():
                primary=costs['cost10bps']
                if primary['unclosedSignalTrade']:
                    entry=primary['executionLedger'][-1]
                    assert entry['action']=='BUY'
                    primary['openPositionAtFinalMark']={'entryAtET':entry['executedAtET'],
                        'netMarkReturnPct':round(100*((1-.001)*last_close/entry['executionPrice']-1),2)}
            old=previous['symbols'][symbol]['primary'][tf+'_alone']['cost10bps']
            new=cases['primary']['baseline']['cost10bps']
            for key in ('finalValue','executions','maxCloseDrawdownPct','losingSignalTrades'):
                assert old[key]==new[key],f'Baseline changed: {symbol} {tf} {key}'
            report['symbols'][symbol][tf]=cases
    (ROOT/(PREFIX+'.json')).write_text(json.dumps(report,separators=(',',':'))+'\n')
    (ROOT/(PREFIX+'.md')).write_text(render(report))
    print(render(report))


if __name__=='__main__':main()
