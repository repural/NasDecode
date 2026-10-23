"""Four fixed stock experiments isolating oversold entries and ATR exits."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from scripts.compare_wavetrend_timeframes import COSTS, compact, simulate
from scripts.research_wavetrend_companions import features

ROOT=Path('data/research')
CONFIGS={'baseline':(False,None),'oversold_entry':(True,None),
         'atr_exit':(False,2),'oversold_and_atr':(True,2)}
NAMES={'baseline':'Original 4H WT','oversold_entry':'Oversold entry only',
       'atr_exit':'ATR exit only','oversold_and_atr':'Oversold entry + ATR exit'}


def oversold(c, index):
    return c.get('cross')=='bullish' and c.get('wt1') is not None and c['wt1']<=-45


def run(rows,start,end,initially_long=True,ledgers=False):
    output={}
    for name,(gate,atr) in CONFIGS.items():
        output[name]={}
        for label,cost in COSTS.items():
            r=simulate(rows,start_date=start,end_date=end,cost=cost,initially_long=initially_long,
                       entry_filter=oversold if gate else None,atr_multiplier=atr)
            output[name][label]=r if ledgers and label=='cost10bps' else compact(r)
    return output


def pct(v):return '—' if v is None else f'{v:+.2f}%'


def buy_and_hold(rows,start,end):
    selected=[c for c in rows if c['startET'][:10]>=start and c['endET'][:10]<=end]
    reference=next(c for c in reversed(rows) if c['startET'][:10]<start)
    peak=10000;drawdown=0
    for c in selected:
        value=10000*c['close']/reference['close']
        peak=max(peak,value);drawdown=min(drawdown,100*(value/peak-1))
    return {'returnPct':round(100*(value/10000-1),2),'finalValue':round(value,2),
            'maxCloseDrawdownPct':round(drawdown,2),'referenceAtET':reference['endET'],
            'lastMarkET':selected[-1]['endET'],
            'costConvention':'Same inherited starting shares; no trades or forced sale, so no transaction costs.'}


def render(r):
    lines=[f"# {r['design']['symbol']}: oversold entries and ATR exits",'','Fixed comparison: January 2–October 16, 2026; identical frozen adjusted Massive 4H input. Primary results use $10,000 inherited stock at the last 2025 close, next available 4H-open execution, 0.10% costs per buy/sell, and end-period marking without forced liquidation.','',
           '## Primary comparison','','| Strategy | Net return | Final value | Max close drawdown | Win rate | Wins/closed | Profit factor | Missed/delayed rebound starts | ATR exits |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,costs in r['primary'].items():
        v=costs['cost10bps'];b=v['rebounds']['5'];wr='—' if v['winRatePct'] is None else f"{v['winRatePct']:.2f}%"
        pf='—' if v['netProfitFactor'] is None else f"{v['netProfitFactor']:.2f}"
        lines.append(f"| {NAMES[name]} | {pct(v['returnPct'])} | ${v['finalValue']:,.2f} | {pct(v['maxCloseDrawdownPct'])} | {wr} | {v['winningSignalTrades']}/{v['closedSignalTrades']} | {pf} | {b['missedStarts']}/{b['qualifyingWindows']} | {v['atrExitExecutions']} |")
    if r.get('buyAndHold'):
        b=r['buyAndHold']
        lines.append(f"| Buy and hold | {pct(b['returnPct'])} | ${b['finalValue']:,.2f} | {pct(b['maxCloseDrawdownPct'])} | — | — | — | — | — |")
        lines += ['', 'Buy-and-hold uses the identical inherited starting shares and ending mark. It makes no trades and is not sold at the end, so no transaction costs apply. Win rate is not applicable.']
    lines += ['','## Sensitivities','','| Strategy | No costs | 0.25%/side | Full period starting cash | Jan–Jun return | Jul–Oct return | Exposure |','|---|---:|---:|---:|---:|---:|---:|']
    for name,costs in r['primary'].items():
        v=costs['cost10bps']
        lines.append(f"| {NAMES[name]} | {pct(costs['zeroCosts']['returnPct'])} | {pct(costs['cost25bps']['returnPct'])} | {pct(r['startInCash'][name]['cost10bps']['returnPct'])} | {pct(r['firstHalf'][name]['cost10bps']['returnPct'])} | {pct(r['secondHalf'][name]['cost10bps']['returnPct'])} | {v['exposure4hBarsPct']:.2f}% |")
    lines += ['','## Final open positions','']
    for name,costs in r['primary'].items():
        v=costs['cost10bps'];p=v.get('openPositionAtFinalMark')
        lines.append(f"- {NAMES[name]}: "+(f"open since {p['entryAtET']}; marked net return {pct(p['netMarkReturnPct'])}." if p else v['finalPosition']+'.'))
    lines += ['','## Frozen rules','']+['- '+v for v in r['design']['rules'].values()]
    lines += ['','## Definitions and limitations','',
              '- The entry-only strategy sells on every new red cross, regardless of WT level. It does not wait for an overbought red cross. The combined strategy sells on a red cross OR an ATR breach.',
              '- ATR(14) uses Wilder smoothing. Trail = max(previous trail, highest completed high since entry - 2 × current ATR14). Trigger only when a completed close is below the trail; fill at the next open, never at the stop price. After ATR exit, wait for a new green cross; oversold variants also require that new cross to qualify at WT1 ≤ -45.',
              '- Initial inherited stock is identical in every primary row and can be held before the first qualifying entry. Start-in-cash sensitivity removes this inherited holding.',
              '- Win rate and profit factor use completed signal-entry round trips, including costs. Inherited and still-open positions are excluded from trade statistics, but their gains/losses are included in portfolio return and drawdown.',
              '- Maximum drawdown is measured at completed 4H closes, not intrabar lows. Extended-hours fills are idealized and fixed costs do not model varying spreads/impact. No dividends, taxes or cash interest.',
              '- Rebounds use original 4H green crosses followed by at least +5% from next open to close 20 bars later. Windows may overlap; zero original-baseline missed starts is by construction. Missed starts include later entries.',
              '- Half-year runs initialize independently with inherited stock; their returns do not concatenate. These are exploratory diagnostics, not holdouts.',
              '- The -45 entry threshold and 2×ATR14 exit were chosen before this run, based on earlier analysis of this same 2026 period. No grid search was performed. These results are not independent validation; all rules require testing on later untouched data.',
              '- Buy-and-hold on the inherited-position convention returned '+pct(r['primary']['baseline']['cost10bps']['buyAndHoldReturnPct'])+' before costs. TradingView candle/numerical equivalence remains unverified.',
              '- The adjacent JSON contains the frozen design, source/code hashes, cost scenarios, full primary ledgers, cash-start and half-year diagnostics.','']
    if r['design']['symbol']=='MU':
        lines += ['MU data coverage: all 2026 evaluation sessions have complete 4H/8H bucket coverage. The December 8, 2025 04:00–08:00 ET warm-up bucket is excluded by the existing collector rule; it is not synthesized. Sparse five-minute source intervals and short warm-up sessions are documented in mu-wavetrend-coverage.json.','']
    if r['design']['symbol']=='GOOGL':
        lines += ['GOOGL Class A data coverage is audited against existing US exchange trading dates. No GOOG or NVDA prices enter GOOGL calculations. Warm-up short sessions and sparse five-minute source intervals are disclosed in googl-wavetrend-coverage.json.','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--symbol',choices=['NVDA','SOXL','MU','GOOGL'],default='NVDA')
    symbol=parser.parse_args().symbol
    prefix=symbol.lower()+'-wavetrend-oversold-atr'
    previous_path=ROOT/('mu-wavetrend-companion-comparison.json' if symbol=='MU' else 'wavetrend-companion-comparison.json')
    previous=None if symbol=='GOOGL' else json.loads(previous_path.read_text())
    design={'startDate':'2026-01-01','endDate':'2026-10-16','symbol':symbol,'timeframe':'4h',
            'entryWT1Threshold':-45,'atrLength':14,'atrMultiplier':2,'costPerSide':COSTS,'optimization':False,
            'rules':{
                'baseline':'Original: enter while completed WT1 > WT2; exit on any confirmed red crossover.',
                'oversold_entry':'Oversold entry: enter only on a new confirmed green cross with WT1 ≤ -45; exit on any confirmed red crossover.',
                'atr_exit':'ATR exit: original entries; exit on any red cross OR completed-close ATR trailing breach.',
                'oversold_and_atr':'Combined: oversold entries; exit on any red cross OR completed-close ATR trailing breach.'}}
    design_path=ROOT/(prefix+'-design.json')
    if design_path.exists():assert json.loads(design_path.read_text())==design
    else:design_path.write_text(json.dumps(design,indent=2)+'\n')
    source_path=ROOT/(symbol.lower()+'-wavetrend.json');digest=hashlib.sha256(source_path.read_bytes()).hexdigest()
    if previous is not None:
        assert digest==previous['inputs'][str(source_path)]['sha256'],'Prior input changed'
    source=json.loads(source_path.read_text());assert not source.get('fetchErrors')
    if symbol=='MU':
        from scripts.audit_mu_wavetrend import audit
        audit(source,json.loads(Path('data/history/mu-daily.json').read_text()))
    if symbol=='GOOGL':
        from scripts.audit_googl_wavetrend import audit
        audit(source,json.loads(Path('data/history/nvda-daily.json').read_text()))
    rows=features(source['timeframes']['4h']['candles']);start,end=design['startDate'],design['endDate']
    report={'researchOnly':True,'generatedUTC':dt.datetime.now(dt.timezone.utc).isoformat(),'design':design,
            'inputs':{str(source_path):digest},'codeHashes':{},'buyAndHold':buy_and_hold(rows,start,end),
            'primary':run(rows,start,end,ledgers=True),'startInCash':run(rows,start,end,False),
            'firstHalf':run(rows,start,'2026-06-30'),'secondHalf':run(rows,'2026-07-01',end)}
    assert report['buyAndHold']['returnPct']==report['primary']['baseline']['cost10bps']['buyAndHoldReturnPct']
    if symbol=='GOOGL':
        from scripts.backtest_wavetrend import simulate as independent_simulate
        for label,cost in COSTS.items():
            check=independent_simulate([c for c in rows if c['endET'][:10]<=end],friction=cost)
            actual=report['primary']['baseline'][label]
            assert check['finalValue']==actual['finalValue']
            assert check['numberOfExecutions']==actual['executions']
    for p in [Path(__file__),Path('scripts/compare_wavetrend_timeframes.py'),Path('scripts/research_wavetrend_companions.py')]:
        report['codeHashes'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    for key in ['primary','startInCash','firstHalf','secondHalf']:
        for name in ['baseline','atr_exit']:
            if previous is None:continue
            old=previous['symbols'][symbol][key][name]
            for label in COSTS:
                new=report[key][name][label]
                for metric in ['returnPct','finalValue','executions','maxCloseDrawdownPct','winningSignalTrades','closedSignalTrades']:
                    assert old[label][metric]==new[metric],f'Prior result changed: {key} {name} {metric}'
    ends={c['endET']:c for c in rows}
    close=next(c['close'] for c in reversed(rows) if c['endET'][:10]<=end)
    for name,costs in report['primary'].items():
        v=costs['cost10bps']
        if name.startswith('oversold'):
            for e in v['executionLedger']:
                c=ends[e['confirmedAtET']]
                if e['action']=='BUY':assert oversold(c,0)
        if v['unclosedSignalTrade']:
            e=v['executionLedger'][-1];assert e['action']=='BUY'
            v['openPositionAtFinalMark']={'entryAtET':e['executedAtET'],
                                         'netMarkReturnPct':round(100*((1-.001)*close/e['executionPrice']-1),2)}
    (ROOT/(prefix+'.json')).write_text(json.dumps(report,separators=(',',':'))+'\n')
    (ROOT/(prefix+'.md')).write_text(render(report))
    print(render(report))


if __name__=='__main__':main()
