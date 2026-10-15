import unittest
from unittest.mock import patch
import datetime as dt
from scripts.probe_fedwatch_tavily import parse_table


class FedwatchTavilyParserTests(unittest.TestCase):
    def sample(self, a="56.27", b="43.73"):
        return ("| MEETING DATE | 375-400 | 400-425 | 425-450 |\n"
                "|---|---|---|---|\n"
                "| 10/28/2026 | "+a+" % | "+b+" % | 0.00 % |\n")

    def test_complete_cme_aggregated_row(self):
        rows = parse_table(self.sample(), today=dt.date(2026, 10, 15))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["targetProbabilities"]["375-400"], 56.27)

    def test_reject_incomplete_probabilities(self):
        self.assertEqual(parse_table(self.sample("10.00", "20.00"), today=dt.date(2026, 10, 15)), [])

    def test_reject_search_snippet_without_header(self):
        self.assertEqual(parse_table("FedWatch Oct 28 56.27 percent chance of no hike"), [])

    def test_reject_old_meeting_dates(self):
        self.assertEqual(parse_table(self.sample(), today=dt.date(2026, 11, 1)), [])


if __name__ == "__main__":
    unittest.main()
