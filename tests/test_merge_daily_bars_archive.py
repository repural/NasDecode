import unittest
from scripts.merge_daily_bars_archive import reconcile

class MergeBarsTests(unittest.TestCase):
    def test_concurrent_updates_preserved(self):
        current={"updatedET":"2026-10-12T17:30:00-04:00","ticker":"SOXL","bars":[
            {"date":"2026-10-08","close":140.0,"sma20":138.0},
            {"date":"2026-10-09","close":141.0,"volume":10}]}
        collected={"updatedET":"2026-10-12T17:20:00-04:00","ticker":"SOXL","bars":[
            {"date":"2026-10-08","close":139.0,"sma20":137.0,"sma20Source":"Massive"},
            {"date":"2026-10-09","close":None,"sma20":139.0,"sma20Source":"Massive"}]}
        merged=reconcile(current,collected)
        self.assertEqual(merged["bars"][0]["close"],140.0)
        self.assertEqual(merged["bars"][0]["sma20"],138.0)
        self.assertEqual(merged["bars"][0]["sma20Source"],"Massive")
        self.assertEqual(merged["bars"][1]["close"],141.0)
        self.assertEqual(merged["bars"][1]["sma20"],139.0)
    def test_newer_capture_wins_without_erasing_non_null(self):
        current={"updatedET":"2026-10-12T15:00:00-04:00",
                 "bars":[{"date":"2026-10-09","close":100.0,"volume":9}]}
        collected={"updatedET":"2026-10-12T16:00:00-04:00",
                   "bars":[{"date":"2026-10-09","close":101.0,"volume":None,"sma20":98.0}]}
        merged=reconcile(current,collected)
        self.assertEqual(merged["bars"][0]["close"],101.0)
        self.assertEqual(merged["bars"][0]["volume"],9)
        self.assertEqual(merged["bars"][0]["sma20"],98.0)

if __name__=="__main__":
    unittest.main()
