import unittest
from scripts.backtest_wavetrend import simulate


def row(day, start_hour, close_hour, price, cross=None, open_price=None):
    return {"startET":f"{day}T{start_hour:02d}:00:00-05:00",
            "endET":f"{day}T{close_hour:02d}:00:00-05:00",
            "open":open_price if open_price is not None else price,
            "close":price,"cross":cross}


class BacktestWaveTrendTests(unittest.TestCase):
    def test_next_bar_execution_full_cash_and_buy(self):
        bars=[row("2025-12-31",12,20,100),
              row("2026-01-02",4,12,110,"bearish"),
              row("2026-01-02",12,20,106,"bullish",open_price=105),
              row("2026-01-05",4,12,120,open_price=110)]
        result=simulate(bars)
        self.assertEqual(result["numberOfExecutions"],2)
        self.assertEqual(result["executions"][0]["executionPrice"],105)
        self.assertEqual(result["executions"][1]["executionPrice"],110)
        self.assertEqual(result["finalPosition"],"shares")
        self.assertAlmostEqual(result["finalValue"],10000/100*105/110*120,2)

    def test_initially_long_and_end_cash(self):
        bars=[row("2025-12-31",12,20,100),
              row("2026-01-02",4,12,110,"bearish"),
              row("2026-01-02",12,20,106,open_price=105)]
        result=simulate(bars)
        self.assertEqual(result["finalPosition"],"cash")
        self.assertEqual(result["finalValue"],10500)
        self.assertEqual(result["numberOfExecutions"],1)

    def test_noncausal_candle_is_rejected(self):
        bars=[row("2025-12-31",12,20,100),
              row("2026-01-02",4,12,110,"bearish"),
              row("2026-01-02",8,16,105)]
        with self.assertRaises(ValueError):
            simulate(bars)


if __name__=="__main__":
    unittest.main()
