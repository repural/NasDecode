import datetime as dt
import json
import unittest
from pathlib import Path
from scripts.compare_wavetrend_timeframes import simulate
from scripts.research_wavetrend_companions import features, rma, entry_allowed


def bar(day, hour, close=100, opening=100, cross=None, up=True, high=None, atr=2):
    start = dt.datetime.fromisoformat(f'{day}T{hour:02}:00:00-05:00')
    return {'startET': start.isoformat(), 'endET': (start + dt.timedelta(hours=4)).isoformat(),
            'open': opening, 'high': high if high is not None else max(opening, close),
            'low': min(opening, close), 'close': close, 'cross': cross,
            'wt1': 1 if up else -1, 'wt2': 0, 'isWarm': True, 'atr14': atr}


class CompanionTests(unittest.TestCase):
    def test_wilder_seed_and_recursion(self):
        self.assertEqual(rma([1, 3, 5], 2), [None, 2, 3.5])

    def test_flat_market_has_known_atr_and_no_directional_strength(self):
        rows = [dict(bar('2026-01-02', 4), high=101, low=99) for _ in range(50)]
        result = features(rows)
        self.assertEqual(result[-1]['ema20'], 100)
        self.assertEqual(result[-1]['atr14'], 2)
        self.assertEqual(result[-1]['plusDI14'], 0)
        self.assertEqual(result[-1]['minusDI14'], 0)
        self.assertEqual(result[-1]['adx14'], 0)

    def test_features_do_not_change_when_future_bars_are_added(self):
        source = json.loads(Path('data/research/nvda-wavetrend.json').read_text())
        candles = source['timeframes']['4h']['candles']
        self.assertEqual(features(candles[:200]), features(candles)[:200])

    def test_price_confirmation_uses_only_current_bullish_setup(self):
        rows = [bar('2026-01-02', 4, high=101, cross='bullish'),
                bar('2026-01-02', 8, close=102, high=103),
                bar('2026-01-02', 12, cross='bearish', up=False)]
        result = features(rows)
        self.assertFalse(entry_allowed('price_confirmation', result[0], 0))
        self.assertTrue(entry_allowed('price_confirmation', result[1], 1))
        self.assertFalse(entry_allowed('price_confirmation', result[2], 2))

    def test_atr_exit_fills_next_open_and_waits_for_new_green(self):
        rows = [bar('2025-12-31', 16),
                bar('2026-01-02', 4, close=105, high=106),
                bar('2026-01-02', 8, close=100, high=105),
                bar('2026-01-02', 12, close=95, opening=90),
                bar('2026-01-02', 16, close=97, cross='bullish'),
                bar('2026-01-05', 4, close=98, opening=98)]
        r = simulate(rows, cost=0, atr_multiplier=2)
        self.assertEqual([e['action'] for e in r['executionLedger']], ['SELL', 'BUY'])
        self.assertEqual(r['executionLedger'][0]['executionPrice'], 90)
        self.assertEqual(r['executionLedger'][0]['trailAtConfirmation'], 102)
        self.assertEqual(r['executionLedger'][1]['executedAtET'], '2026-01-05T04:00:00-05:00')

    def test_atr_trail_never_loosens_when_volatility_rises(self):
        rows = [bar('2025-12-31', 16),
                bar('2026-01-02', 4, close=105, high=106, atr=2),
                bar('2026-01-02', 8, close=103, high=107, atr=5),
                bar('2026-01-02', 12, close=101, high=106, atr=5),
                bar('2026-01-02', 16)]
        r = simulate(rows, cost=0, atr_multiplier=2)
        self.assertEqual(r['executionLedger'][0]['trailAtConfirmation'], 102)
        self.assertEqual(r['executionLedger'][0]['executedAtET'], '2026-01-02T16:00:00-05:00')

    def test_profit_factor_and_win_rate_use_completed_net_trades(self):
        rows = [bar('2025-12-31', 16),
                bar('2026-01-02', 4, cross='bullish'),
                bar('2026-01-02', 8, cross='bearish', up=False),
                bar('2026-01-02', 12, close=110, opening=110, cross='bullish'),
                bar('2026-01-02', 16, close=110, opening=110, cross='bearish', up=False),
                bar('2026-01-05', 4, close=99, opening=99, up=False)]
        r = simulate(rows, cost=0, initially_long=False)
        self.assertEqual(r['closedSignalTrades'], 2)
        self.assertEqual(r['winRatePct'], 50)
        self.assertEqual(r['averageWinPct'], 10)
        self.assertEqual(r['averageLossPct'], -10)
        self.assertEqual(r['netProfitFactor'], round(1000 / 1100, 4))
        self.assertEqual(r['returnPct'], -1)

    def test_entry_filter_does_not_trigger_an_early_exit(self):
        rows = [bar('2025-12-31', 16), bar('2026-01-02', 4, cross='bullish'),
                bar('2026-01-02', 8), bar('2026-01-02', 12, cross='bearish', up=False),
                bar('2026-01-02', 16)]
        r = simulate(rows, initially_long=False, entry_filter=lambda c, i: i == 1)
        self.assertEqual([e['action'] for e in r['executionLedger']], ['BUY', 'SELL'])
        self.assertEqual(r['executionLedger'][1]['executedAtET'], '2026-01-02T16:00:00-05:00')
