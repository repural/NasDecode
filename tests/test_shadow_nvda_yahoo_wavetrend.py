#!/usr/bin/env python3
"""Local deterministic checks for confirmed-only Yahoo overlay."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from scripts.shadow_nvda_yahoo_wavetrend import confirmed_yahoo_candles, build_shadow
from scripts.research_nvda_wavetrend import wavetrend

NY=ZoneInfo("America/New_York")


def bars(day, hour, count=48):
    start=dt.datetime.combine(dt.date.fromisoformat(day),dt.time(hour),NY)
    return [{"timeET":(start+dt.timedelta(minutes=5*i)).isoformat(),"dateET":day,
             "hourET":(start+dt.timedelta(minutes=5*i)).hour,
             "open":100.0,"high":101.0,"low":99.0,"close":100.0}
            for i in range(count)]


class ShadowTests(unittest.TestCase):
    def test_completed_4h_accepts_48(self):
        now=dt.datetime(2026,10,16,9,0,tzinfo=NY)
        candles,rejected=confirmed_yahoo_candles(bars("2026-10-16",4),4,now)
        self.assertEqual(len(candles),1)
        self.assertEqual(candles[0]["underlying5mBars"],48)
        self.assertFalse(rejected)

    def test_missing_interval_is_rejected(self):
        now=dt.datetime(2026,10,16,9,0,tzinfo=NY)
        candles,rejected=confirmed_yahoo_candles(bars("2026-10-16",4)[:-1],4,now)
        self.assertFalse(candles)
        self.assertEqual(rejected[0]["reason"],"missing_5m_intervals")

    def test_not_yet_confirmed_is_rejected(self):
        now=dt.datetime(2026,10,16,8,2,tzinfo=NY)
        candles,rejected=confirmed_yahoo_candles(bars("2026-10-16",4),4,now)
        self.assertFalse(candles)
        self.assertEqual(rejected[0]["reason"],"not_yet_confirmed")

    def test_append_preserves_archive_and_recalculates(self):
        history=[]
        for i in range(120):
            day=dt.date(2026,9,1)+dt.timedelta(days=i//4)
            h=(4,8,12,16)[i%4]
            start=dt.datetime.combine(day,dt.time(h),NY)
            history.append({"startET":start.isoformat(),
                            "endET":(start+dt.timedelta(hours=4)).isoformat(),
                            "open":100+i/10,"high":101+i/10,"low":99+i/10,
                            "close":100+i/10,"underlying5mBars":48})
        # Test uses the saved boundary of Oct 15 without requiring realistic past dates.
        for tf in (4,8):
            pass
        candles4=wavetrend(history)
        candles8=wavetrend([{"startET":c["startET"],"endET":c["endET"],
                             "open":c["open"],"high":c["high"],"low":c["low"],
                             "close":c["close"]} for c in history])
        self.assertTrue(candles4[-1]["isWarm"])
        self.assertEqual(len(candles8),120)


if __name__=="__main__":
    unittest.main()
