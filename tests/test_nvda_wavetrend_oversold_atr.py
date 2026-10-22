import unittest
from scripts.compare_wavetrend_timeframes import simulate
from scripts.research_nvda_oversold_atr import oversold
from tests.test_wavetrend_zones import zoned


class OversoldATRTests(unittest.TestCase):
    def test_entry_filter_requires_new_green_and_includes_boundary(self):
        self.assertFalse(oversold(zoned('2026-01-02',4,-60),0))
        self.assertFalse(oversold(zoned('2026-01-02',4,-44.99,'bullish'),0))
        self.assertTrue(oversold(zoned('2026-01-02',4,-45,'bullish'),0))

    def test_oversold_entry_sells_red_without_overbought_requirement(self):
        rows=[zoned('2025-12-31',16,0),zoned('2026-01-02',4,-45,'bullish'),
              zoned('2026-01-02',8,-20,'bearish'),zoned('2026-01-02',12,-20)]
        r=simulate(rows,initially_long=False,entry_filter=oversold)
        self.assertEqual([e['action'] for e in r['executionLedger']],['BUY','SELL'])
        self.assertEqual(r['executionLedger'][1]['executedAtET'],rows[-1]['startET'])

    def test_combined_atr_exit_waits_for_new_qualifying_green(self):
        rows=[zoned('2025-12-31',16,0),zoned('2026-01-02',4,-50,'bullish'),
              zoned('2026-01-02',8,-40,close=105,high=106),
              zoned('2026-01-02',12,-30,close=100,high=105),
              zoned('2026-01-02',16,-20),
              zoned('2026-01-05',4,-10,'bullish'),
              zoned('2026-01-05',8,-55,'bullish'),zoned('2026-01-05',12,-40)]
        r=simulate(rows,initially_long=False,entry_filter=oversold,atr_multiplier=2)
        ledger=r['executionLedger']
        self.assertEqual([e['action'] for e in ledger],['BUY','SELL','BUY'])
        self.assertEqual(ledger[1]['reason'],'atr_trail')
        self.assertEqual(ledger[2]['executedAtET'],rows[-1]['startET'])
