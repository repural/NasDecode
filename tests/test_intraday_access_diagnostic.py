import datetime as dt
import os
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
from scripts.diagnose_intraday_access import compare

class IntradayAccessTests(unittest.TestCase):
    def test_missing_key_does_not_attempt_requests(self):
        with patch.dict(os.environ,{"MASSIVE_API_KEY":""}):
            self.assertEqual(compare()["status"],"missing_api_key")

    def test_compares_equal_symbols_and_dates(self):
        calls=[]
        def stub(symbol,day,key):
            calls.append((symbol,day))
            return {"httpStatus":403,"providerStatus":"http_error","count":None,"requestDate":day}
        now=dt.datetime(2026,10,16,9,40,tzinfo=ZoneInfo("America/New_York"))
        with patch.dict(os.environ,{"MASSIVE_API_KEY":"dummy"}):
            result=compare(now,request=stub)
        self.assertEqual(result["dates"],{"olderTradingDay":"2026-10-08",
                                           "previousTradingDay":"2026-10-15",
                                           "currentSession":"2026-10-16"})
        self.assertEqual(len(calls),6)
        self.assertEqual(set(result["results"]),{"NVDA","SOXL"})

if __name__=="__main__":
    unittest.main()
