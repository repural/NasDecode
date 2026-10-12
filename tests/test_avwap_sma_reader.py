import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from scripts import refresh


class StoredSMAResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch=patch.object(refresh,"HISTORY_DIR",self.tmp.name)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def save(self,bars):
        with open(os.path.join(self.tmp.name,"nvda-daily.json"),"w") as f:
            json.dump({"bars":bars},f)

    def test_no_future_leakage(self):
        self.save([
            {"date":"2026-10-08","sma20":220.0,"sma20Source":"Massive",
             "sma50":210.0,"sma50Source":"Massive"},
            {"date":"2026-10-09","sma20":230.0,"sma20Source":"Massive",
             "sma50":215.0,"sma50Source":"Massive"}])
        r=refresh.read_persisted_sma("NVDA","2026-10-08")
        self.assertEqual(r["status"],"ready")
        self.assertEqual(r["sma20"],220.0)
        self.assertEqual(r["observationDate"],"2026-10-08")

    def test_missing_and_stale(self):
        self.save([{"date":"2026-09-01","sma20":220.0,"sma20Source":"Massive"}])
        r=refresh.read_persisted_sma("NVDA","2026-10-09")
        self.assertEqual(r["status"],"stale")
        self.assertIsNone(r["sma20"])
        self.assertIsNone(r["sma50"])

    def test_unverified_sma_not_accepted(self):
        self.save([{"date":"2026-10-09","sma20":220.0,"sma50":210.0}])
        r=refresh.read_persisted_sma("NVDA","2026-10-09")
        self.assertEqual(r["status"],"partial")
        self.assertIsNone(r["sma20"])

    def test_research_only_relations(self):
        self.save([{"date":"2026-10-09","sma20":220.0,"sma20Source":"Massive",
                    "sma50":200.0,"sma50Source":"Massive"}])
        card={"ticker":"NVDA","throughDate":"2026-10-09","price":231.0,
              "anchors":{"lowestLow":{"avwap":210.0}}}
        result=refresh.avwap_sma_research(card)
        self.assertEqual(result["status"],"ready")
        self.assertEqual(result["priceVsSma20Pct"],5.0)
        self.assertEqual(result["sma20VsSma50Pct"],10.0)
        self.assertEqual(result["anchors"]["lowestLow"]["avwapVsSma20Pct"],-4.545)
        self.assertTrue(result["researchOnly"])


if __name__=="__main__":
    unittest.main()
