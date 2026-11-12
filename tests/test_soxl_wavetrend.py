import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.publish_soxl_wavetrend import publish, interpretation
from scripts.refresh_nvda_wavetrend import refresh


class SOXLWaveTrendTests(unittest.TestCase):
    def test_matching_snapshot_and_report_are_published(self):
        with tempfile.TemporaryDirectory() as folder:
            result = publish(dst=Path(folder) / "feed.json")
        self.assertEqual(result["symbol"], "SOXL")
        self.assertEqual(len(result["timeframes"]["4h"]["candles"]), 48)
        # Publication must include commentary in every momentum state. Mixed
        # states use different wording and need not contain the literal "WT1".
        self.assertIsInstance(result["interpretation"], str)
        self.assertGreater(len(result["interpretation"]), 20)
        self.assertNotIn("executions", result["backtest"]["timeframes"]["4h"]["zeroCosts"])

    def test_interpretation_handles_all_four_momentum_states(self):
        for up4, up8 in ((True, True), (False, False), (True, False), (False, True)):
            with self.subTest(bullish4h=up4, bullish8h=up8):
                source = {"timeframes": {
                    "4h": {"latest": {"wt1": 1 if up4 else -1, "wt2": 0},
                           "crosses": [], "candles": []},
                    "8h": {"latest": {"wt1": 1 if up8 else -1, "wt2": 0}}}}
                text = interpretation(source)
                if up4 == up8:
                    self.assertIn("Both timeframes are " + ("bullish" if up4 else "bearish"), text)
                else:
                    self.assertIn("4H is " + ("bullish" if up4 else "bearish"), text)
                    self.assertIn("8H remains " + ("bullish" if up8 else "bearish"), text)

    def test_mismatched_backtest_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "bad.json"
            report = json.loads(Path("data/research/soxl-wavetrend-backtest.json").read_text())
            report["sourceResearchGeneratedET"] = "old snapshot"
            bad.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "snapshot"):
                publish(backtest=bad, dst=Path(folder) / "feed.json")

    def test_incremental_refresh_preserves_soxl_history_and_rejects_wrong_symbol(self):
        source = json.loads(Path("data/research/soxl-wavetrend.json").read_text())
        now = dt.datetime.now(ZoneInfo("America/New_York"))
        result, advanced = refresh(source, [], now, symbol="SOXL")
        self.assertFalse(advanced)
        self.assertEqual(source, result)
        with self.assertRaises(ValueError):
            refresh(source, [], now)  # NVDA default cannot accept SOXL.

    def test_completed_new_session_advances_both_timeframes_without_losing_history(self):
        source = json.loads(Path("data/research/soxl-wavetrend.json").read_text())
        ny = ZoneInfo("America/New_York")
        last = dt.datetime.fromisoformat(source["timeframes"]["4h"]["lastEndET"])
        day = last.date() + dt.timedelta(days=1)
        while day.weekday() >= 5:
            day += dt.timedelta(days=1)
        bars = []
        for i in range(192):
            stamp = dt.datetime.combine(day, dt.time(4), ny) + dt.timedelta(minutes=5*i)
            bars.append({"timestampET": stamp.isoformat(), "dateET": day.isoformat(),
                "hourET": stamp.hour, "open": 95.0, "high": 96.0, "low": 94.0, "close": 95.5})
        result, advanced = refresh(source, bars, last + dt.timedelta(days=5), symbol="SOXL")
        self.assertTrue(advanced)
        for tf, extra in (("4h", 4), ("8h", 2)):
            self.assertEqual(len(result["timeframes"][tf]["candles"]), len(source["timeframes"][tf]["candles"]) + extra)
            self.assertEqual(result["timeframes"][tf]["candles"][:-extra], source["timeframes"][tf]["candles"])
