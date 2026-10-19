import copy
import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from scripts.reconcile_nvda_yahoo_wavetrend import reconcile

NY = ZoneInfo("America/New_York")


class ReconciliationTests(unittest.TestCase):
    def test_matching_candles_and_signal_disagreement(self):
        start = "2026-10-16T04:00:00-04:00"
        base = {"symbol": "NVDA", "fetchErrors": [], "generatedET": "2026-10-17T12:00:00-04:00",
                "timeframes": {tf: {"candles": [{"startET": start, "open": 218.5,
                    "high": 219.46, "low": 216.5, "close": 217.1,
                    "wt1": -60.458786, "wt2": -61.787882, "cross": "bullish"}]}
                    for tf in ("4h", "8h")}}
        shadow = {"symbol": "NVDA", "researchOnly": True, "publicationAllowed": False,
                  "observations": {"4h": {start: {"open": 218.5, "high": 219.45, "low": 216.5,
                      "close": 217.1, "wt1": -60.462725, "wt2": -61.788867, "cross": "bullish"}},
                       "8h": {start: {"open": 218.5, "high": 219.45, "low": 216.5,
                      "close": 217.1, "wt1": -60.462725, "wt2": -61.788867, "cross": "bearish"}}}}
        before = copy.deepcopy(shadow)
        result = reconcile(shadow, base, dt.datetime(2026, 10, 19, 8, tzinfo=NY))
        self.assertEqual(result["reconciliation"]["4h"]["matchedCandles"], 1)
        self.assertEqual(result["reconciliation"]["4h"]["crossDisagreements"], 0)
        self.assertEqual(result["reconciliation"]["8h"]["crossDisagreements"], 1)
        self.assertAlmostEqual(result["reconciliation"]["4h"]["samples"][0]["wt1Delta"], -0.003939)
        self.assertEqual(shadow, before, "must not mutate source document")
        self.assertEqual(result["observations"], before["observations"])

    def test_missing_baseline_is_not_counted_as_matched(self):
        base = {"symbol": "NVDA", "fetchErrors": [],
                "timeframes": {"4h": {"candles": []}, "8h": {"candles": []}}}
        shadow = {"symbol": "NVDA", "researchOnly": True, "publicationAllowed": False,
                  "observations": {"4h": {"2026-10-16T04:00:00-04:00": {"cross": "bullish"}}, "8h": {}}}
        result = reconcile(shadow, base)
        self.assertEqual(result["reconciliation"]["4h"]["matchedCandles"], 0)
        self.assertEqual(result["reconciliation"]["4h"]["unmatchedYahooCandles"], 1)


if __name__ == "__main__":
    unittest.main()
