"""Postmortem of frozen 4H WT trades; entry features use confirmed data only."""
import bisect
import hashlib
import json
import statistics
from pathlib import Path
from scripts.compare_wavetrend_timeframes import daily_rows, stamp
from scripts.research_wavetrend_companions import features

ROOT=Path('data/research')
PREFIX='wavetrend-losing-trade-diagnostics'


def summary(rows):
    losers=[r for r in rows if r['netReturnPct']<0]
    winners=[r for r in rows if r['netReturnPct']>0]
    return {'n':len(rows),'losses':len(losers),'wins':len(winners),
            'lossRatePct':round(100*len(losers)/len(rows),2) if rows else None,
            'meanReturnPct':round(statistics.mean(r['netReturnPct'] for r in rows),3) if rows else None}


def averages(rows):
    keys=['holding4hBars','wt1','wtSeparation','emaDistancePct','diSpread','adx14','atrPct','prior3barReturnPct','mfePct','maePct','entryGapPct']
    return {key:{'mean':round(statistics.mean(r[key] for r in rows if r[key] is not None),3),
                 'median':round(statistics.median(r[key] for r in rows if r[key] is not None),3)}
            for key in keys if any(r[key] is not None for r in rows)}


def analyze(symbol, baseline):
    path=ROOT/f'{symbol.lower()}-wavetrend.json'
    source=json.loads(path.read_text());four=features(source['timeframes']['4h']['candles'])
    eight=source['timeframes']['8h']['candles']
    daily=daily_rows(json.loads(Path(f'data/history/{symbol.lower()}-daily.json').read_text())['bars'])
    higher={'eight':eight,'daily':daily}
    ends={k:[stamp(c['endET']) for c in v] for k,v in higher.items()}
    indices={c['startET']:i for i,c in enumerate(four)}
    buys={e['executedAtET']:e for e in baseline['executionLedger'] if e['action']=='BUY'}
    by_end={c['endET']:i for i,c in enumerate(four)}
    rows=[]
    for trade in baseline['tradeLedger']:
        e=buys[trade['entryAtET']];i=by_end[e['confirmedAtET']];c=four[i]
        assert stamp(c['endET'])<=stamp(trade['entryAtET'])
        first,last=indices[trade['entryAtET']],indices[trade['exitAtET']]
        assert first==trade['entryIndex'] and last-first==trade['holding4hBars']
        held=four[first:last];p=trade['entryPrice'];gross=100*(trade['exitPrice']/p-1)
        r={**trade,'confirmedAtET':c['endET'],'wt1':c['wt1'],
           'wtSeparation':c['wt1']-c['wt2'],'emaDistancePct':100*(c['close']/c['ema20']-1),
           'diSpread':c['plusDI14']-c['minusDI14'],'adx14':c['adx14'],
           'adxRising':c['adx14Rising'],'atrPct':100*c['atr14']/c['close'],
           'prior3barReturnPct':100*(c['close']/four[i-3]['close']-1),
           'entryGapPct':100*(p/c['close']-1),'freshGreen':c['cross']=='bullish',
           'grossReturnPct':gross,'costFlippedLoss':gross>=0 and trade['netReturnPct']<0,
           'mfePct':100*(max([p,trade['exitPrice']]+[b['high'] for b in held])/p-1),
           'maePct':100*(min([p,trade['exitPrice']]+[b['low'] for b in held])/p-1),
           'half':'H1' if trade['entryAtET'][:10]<='2026-06-30' else 'H2'}
        for k,series in higher.items():
            j=bisect.bisect_right(ends[k],stamp(c['endET']))-1
            h=series[j] if j>=0 else None
            assert h and h['isWarm'] and stamp(h['endET'])<=stamp(c['endET'])
            r[k+'Bullish']=h['wt1']>h['wt2']
        # Descriptive future outcomes: never used as entry predictors.
        r['postExit20barReturnPct']=100*(four[last+19]['close']/trade['exitPrice']-1) if last+19<len(four) and four[last+19]['endET'][:10]<='2026-10-16' else None
        rows.append(r)
        assert r['maePct']<=gross+1e-8<=r['mfePct']+1e-8
    partitions={
        'WT <= -45':lambda r:r['wt1']<=-45,
        '-45 < WT < 0':lambda r:-45<r['wt1']<0,
        'WT >= 0':lambda r:r['wt1']>=0,
        'Price > EMA20':lambda r:r['emaDistancePct']>0,
        'Price <= EMA20':lambda r:r['emaDistancePct']<=0,
        '+DI > -DI':lambda r:r['diSpread']>0,
        '+DI <= -DI':lambda r:r['diSpread']<=0,
        'ADX rising':lambda r:r['adxRising'],
        'ADX flat/falling':lambda r:not r['adxRising'],
        '8H bullish':lambda r:r['eightBullish'],
        '8H bearish':lambda r:not r['eightBullish'],
        'Daily bullish':lambda r:r['dailyBullish'],
        'Daily bearish':lambda r:not r['dailyBullish'],
        'Entry Jan-Jun':lambda r:r['half']=='H1',
        'Entry Jul-Oct':lambda r:r['half']=='H2'}
    losers=[r for r in rows if r['netReturnPct']<0];winners=[r for r in rows if r['netReturnPct']>0]
    return {'overall':summary(rows),'entryGroups':{k:summary([r for r in rows if f(r)]) for k,f in partitions.items()},
            'loserAverages':averages(losers),'winnerAverages':averages(winners),
            'rapidLossesWithin4Bars':sum(r['holding4hBars']<=4 for r in losers),
            'costFlippedLosses':sum(r['costFlippedLoss'] for r in losers),
            'losersWithAtLeast1PctFavorableExcursion':sum(r['mfePct']>=1 for r in losers),
            'postExitLosersAvailable':sum(r['postExit20barReturnPct'] is not None for r in losers),
            'postExitLosersRebounding5Pct':sum(r['postExit20barReturnPct'] is not None and r['postExit20barReturnPct']>=5 for r in losers),
            'worstFive':sorted(rows,key=lambda r:r['netReturnPct'])[:5],'trades':rows}


def render(report):
    lines=['# Losing-trade diagnostics: 4H WaveTrend','','January 2–October 16, 2026; unchanged frozen NVDA/SOXL inputs. 0.10% friction on each side. Completed signal-entry trades only; inherited initial and still-open positions excluded from trade statistics.','','Entry groups use information confirmed before execution. All buckets were declared before inspecting this diagnostic run. These are retrospective descriptions; correlated observations, small groups and repeated exploration preclude treating them as proven predictors.','']
    for symbol,d in report['symbols'].items():
        lines += [f'## {symbol}','',f"Completed trades: {d['overall']['n']}; losing: {d['overall']['losses']}; winning: {d['overall']['wins']}.",
                  f"Losses exiting within four 4H bars: {d['rapidLossesWithin4Bars']}. Gross nonnegative trades made negative by costs: {d['costFlippedLosses']}. Losing trades with an intratrade high at least 1% above entry: {d['losersWithAtLeast1PctFavorableExcursion']}.",
                  f"After a losing exit, {d['postExitLosersRebounding5Pct']}/{d['postExitLosersAvailable']} eligible windows rose at least 5% by the close of 20 subsequent 4H bars. This is a future outcome, not an entry feature.",'',
                  '| Entry characteristic | Trades | Losses | Loss rate | Mean net trade return |','|---|---:|---:|---:|---:|']
        for name,v in d['entryGroups'].items():
            lines.append(f"| {name} | {v['n']} | {v['losses']} | {v['lossRatePct']}% | {v['meanReturnPct']}% |")
        lines += ['','| Metric | Losing-trade median | Winning-trade median |','|---|---:|---:|']
        for k,v in d['loserAverages'].items():
            lines.append(f"| {k} | {v['median']} | {d['winnerAverages'][k]['median']} |")
        lines += ['','| Worst trade entry ET | Exit ET | Net return | WT1 at signal | ADX | ATR % | Best intratrade gain % | Worst intratrade decline % |','|---|---|---:|---:|---:|---:|---:|---:|']
        for t in d['worstFive']:
            lines.append(f"| {t['entryAtET']} | {t['exitAtET']} | {t['netReturnPct']:.2f}% | {t['wt1']:.2f} | {t['adx14']:.2f} | {t['atrPct']:.2f} | {t['mfePct']:.2f} | {t['maePct']:.2f} |")
        lines += ['','Previously tested companion strategies (full portfolio backtests; not hypothetical deletion of losing trades):','',
                  '| Rule | Net return | Win rate | Wins / closed trades | Max close drawdown |','|---|---:|---:|---:|---:|']
        for name,v in report['testedCompanions'][symbol].items():
            lines.append(f"| {name} | {v['returnPct']:+.2f}% | {v['winRatePct']:.2f}% | {v['winningSignalTrades']}/{v['closedSignalTrades']} | {v['maxCloseDrawdownPct']:.2f}% |")
        lines += ['']
    lines += ['## Conclusions and next validation','',
              '- Rapid reversal is the strongest common descriptive pattern: most losses exited within four bars, whereas median winners lasted nine bars for NVDA and ten for SOXL. This explains whipsaw damage but does not identify bad trades in advance.',
              '- Entry WT level behaves differently by asset. NVDA entries at or below -45 lost 2/9 times, versus 30/46 outside that zone. SOXL entries at or below -45 lost 5/8 times, versus 23/45 outside. A universal oversold-only entry filter is not supported.',
              '- SOXL winners entered with materially higher median ADX and positive directional spread. Its previously tested DMI plus rising ADX filter improved win rate and drawdown while reducing total return. NVDA directional/EMA gates did not improve the prior full portfolio results.',
              '- Some losing trades first moved favorably. This supports investigating exits, but does not prove a particular stop or profit target: the existing ATR exit helped NVDA and hurt SOXL.',
              '- Costs explain three NVDA losses and zero SOXL losses by flipping nonnegative gross returns negative; price reversals, rather than costs alone, explain most losing trades.',
              '- Next controlled experiments should isolate oversold entry from overbought exit, retain the original strategy as comparator, and validate frozen rules on later untouched data. The prior zone strategy changed both entry and exit, so its benefit cannot be attributed to entry filtering alone.','',
              '## Interpretation limits','',
              '- A rapid losing exit describes a whipsaw after it happened; it is not information available when buying. The reported holding time is in available extended-hours 4H bars, not continuous clock hours.',
              '- MFE/MAE use highs/lows while held plus the exit fill itself. The entry candle is included; later high/low of the exit candle is excluded because execution is at its open. They do not establish executable stop/profit targets or high/low order.',
              '- Entry gap is the next-open move from the signal close. That exact fill gap is an execution observation, not known at the preceding signal close.',
              '- Mean trade returns are unweighted arithmetic averages, not portfolio returns. Winner and loser characteristics describe association, not causation.',
              '- Rejecting one original trade changes position timing and subsequent trades. Only the existing complete backtests support portfolio comparisons; entry-group loss rates do not establish filter profitability.',
              '- Already explored 2026 data; no independent validation. Comparing many characteristics creates selection risk. Asset-specific findings need later, untouched data with rules frozen first.',
              '- Existing baseline enters in a bullish WT state and exits on red crosses. The separately tested zone strategy changes both entry and exit; this diagnostic concerns the original baseline.',
              '- Source and code hashes and trade-level features are retained in the adjacent JSON. No live signals or UI were changed.','']
    return '\n'.join(lines)


def main():
    companion_path=ROOT/'wavetrend-companion-comparison.json'
    companion=json.loads(companion_path.read_text())
    report={'researchOnly':True,'startDate':'2026-01-01','endDate':'2026-10-16',
            'inputs':{},'symbols':{},'testedCompanions':{},'codeHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    report['inputs'][str(companion_path)]=hashlib.sha256(companion_path.read_bytes()).hexdigest()
    for symbol in ['NVDA','SOXL']:
        path=ROOT/f'{symbol.lower()}-wavetrend.json';digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest==companion['inputs'][str(path)]['sha256']
        report['inputs'][str(path)]=digest
        for p in [Path(f'data/history/{symbol.lower()}-daily.json'),Path('scripts/research_wavetrend_companions.py'),Path('scripts/compare_wavetrend_timeframes.py')]:
            report['inputs'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        primary=companion['symbols'][symbol]['primary']
        report['symbols'][symbol]=analyze(symbol,primary['baseline']['cost10bps'])
        assert report['symbols'][symbol]['overall']['losses']==primary['baseline']['cost10bps']['losingSignalTrades']
        report['testedCompanions'][symbol]={name:{k:costs['cost10bps'][k] for k in ['returnPct','winRatePct','winningSignalTrades','closedSignalTrades','maxCloseDrawdownPct']} for name,costs in primary.items()}
    (ROOT/(PREFIX+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/(PREFIX+'.md')).write_text(render(report))
    print(render(report))


if __name__=='__main__':main()
