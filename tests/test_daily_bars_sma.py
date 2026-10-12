import unittest
from scripts.collect_daily_bars import add_sma

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

if __name__=="__main__":
    unittest.main()
