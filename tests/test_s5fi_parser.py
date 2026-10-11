"""Offline checks for S5FI dated-price parsing and fail-closed handling."""
import unittest
from scripts.probe_s5fi_tavily import candidates

class TestS5FIParser(unittest.TestCase):
    def test_price_column_and_uk_date(self):
        raw = "| Date | Price | Open | High | Low | Vol. | Change % |\n| 09/10/2026 | 34.93 | 33.10 | 35.01 | 32.80 | | +5.53% |"
        self.assertEqual(candidates(raw), [{"date": "2026-10-09", "pctAbove50dma": 34.93}])

    def test_missing_date_rejected(self):
        self.assertEqual(candidates("| | 34.93 | 33.10 | 35.01 | 32.80 | +5.53% |"), [])

    def test_invalid_ohlc_rejected(self):
        self.assertEqual(candidates("| 09/10/2026 | 99.5 | 50 | 40 | 20 | | +3% |"), [])

    def test_date_not_inferred_from_row_order(self):
        raw="| | 29.48 | 28.62 | 30.81 | 28.62 | +9.88% |\n| 02/10/2026 | 24.65 | 24.05 | 24.65 | 23.26 | +7.83% |"
        self.assertEqual(candidates(raw), [{"date":"2026-10-02","pctAbove50dma":24.65}])

if __name__ == "__main__":
    unittest.main()
