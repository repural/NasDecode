import datetime as dt
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import research_nvda_wavetrend as collector
from scripts.audit_googl_wavetrend import audit


class GOOGLTests(unittest.TestCase):
    def test_class_a_provider_request(self):
        with patch.object(collector,'LAST_FETCH',0),patch.object(collector.urllib.request,'urlopen',return_value=io.StringIO('{"status":"OK","results":[]}')) as request:
            rows,status=collector.fetch_bars(dt.date(2026,1,2),dt.date(2026,1,3),'test-only','GOOGL')
        self.assertEqual(status,'ok')
        self.assertIn('/ticker/GOOGL/',request.call_args.args[0].full_url)
        self.assertIn('limit=50000',request.call_args.args[0].full_url)

    def fixture(self):
        source=json.loads(Path('data/research/nvda-wavetrend.json').read_text())
        source['symbol']='GOOGL' # Candle-shape fixture only; never analysis input.
        return source,json.loads(Path('data/history/nvda-daily.json').read_text())

    def test_complete_fixture_and_wrong_symbol(self):
        source,calendar=self.fixture()
        self.assertEqual(audit(source,calendar)['timeframes']['4h']['evaluationMissingBuckets'],{})
        source['symbol']='GOOG'
        with self.assertRaises(ValueError):audit(source,calendar)

    def test_missing_evaluation_bucket_rejected(self):
        source,calendar=self.fixture();rows=source['timeframes']['4h']['candles']
        rows.pop(next(i for i,c in enumerate(rows) if c['startET'][:10]=='2026-01-05'))
        with self.assertRaisesRegex(ValueError,'Missing GOOGL evaluation buckets'):audit(source,calendar)
