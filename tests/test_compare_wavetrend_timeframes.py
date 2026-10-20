import datetime as dt
import json
import unittest
from pathlib import Path
from scripts.backtest_wavetrend import simulate as prior_simulate
from scripts.compare_wavetrend_timeframes import simulate, daily_rows, extended_daily


def candle(day, hour, close=100, cross=None, up=True, opening=100):
    start = dt.datetime.fromisoformat(f'{day}T{hour:02}:00:00-05:00')
    return {'startET': start.isoformat(), 'endET': (start + dt.timedelta(hours=4)).isoformat(),
            'open': opening, 'high': max(opening, close), 'low': min(opening, close),
            'close': close, 'isWarm': True, 'wt1': 1 if up else -1, 'wt2': 0, 'cross': cross}


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.four = [candle('2025-12-31', 16),
                     candle('2026-01-02', 4, cross='bullish'),
                     candle('2026-01-02', 8),
                     candle('2026-01-02', 12),
                     candle('2026-01-02', 16),
                     candle('2026-01-05', 4)]

    def test_future_daily_bar_cannot_authorize_earlier_entry(self):
        higher = [{'endET': '2025-12-31T16:00:00-05:00', 'isWarm': True, 'wt1': -1, 'wt2': 0},
                  {'endET': '2026-01-02T16:00:00-05:00', 'isWarm': True, 'wt1': 1, 'wt2': 0}]
        r = simulate(self.four, higher, initially_long=False)
        buy = r['executionLedger'][0]
        self.assertEqual(buy['executedAtET'], '2026-01-02T16:00:00-05:00')
        self.assertEqual(buy['higherConfirmedAtET'], '2026-01-02T16:00:00-05:00')

    def test_missing_higher_history_blocks_entry(self):
        r = simulate(self.four, [], initially_long=False)
        self.assertEqual(r['executions'], 0)
        self.assertEqual(r['finalValue'], 10000)

    def test_fees_applied_to_both_sides_of_round_trip(self):
        four = self.four[:2] + [candle('2026-01-02', 8, cross='bearish', up=False),
                               candle('2026-01-02', 12, close=110, opening=110, up=False)]
        r = simulate(four, cost=.001, initially_long=False)
        self.assertEqual(r['executions'], 2)
        self.assertAlmostEqual(r['finalValue'], 10000 * .999 * 1.1 * .999, places=2)
        self.assertEqual(r['closedSignalTrades'], 1)

    def test_drawdown_tracks_prior_equity_peak(self):
        four = [self.four[0], candle('2026-01-02', 4, close=110),
                candle('2026-01-02', 8, close=80)]
        r = simulate(four, cost=0)
        self.assertEqual(r['maxCloseDrawdownPct'], -27.27)
        self.assertEqual(r['returnPct'], -20)

    def test_higher_bearish_turn_does_not_change_common_exit_rule(self):
        higher = [{'endET': '2025-12-31T16:00:00-05:00', 'isWarm': True, 'wt1': 1, 'wt2': 0},
                  {'endET': '2026-01-02T12:00:00-05:00', 'isWarm': True, 'wt1': -1, 'wt2': 0}]
        r = simulate(self.four, higher, initially_long=False)
        self.assertEqual([e['action'] for e in r['executionLedger']], ['BUY'])

    def test_four_hour_baseline_reproduces_existing_simulator(self):
        for symbol in ('nvda', 'soxl'):
            source = json.loads(Path(f'data/research/{symbol}-wavetrend.json').read_text())
            rows = [c for c in source['timeframes']['4h']['candles'] if c['endET'][:10] <= '2026-10-16']
            for cost in (0, .001, .0025):
                old = prior_simulate(rows, friction=cost)
                new = simulate(rows, cost=cost)
                self.assertEqual(old['finalValue'], new['finalValue'])
                self.assertEqual(old['numberOfExecutions'], new['executions'])
                self.assertEqual([t['executedAtET'] for t in old['executions']],
                                 [t['executedAtET'] for t in new['executionLedger']])

    def test_daily_bars_are_available_at_regular_close(self):
        d = daily_rows([{'date': '2026-01-02', 'open': 100, 'high': 101, 'low': 99, 'close': 100}])
        self.assertEqual(d[0]['endET'], '2026-01-02T16:00:00-05:00')

    def test_standalone_daily_exit_waits_for_new_daily_close(self):
        signals = [dict(self.four[0], endET='2025-12-31T16:00:00-05:00', cross='bearish'),
                   dict(self.four[1], endET='2026-01-02T16:00:00-05:00', cross='bearish', wt1=-1)]
        r = simulate(self.four, signal=signals)
        self.assertEqual(r['executionLedger'][0]['action'], 'SELL')
        self.assertEqual(r['executionLedger'][0]['executedAtET'], '2026-01-02T16:00:00-05:00')

    def test_standalone_eight_hour_matches_existing_eight_hour_simulator(self):
        for symbol in ('nvda', 'soxl'):
            source = json.loads(Path(f'data/research/{symbol}-wavetrend.json').read_text())
            four = source['timeframes']['4h']['candles']
            eight = [c for c in source['timeframes']['8h']['candles'] if c['endET'][:10] <= '2026-10-16']
            for cost in (0, .001, .0025):
                old = prior_simulate(eight, friction=cost)
                new = simulate(four, cost=cost, end_date='2026-10-16', signal=eight)
                self.assertEqual(old['finalValue'], new['finalValue'])
                self.assertEqual(old['numberOfExecutions'], new['executions'])

    def test_eight_hour_daily_pair_waits_for_daily_and_ignores_four_hour_exit(self):
        four = [dict(c) for c in self.four]
        four[4]['cross'] = 'bearish'
        eight = [dict(four[0], startET='2025-12-31T12:00:00-05:00', cross=None),
                 dict(four[1], endET='2026-01-02T12:00:00-05:00', cross='bullish'),
                 dict(four[3], endET='2026-01-02T20:00:00-05:00', cross=None)]
        daily = [dict(four[0], endET='2025-12-31T16:00:00-05:00', wt1=-1),
                 dict(four[1], endET='2026-01-02T16:00:00-05:00', wt1=1)]
        r = simulate(four, higher=daily, signal=eight, initially_long=False)
        self.assertEqual([e['action'] for e in r['executionLedger']], ['BUY'])
        self.assertEqual(r['executionLedger'][0]['executedAtET'], '2026-01-02T16:00:00-05:00')

    def test_incomplete_extended_daily_is_excluded(self):
        daily, excluded = extended_daily(self.four[1:4])
        self.assertFalse(daily)
        self.assertEqual(excluded, ['2026-01-02'])
