import unittest
from scripts.compare_wavetrend_timeframes import simulate
from tests.test_wavetrend_companions import bar


def zoned(day, hour, wt, cross=None, **kwargs):
    c = bar(day, hour, cross=cross, **kwargs)
    c.update(wt1=wt, wt2=wt-1 if cross != 'bearish' else wt+1)
    return c


class ZoneTests(unittest.TestCase):
    def test_only_fresh_qualifying_crosses_execute_at_next_open(self):
        rows = [zoned('2025-12-31',16,-60,'bullish'),
                zoned('2026-01-02',4,-60),  # stale green must not buy
                zoned('2026-01-02',8,-44,'bullish'),  # outside zone
                zoned('2026-01-02',12,-45,'bullish'),
                zoned('2026-01-02',16,44,'bearish',opening=101),  # hold
                zoned('2026-01-05',4,45,'bearish'),
                zoned('2026-01-05',8,-60,'bullish',opening=110),
                zoned('2026-01-05',12,-60,opening=105)]
        r=simulate(rows,initially_long=False,zone_threshold=45,cost=0)
        ledger=r['executionLedger']
        self.assertEqual([e['action'] for e in ledger],['BUY','SELL','BUY'])
        self.assertEqual([e['executionPrice'] for e in ledger],[101,110,105])
        self.assertEqual([e['signalWT1'] for e in ledger],[-45,45,-60])
        self.assertTrue(r['unclosedSignalTrade'])

    def test_eight_hour_cross_cannot_execute_before_confirmation(self):
        four=[zoned('2025-12-31',16,0)]+[zoned('2026-01-02',h,0) for h in (4,8,12,16)]
        eight=[dict(four[0]),dict(zoned('2026-01-02',4,-55,'bullish'),endET=four[2]['endET'])]
        r=simulate(four,signal=eight,initially_long=False,zone_threshold=53)
        self.assertEqual(r['executionLedger'][0]['executedAtET'],four[3]['startET'])

    def test_unqualified_red_keeps_inherited_position(self):
        rows=[zoned('2025-12-31',16,0),zoned('2026-01-02',4,0,'bearish'),zoned('2026-01-02',8,-60)]
        r=simulate(rows,zone_threshold=45)
        self.assertEqual(r['executions'],0)
        self.assertEqual(r['finalPosition'],'shares')

    def test_reject_invalid_zone(self):
        for level in (-1,0,float('nan'),float('inf')):
            with self.assertRaises(ValueError):simulate([],zone_threshold=level)
