import datetime as dt
import unittest
from scripts.collect_intraday_avwap import historical_anchors,evaluate

class IntradayAVWAPTests(unittest.TestCase):
    def test_missing_history_is_unavailable(self):
        a,t=historical_anchors([],"2026-10-13")
        self.assertEqual(a,{})
        self.assertEqual(evaluate([],t)["status"],"unavailable")

    def test_touch_then_followthrough(self):
        bars=[{"timestampET":"2026-10-13T09:30:00-04:00","open":99.5,"high":101,"low":99,
               "close":100,"volume":100,"vwap":100},
              {"timestampET":"2026-10-13T09:35:00-04:00","open":101.5,"high":103,"low":101.5,
               "close":102,"volume":100,"vwap":102}]
        total={"lowestLow":{"weighted":10000,"volume":100}}
        result=evaluate(bars,total)
        self.assertEqual(result["status"],"developing_intraday")
        self.assertEqual(result["signals"][0]["phase"],"bounce_follow_through_5m")
        self.assertTrue(result["momentumBreakout5m"])

    def test_no_touch_only_proximity(self):
        bars=[{"timestampET":"2026-10-13T09:30:00-04:00","open":101,"high":102,"low":100.5,
               "close":101,"volume":100,"vwap":101}]
        result=evaluate(bars,{"lowestLow":{"weighted":10000,"volume":100}})
        self.assertEqual(result["signals"][0]["phase"],"approaching")

if __name__=="__main__":
    unittest.main()
