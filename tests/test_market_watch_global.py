#!/usr/bin/env python3
import datetime as dt
import unittest

from scripts.market_watch_global import (
    classify_transmission,
    extract_percent_moves,
    move_is_material,
    qualify_global_result,
    severity_from_moves,
)


class GlobalSemiconductorDetectionTests(unittest.TestCase):
    def test_volatility_normalized_move(self):
        self.assertTrue(move_is_material(-5.0, 6.0))   # absolute safeguard
        self.assertTrue(move_is_material(-4.0, 1.5))   # 2.67 sigma-like ratio
        self.assertFalse(move_is_material(-2.0, 1.5))

    def test_october_15_korea_regression(self):
        result = {
            "title": "South Korea's KOSPI triggers circuit breaker in tech-led selloff - Reuters",
            "url": "https://www.reuters.com/world/asia-pacific/south-koreas-kospi-triggers-circuit-breaker-tech-led-selloff-2026-10-15/",
            "published_date": "2026-10-15T03:30:00Z",
            "content": (
                "The KOSPI plunged 8% after persistent U.S. inflation concerns and a prior "
                "Philadelphia Semiconductor Index fall. Samsung Electronics dropped 9.7% and "
                "SK Hynix fell 11.35% as the tech-led rout triggered a circuit breaker."
            ),
        }
        event = qualify_global_result(
            "South Korea", result,
            discovered_at=dt.datetime(2026, 10, 15, 4, 0, tzinfo=dt.timezone.utc),
        )
        self.assertIsNotNone(event)
        self.assertEqual(event["type"], "global-semiconductor")
        self.assertEqual(event["eventType"], "circuit-breaker")
        self.assertEqual(event["transmissionType"], "us-led-spillover")
        self.assertIn("South Korea", event["affectedMarkets"])
        self.assertIn("Samsung Electronics", event["affectedEntities"])
        self.assertIn("SK Hynix", event["affectedEntities"])
        self.assertIn("MU", event["affectedTickers"])
        self.assertEqual(event["severity"], "Very High")
        self.assertGreaterEqual(event["materialityScore"], 12)

    def test_global_sync_classification(self):
        text = (
            "A global selloff hit Wall Street and semiconductor shares across Japan, Taiwan "
            "and South Korea after the Nasdaq decline."
        )
        self.assertEqual(classify_transmission(text, ["Japan", "Taiwan", "South Korea"]), "globally-synchronized")

    def test_routine_move_without_catalyst_is_rejected(self):
        result = {
            "title": "TSMC shares edge lower in routine trade",
            "url": "https://www.reuters.com/world/asia-pacific/example-2026-10-15/",
            "published_date": "2026-10-15T01:00:00Z",
            "content": "TSMC moved modestly during a quiet TAIEX session.",
        }
        self.assertIsNone(qualify_global_result("Taiwan", result))

    def test_untrusted_source_is_rejected(self):
        result = {
            "title": "KOSPI plunges 9% as chip stocks trigger circuit breaker",
            "url": "https://example.invalid/story",
            "published_date": "2026-10-15T01:00:00Z",
            "content": "Samsung fell 10% and SK Hynix fell 11%.",
        }
        self.assertIsNone(qualify_global_result("South Korea", result))

    def test_percent_extraction(self):
        moves = extract_percent_moves("KOSPI plunged 8%, Samsung dropped 9.7% while TSMC rose 2.1%.")
        self.assertEqual(moves, [-8.0, -9.7, 2.1])
        self.assertEqual(severity_from_moves(moves, market_count=1), "Very High")


if __name__ == "__main__":
    unittest.main()
