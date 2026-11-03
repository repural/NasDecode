"""Non-overlapping v3 execution assumptions, using synthetic OHLC observations."""
import unittest
from scripts.backtest_directional_v3_nonoverlap import analyze,trade

class EventBacktestTests(unittest.TestCase):
    def sample(self, n=14):
        dates=[f"2026-07-{i:02d}" for i in range(1,n+1)]
        rec={d:{"market":{"SOXL":{"open":100+i,"high":102+i,"low":99+i,"close":101+i}}} for i,d in enumerate(dates)}
        engine={"engineVersion":"directional-engine-v3.0","frozenProtocol":{"specSha256":"test-frozen"},
                "records":[{"date":d,"setup":"washout_rebound"} for d in dates]}
        return dates,rec,engine

    def test_next_open_to_fifth_close_and_no_overlap(self):
        dates,rec,engine=self.sample()
        result=analyze(engine,{"records":rec})
        self.assertEqual([x["signalDate"] for x in result["trades"]],[dates[0],dates[6]])
        self.assertEqual(result["trades"][0]["entryDate"],dates[1])
        self.assertEqual(result["trades"][0]["exitDate"],dates[5])
        self.assertAlmostEqual(result["trades"][0]["returnPct"],100*((106/101)-1),places=4)
        self.assertEqual(result["skippedSignals"]["overlap"],10)

    def test_missing_open_is_not_filled_with_close(self):
        dates,rec,engine=self.sample()
        del rec[dates[1]]["market"]["SOXL"]["open"]
        result=analyze(engine,{"records":rec})
        self.assertGreater(result["skippedSignals"]["missing_entry_or_exit"],0)
        self.assertNotEqual(result["trades"][0]["signalDate"],dates[0])

    def test_unmatured_final_signal_is_not_tested(self):
        dates,rec,engine=self.sample(5)
        result=analyze(engine,{"records":rec})
        self.assertEqual(result["overall"]["n"],0)
        self.assertEqual(result["skippedSignals"]["not_mature"],5)

if __name__=="__main__":
    unittest.main()
