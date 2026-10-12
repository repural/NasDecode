import unittest
from scripts.collect_daily_bars import add_sma, merge_provider_sma, validate_sma

class TestDailySMA(unittest.TestCase):
    def test_first_full_window(self):
        bars=[{"date":str(i),"close":float(i)} for i in range(1,61)]
        add_sma(bars)
        self.assertIsNone(bars[18]["sma20"])
        self.assertAlmostEqual(bars[19]["sma20"],10.5)
        self.assertIsNone(bars[48]["sma50"])
        self.assertAlmostEqual(bars[49]["sma50"],25.5)
        self.assertAlmostEqual(bars[59]["sma20"],50.5)
        self.assertAlmostEqual(bars[59]["sma50"],35.5)

    def test_null_does_not_shortcut_window(self):
        bars=[{"date":str(i),"close":float(i)} for i in range(1,62)]
        bars[40]["close"]=None
        add_sma(bars)
        self.assertIsNone(bars[41]["sma20"])
        self.assertIsNone(bars[59]["sma50"])
        self.assertIsNone(bars[59]["sma20"])
        self.assertAlmostEqual(bars[60]["sma20"],51.5)

    def test_provider_is_canonical_and_missing_is_not_fabricated(self):
        bars=[{"date":"2026-10-08","close":10.0},{"date":"2026-10-09","close":11.0}]
        merge_provider_sma(bars,{"2026-10-09":10.75},20)
        self.assertIsNone(bars[0]["sma20"])
        self.assertEqual(bars[1]["sma20"],10.75)
        self.assertEqual(bars[1]["sma20Source"],"Massive")
        merge_provider_sma(bars,None,20)
        self.assertEqual(bars[1]["sma20"],10.75)
        self.assertEqual(validate_sma(bars)["sma20"]["providerCoverage"],1)

if __name__=="__main__":
    unittest.main()
