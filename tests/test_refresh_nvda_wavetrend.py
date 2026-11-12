import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from scripts.refresh_nvda_wavetrend import refresh
from scripts.research_nvda_wavetrend import wavetrend,crossover_records


class IncrementalNVDAWaveTrendTests(unittest.TestCase):
    def setUp(self):
        ny=ZoneInfo("America/New_York")
        # 120 confirmed candles in each timeframe, ending the prior trading date.
        self.document={"symbol":"NVDA","fetchErrors":[],
             "historicalDataEndET":"2026-10-14T19:55:00-04:00","timeframes":{}}
        for hours in (4,8):
            candles=[]
            for i in range(120):
                date=dt.date(2026,2,1)+dt.timedelta(days=i//(16//hours))
                hour=4+(i%(16//hours))*hours
                start=dt.datetime.combine(date,dt.time(hour),ny)
                candles.append({"startET":start.isoformat(),
                    "endET":(start+dt.timedelta(hours=hours)).isoformat(),
                    "open":200.0+i/5,"high":201.0+i/5,
                    "low":199.0+i/5,"close":200.5+i/5,
                    "underlying5mBars":12*hours})
            rows=wavetrend(candles)
            self.document["timeframes"][str(hours)+"h"]={"candles":rows,
                "latest":rows[-1],"crosses":crossover_records(rows)}

    def test_no_bars_does_not_advance(self):
        now=dt.datetime(2026,10,16,8,tzinfo=ZoneInfo("America/New_York"))
        out,advanced=refresh(self.document,[],now)
        self.assertFalse(advanced)
        self.assertEqual(out["historicalDataEndET"],self.document["historicalDataEndET"])

    def test_incomplete_session_refused(self):
        now=dt.datetime(2026,10,16,8,tzinfo=ZoneInfo("America/New_York"))
        single={"timestampET":"2026-10-15T04:00:00-04:00","dateET":"2026-10-15","hourET":4,
                "open":230.0,"high":230.1,"low":229.9,"close":230.0}
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            refresh(self.document,[single],now)
