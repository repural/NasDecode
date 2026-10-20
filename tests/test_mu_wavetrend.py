import datetime as dt
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import research_nvda_wavetrend as collector
from scripts.audit_mu_wavetrend import audit


class MUResearchTests(unittest.TestCase):
    def test_provider_request_uses_mu_ticker(self):
        with patch.object(collector, 'LAST_FETCH', 0), patch.object(
                collector.urllib.request, 'urlopen', return_value=io.StringIO('{"status":"OK","results":[]}')) as fetch:
            rows, status = collector.fetch_bars(dt.date(2026, 1, 2), dt.date(2026, 1, 3), 'test-only', 'MU')
        self.assertEqual(status, 'ok')
        self.assertEqual(rows, [])
        url = fetch.call_args.args[0].full_url
        self.assertIn('/ticker/MU/range/5/minute/', url)
        self.assertNotIn('/NVDA/', url)

    def test_build_records_mu_provenance(self):
        with patch.dict('os.environ', {'MASSIVE_API_KEY': 'test-only'}), patch.object(
                collector, 'load_extended_bars', return_value=([], [])) as load:
            doc = collector.build(365, dt.datetime(2026, 10, 20, tzinfo=collector.NY), 'MU')
        self.assertEqual(doc['symbol'], 'MU')
        self.assertEqual(load.call_args.args[-1], 'MU')

    def fixture(self):
        # Reuse the existing verified candle shape solely as an offline audit fixture.
        source = json.loads(Path('data/research/nvda-wavetrend.json').read_text())
        source['symbol'] = 'MU'
        daily = json.loads(Path('data/history/mu-daily.json').read_text())
        return source, daily

    def test_audit_accepts_ordered_complete_fixture(self):
        source, daily = self.fixture()
        result = audit(source, daily)
        self.assertEqual(result['symbol'], 'MU')
        self.assertGreater(result['timeframes']['8h']['candles'], 100)

    def test_audit_rejects_missing_timeframe_bucket(self):
        source, daily = self.fixture()
        source['timeframes']['4h']['candles'].pop(105)
        with self.assertRaisesRegex(ValueError, 'missing MU timeframe buckets'):
            audit(source, daily)

    def test_audit_rejects_duplicate_timestamp(self):
        source, daily = self.fixture()
        source['timeframes']['4h']['candles'].insert(101, source['timeframes']['4h']['candles'][100])
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            audit(source, daily)
