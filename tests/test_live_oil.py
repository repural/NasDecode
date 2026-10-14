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

    def test_dashboard_oil_scorecard_parses_published_quote_format(self):
        import re
        from pathlib import Path
        source = Path("scripts/refresh.py").read_text(encoding="utf-8")
        pattern = r'\b' + 'Brent' + r'\s*\$([0-9]+(?:\.[0-9]+)?)\s*\(([^)]*)\)'
        self.assertIn("match=re.search(r'\\b'+label+r'\\s*\\$([0-9]+(?:\\.[0-9]+)?)\\s*\\(([^)]*)\\)'", source)
        latest = "Brent $106.19 (+0.47%) | WTI $95.59 (+1.54%)"
        brent = re.search(pattern, latest, re.I)
        wti = re.search(pattern.replace("Brent", "WTI"), latest, re.I)
        self.assertIsNotNone(brent)
        self.assertIsNotNone(wti)
        self.assertEqual(brent.groups(), ("106.19", "+0.47%"))
        self.assertEqual(wti.groups(), ("95.59", "+1.54%"))

    def test_browser_initializes_live_quote_polling(self):
        from pathlib import Path
        for path in ("index.html", "public/index.html"):
            script = Path(path).read_text(encoding="utf-8")
            self.assertIn("startLiveOilPolling();(async()=>", script, path)
            self.assertIn("const d=await load();await loadLiveOil();", script, path)
            self.assertIn("liveOilTimer=setInterval(loadLiveOil,30*1000)", script, path)


if __name__ == "__main__":
    unittest.main()
