import datetime as dt
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.shadow_nvda_yahoo_wavetrend import developing_yahoo_candle, build_shadow
from scripts.wavetrend_presentation import presentation
from scripts.research_nvda_wavetrend import wavetrend
from scripts import publish_nvda_wavetrend, publish_soxl_wavetrend

NY = ZoneInfo('America/New_York')


def bars(start, count=13, price=250):
    return [{'timeET': (start+dt.timedelta(minutes=5*i)).isoformat(),
             'dateET': start.date().isoformat(), 'hourET': (start+dt.timedelta(minutes=5*i)).hour,
             'open': price, 'high': price+1, 'low': price-1, 'close': price}
            for i in range(count)]


class DevelopingTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(Path('data/research/nvda-wavetrend.json').read_text())
        last = dt.datetime.fromisoformat(self.source['timeframes']['4h']['latest']['endET'])
        day = last.date()+dt.timedelta(days=1)
        while day.weekday() >= 5: day += dt.timedelta(days=1)
        self.start = dt.datetime.combine(day, dt.time(4), NY)
        self.now = self.start+dt.timedelta(hours=1, minutes=2)
        self.bars = bars(self.start)

    def render(self, raw, now=None):
        shadow = {'symbol': 'NVDA', 'timeframes': {'4h': {'developingCandle': raw}}}
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'shadow.json';p.write_text(json.dumps(shadow))
            return presentation(self.source, p, now or self.now)

    def test_current_partial_slot_is_valid_but_internal_gap_is_not(self):
        for hours in (4, 8):
            raw = developing_yahoo_candle(self.bars, hours, self.now)
            self.assertEqual(raw['underlying5mBars'], 13)
            self.assertEqual(raw['asOfET'], self.now.isoformat())
            self.assertFalse(raw['isConfirmed'])
            self.assertIsNone(developing_yahoo_candle(self.bars[:4]+self.bars[5:], hours, self.now))

    def test_missing_first_interval_and_stale_feed_are_rejected(self):
        self.assertIsNone(developing_yahoo_candle(self.bars[1:], 4, self.now))
        self.assertIsNone(developing_yahoo_candle(self.bars, 4, self.now+dt.timedelta(minutes=25)))

    def test_future_rows_do_not_enter_current_calculation(self):
        rows=self.bars+bars(self.now+dt.timedelta(hours=1),1,1000)
        raw=developing_yahoo_candle(rows,4,self.now)
        self.assertEqual(raw['high'],251)

    def test_no_developing_preview_outside_extended_session(self):
        for now in [self.start.replace(hour=3),self.start.replace(hour=20),
                    dt.datetime(2026,10,24,10,tzinfo=NY)]:
            self.assertIsNone(developing_yahoo_candle(self.bars,4,now))

    def test_preview_does_not_change_history_latest_or_confirmed_crosses(self):
        before=json.dumps(self.source)
        raw=developing_yahoo_candle(self.bars,4,self.now)
        result=self.render(raw);without=self.render(None)
        a,b=result['timeframes']['4h'],without['timeframes']['4h']
        for key in ('candles','latest','crosses','candleCount','lastEndET'):
            self.assertEqual(a[key],b[key])
        self.assertEqual(json.dumps(self.source),before)
        preview=a['developing'];expected=wavetrend(b['candles']+[raw])[-1]
        self.assertEqual(preview['wt1'],expected['wt1'])
        self.assertEqual(preview['wt2'],expected['wt2'])
        self.assertEqual(preview['potentialCross'],expected['cross'])
        self.assertIsNone(preview['cross'])

    def test_repeated_updates_replace_preview_without_compounding_ema(self):
        raw=developing_yahoo_candle(self.bars,4,self.now)
        first=self.render(raw)['timeframes']['4h']['developing']
        changed=developing_yahoo_candle(bars(self.start,13,100),4,self.now)
        second=self.render(changed)['timeframes']['4h']['developing']
        self.assertNotEqual(first['wt1'],second['wt1'])
        self.assertEqual(self.render(raw)['timeframes']['4h']['developing'],first)

    def test_expired_future_malformed_and_gap_preview_are_rejected(self):
        raw=developing_yahoo_candle(self.bars,4,self.now)
        self.assertIsNone(self.render(raw,self.start+dt.timedelta(hours=4))['timeframes']['4h']['developing'])
        for changes in [{'high':1},{'underlying5mBars':12},
                        {'asOfET':(self.now+dt.timedelta(minutes=1)).isoformat()},
                        {'startET':(self.start+dt.timedelta(hours=4)).isoformat()}]:
            with self.subTest(changes=changes):
                self.assertIsNone(self.render(raw|changes)['timeframes']['4h']['developing'])

    def test_shadow_persists_partial_separately_from_confirmed_ledger(self):
        report=build_shadow(self.source,self.bars,self.now)
        for tf in ('4h','8h'):
            item=report['timeframes'][tf]
            self.assertIsNotNone(item['developingCandle'])
            self.assertEqual(item['newYahooCandles'],0)
            self.assertEqual(item['yahooCandles'],[])

    def test_both_publishers_include_preview_without_changing_backtest_or_archive(self):
        for symbol,module in [('NVDA',publish_nvda_wavetrend),('SOXL',publish_soxl_wavetrend)]:
            with self.subTest(symbol=symbol),tempfile.TemporaryDirectory() as folder:
                src=Path('data/research/'+symbol.lower()+'-wavetrend.json')
                before=src.read_bytes()
                source=json.loads(before)
                day=dt.datetime.fromisoformat(source['timeframes']['4h']['latest']['endET']).date()+dt.timedelta(days=1)
                while day.weekday()>=5:day+=dt.timedelta(days=1)
                start=dt.datetime.combine(day,dt.time(4),NY)
                now=start+dt.timedelta(hours=1,minutes=2)
                shadow=Path(folder)/'shadow.json'
                shadow.write_text(json.dumps({'symbol':symbol,'timeframes':{
                    tf:{'developingCandle':developing_yahoo_candle(bars(start),h,now)}
                    for tf,h in [('4h',4),('8h',8)]}}))
                with patch.object(module,'presentation',side_effect=lambda s:presentation(s,shadow,now)):
                    result=module.publish(dst=Path(folder)/'feed.json')
                for tf in ('4h','8h'):
                    series=result['timeframes'][tf]
                    self.assertIsNotNone(series['developing'])
                    self.assertNotEqual(series['latest']['endET'],series['developing']['endET'])
                    self.assertEqual(len(series['candles']),48)
                    self.assertTrue(all(c.get('isConfirmed') is not False for c in series['candles']))
                self.assertEqual(src.read_bytes(),before)
                if symbol=='SOXL':
                    report=json.loads(Path('data/research/soxl-wavetrend-backtest.json').read_text())
                    expected=report['timeframes']['4h']['zeroCosts']['finalValue']
                    self.assertEqual(result['backtest']['timeframes']['4h']['zeroCosts']['finalValue'],expected)
