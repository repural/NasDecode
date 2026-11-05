import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from scripts.update_qqq_wavetrend import daily_averages, publish
from scripts.research_nvda_wavetrend import NY, wavetrend, crossover_records


class QQQTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,11,5,3,tzinfo=NY)
        day=dt.date(2025,1,1)
        self.daily={'ticker':'QQQ','adjusted':True,'source':'test adjusted closes',
                    'bars':[{'date':(day+dt.timedelta(days=i)).isoformat(),'close':i+1} for i in range(220)]}

    def test_daily_windows_and_unfinished_date(self):
        self.daily['bars'].append({'date':'2026-11-05','close':99999})
        m=daily_averages(self.daily,self.now)
        self.assertEqual(m['sma50'],195.5)
        self.assertEqual(m['sma200'],120.5)
        self.assertEqual(m['price'],220)
        self.assertAlmostEqual(m['distanceSMA50Pct'],100*(220/195.5-1),places=4)

    def test_bad_daily_archive(self):
        for mutation in ('short','wrong','missing','duplicate'):
            d=json.loads(json.dumps(self.daily))
            if mutation=='short':d['bars']=d['bars'][-199:]
            if mutation=='wrong':d['ticker']='NVDA'
            if mutation=='missing':d['bars'][-1]['close']=None
            if mutation=='duplicate':d['bars'][-1]['date']=d['bars'][-2]['date']
            with self.assertRaises(ValueError):daily_averages(d,self.now)

    def test_publish_isolated_symbol_and_warmed_timeframes(self):
        source={'symbol':'QQQ','schemaVersion':2,'historicalDataEndET':'2026-11-04T19:55:00-05:00',
                'fetchErrors':[],'timeframes':{}}
        for hours in (4,8):
            candles=[]
            for i in range(160):
                start=dt.datetime(2025,1,1,4,tzinfo=NY)+dt.timedelta(hours=i*hours)
                c=100+i/10
                candles.append({'startET':start.isoformat(),'endET':(start+dt.timedelta(hours=hours)).isoformat(),
                                'open':c,'high':c+1,'low':c-1,'close':c})
            rows=wavetrend(candles)
            source['timeframes'][str(hours)+'h']={'candles':rows,'latest':rows[-1],
                'candleCount':len(rows),'crosses':crossover_records(rows)}
        with tempfile.TemporaryDirectory() as tmp:
            src,dst,daily,shadow=[Path(tmp)/n for n in ('source.json','public.json','daily.json','shadow.json')]
            src.write_text(json.dumps(source));daily.write_text(json.dumps(self.daily))
            before=src.read_bytes()
            result=publish(self.now,src,dst,daily,shadow)
            self.assertEqual(result['symbol'],'QQQ')
            self.assertEqual(result['movingAverages']['sma200'],120.5)
            self.assertTrue(all(len(v['candles'])==48 for v in result['timeframes'].values()))
            self.assertEqual(src.read_bytes(),before)
            source['symbol']='NVDA';src.write_text(json.dumps(source))
            with self.assertRaises(ValueError):publish(self.now,src,dst,daily,shadow)


if __name__=='__main__':unittest.main()
