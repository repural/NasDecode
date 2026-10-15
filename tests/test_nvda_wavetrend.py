import datetime as dt
import unittest
from scripts.research_nvda_wavetrend import aggregate, crossover_records, ema, sma, wavetrend


class WaveTrendTests(unittest.TestCase):
    def test_ema_seed_and_sma(self):
        self.assertEqual(ema([1.0, 3.0, 5.0], 3), [1.0, 2.0, 3.5])
        self.assertEqual(sma([1.0, 3.0, 5.0], 2), [None, 2.0, 4.0])

    def test_extended_4h_and_8h_boundaries(self):
        rows = []
        for hour in range(4,20):
            for minute in range(0,60,5):
                rows.append({"timestampET":f"2026-10-14T{hour:02d}:{minute:02d}:00-04:00",
                             "dateET":"2026-10-14","hourET":hour,
                             "open":float(hour),"high":float(hour)+1,
                             "low":float(hour)-1,"close":float(hour)+0.5})
        four=aggregate(rows,4)
        eight=aggregate(rows,8)
        self.assertEqual([x["startET"][11:16] for x in four],["04:00","08:00","12:00","16:00"])
        self.assertEqual([x["endET"][11:16] for x in eight],["12:00","20:00"])
        self.assertTrue(all(x["underlying5mBars"]==48 for x in four))
        self.assertTrue(all(x["underlying5mBars"]==96 for x in eight))

    def test_unfinished_candle_excluded(self):
        rows=[{"timestampET":f"2026-10-14T04:{i:02d}:00-04:00","dateET":"2026-10-14",
               "hourET":4,"open":10,"high":11,"low":9,"close":10} for i in range(0,55,5)]
        self.assertEqual(aggregate(rows,4),[])

    def test_crossover_records_preserve_open_and_close_times_and_prices(self):
        rows=[{"startET":"2026-10-14T08:00:00-04:00",
               "endET":"2026-10-14T12:00:00-04:00",
               "direction":"unused","cross":"bearish",
               "open":228.0,"high":229.0,"low":223.0,"close":224.1,
               "wt1":-39.4,"wt2":-38.6},
              {"startET":"2026-10-14T12:00:00-04:00",
               "endET":"2026-10-14T16:00:00-04:00",
               "cross":None,"open":224.1,"high":225.0,"low":220.0,
               "close":221.0,"wt1":-41.0,"wt2":-40.0}]
        exported=crossover_records(rows)
        self.assertEqual(len(exported),1)
        event=exported[0]
        self.assertEqual(event["candleStartET"],"2026-10-14T08:00:00-04:00")
        self.assertEqual(event["confirmedAtET"],"2026-10-14T12:00:00-04:00")
        self.assertEqual(event["endET"],event["confirmedAtET"])
        self.assertEqual(event["low"],223.0)
        self.assertEqual(event["priceAtConfirmation"],224.1)
        self.assertNotEqual(event["priceAtConfirmation"],event["low"])

    def test_no_crosses_before_warmup(self):
        rows=[{"startET":f"2026-09-{i%28+1:02d}T04:00:00-04:00",
               "endET":"x","open":100,"high":110+i/20,"low":90+i/20,
               "close":100+i/20} for i in range(60)]
        result=wavetrend(rows)
        self.assertTrue(all(r["cross"] is None for r in result))
        self.assertTrue(all(not r["isWarm"] for r in result))


if __name__ == "__main__":
    unittest.main()
