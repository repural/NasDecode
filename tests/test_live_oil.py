import datetime as dt
import unittest

from scripts.collect_live_oil import build_snapshot, change_percent


# Collector tests run independently of the dashboard's full data refresh.
class LiveOilQuoteTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 10, 13, 9, 30, tzinfo=dt.timezone.utc)
        self.quote = {
            "last": "105.03",
            "change_pct": "-1.52%",
            "last_time": "2026-10-13T09:20:00.000+0000",
        }

    def test_valid_independent_brent(self):
        data = build_snapshot({"@LCO.1": self.quote}, self.now)
        self.assertIn("brent", data["quotes"])
        self.assertNotIn("wti", data["quotes"])
        self.assertEqual(data["quotes"]["brent"]["price"], 105.03)

    def test_valid_independent_wti(self):
        data = build_snapshot({"@CL.1": self.quote}, self.now)
        self.assertIn("wti", data["quotes"])
        self.assertNotIn("brent", data["quotes"])

    def test_missing_change_does_not_hide_price(self):
        quote = {**self.quote, "change_pct": None}
        data = build_snapshot({"@LCO.1": quote}, self.now)
        self.assertEqual(data["quotes"]["brent"]["price"], 105.03)
        self.assertIsNone(data["quotes"]["brent"]["changePct"])

    def test_unchanged_is_zero(self):
        self.assertEqual(change_percent({**self.quote, "change_pct": "UNCH"}), 0.0)

    def test_stale_quote_rejected(self):
        quote = {**self.quote, "last_time": "2026-10-13T09:00:00+0000"}
        self.assertEqual(build_snapshot({"@LCO.1": quote}, self.now)["quotes"], {})

    def test_undated_quote_rejected(self):
        quote = {**self.quote, "last_time": None}
        self.assertEqual(build_snapshot({"@LCO.1": quote}, self.now)["quotes"], {})


if __name__ == "__main__":
    unittest.main()
