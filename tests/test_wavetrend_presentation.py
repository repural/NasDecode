import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.wavetrend_presentation import presentation

NY = ZoneInfo('America/New_York')


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(Path('data/research/nvda-wavetrend.json').read_text())
        last = dt.datetime.fromisoformat(self.source['timeframes']['4h']['latest']['endET'])
        day = last.date() + dt.timedelta(days=1)
        while day.weekday() >= 5:
            day += dt.timedelta(days=1)
        self.start = dt.datetime.combine(day, dt.time(4), NY)
        self.now = self.start + dt.timedelta(hours=9)

    def observation(self, hours):
        return {'startET': self.start.isoformat(),
                'endET': (self.start + dt.timedelta(hours=hours)).isoformat(),
                'open': 200, 'high': 202, 'low': 199, 'close': 201,
                'wt1': 999, 'wt2': 999, 'cross': 'bullish'}

    def render(self, shadow, now=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'shadow.json'
            path.write_text(json.dumps(shadow))
            return presentation(self.source, path, now or self.now)

    def test_overlay_recalculates_wt_without_modifying_canonical(self):
        before = json.dumps(self.source)
        shadow = {'symbol': 'NVDA', 'observations': {tf: {self.start.isoformat(): self.observation(h)}
                                                    for tf, h in [('4h', 4), ('8h', 8)]}}
        result = self.render(shadow)
        self.assertEqual(result['displaySource'], 'Massive + Yahoo provisional')
        for tf in ('4h', '8h'):
            self.assertEqual(result['timeframes'][tf]['latest']['provider'], 'Yahoo provisional')
            self.assertNotEqual(result['timeframes'][tf]['latest']['wt1'], 999)
        self.assertEqual(json.dumps(self.source), before)

    def test_massive_replaces_previously_saved_yahoo(self):
        baseline = self.source['timeframes']['4h']['latest']
        shadow = {'observations': {'4h': {baseline['startET']: {**baseline, 'close': 1000}}}}
        result = self.render(shadow)
        self.assertEqual(result['timeframes']['4h']['latest']['close'], baseline['close'])
        self.assertEqual(result['displaySource'], 'Massive')

    def test_developing_candle_is_not_published(self):
        shadow = {'observations': {'4h': {self.start.isoformat(): self.observation(4)}}}
        result = self.render(shadow, self.start + dt.timedelta(hours=4, minutes=2))
        self.assertEqual(result['timeframes']['4h']['yahooCandles'], 0)

    def test_missing_first_candle_is_not_bridged(self):
        candle = self.observation(4)
        candle['startET'] = (self.start + dt.timedelta(hours=4)).isoformat()
        candle['endET'] = (self.start + dt.timedelta(hours=8)).isoformat()
        result = self.render({'observations': {'4h': {candle['startET']: candle}}})
        self.assertEqual(result['timeframes']['4h']['yahooCandles'], 0)

    def test_wrong_symbol_refused(self):
        with self.assertRaises(ValueError):
            self.render({'symbol': 'SOXL'})

    def test_bad_ohlc_is_not_published(self):
        candle = self.observation(4)
        candle['high'] = 190
        result = self.render({'observations': {'4h': {candle['startET']: candle}}})
        self.assertEqual(result['timeframes']['4h']['yahooCandles'], 0)
