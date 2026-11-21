import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import update_data

ROW = {'state': 'Uttar Pradesh', 'district': 'Lucknow', 'market': 'Lucknow',
       'commodity': 'Wheat', 'modal_price': '2300', 'arrival_date': '01/11/2026'}


class PriceFeedConnectionTests(unittest.TestCase):
    def test_data_gov_pagination_and_filter(self):
        calls = []
        def fake_get(url, **kwargs):
            params = parse_qs(urlparse(url).query)
            calls.append(params)
            return json.dumps({'records': [ROW] if params['offset'] == ['0'] else []}).encode()
        with patch.object(update_data, 'http_get', side_effect=fake_get):
            rows = update_data.fetch_data_gov(update_data.SAMPLE_DATA_GOV_API_KEY, state='Uttar Pradesh', max_records=20)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['modal_price'], 2300)
        self.assertEqual(calls[0]['filters[state]'], ['Uttar Pradesh'])
        self.assertEqual(calls[0]['limit'], ['10'])

    def test_authorised_feed_uses_server_side_bearer_and_normalises(self):
        with patch.object(update_data, 'http_get', return_value=json.dumps({'prices': [ROW]}).encode()) as request:
            rows = update_data.fetch_authorised_price_feed('https://example.gov/feed', 'secret', 'e-NAM trade feed')
        self.assertEqual(request.call_args.kwargs['headers'], {'Authorization': 'Bearer secret'})
        self.assertEqual(rows[0]['source'], 'e-NAM trade feed')
        self.assertNotIn('secret', json.dumps(rows))

    def test_failing_feed_keeps_old_snapshot_labelled_cached(self):
        row = update_data.format_record(ROW)
        prior = update_data.build_source_prices_snapshot({'enam_trade': {'status': 'live', 'records': [row]}}, checked_at='old')
        result = update_data.build_source_prices_snapshot({'enam_trade': {'status': 'error', 'records': []}}, previous=prior, checked_at='new')
        feed = next(f for f in result['feeds'] if f['id'] == 'enam_trade')
        self.assertEqual(feed['status'], 'cached')
        self.assertEqual(feed['data_updated_at'], 'old')
        self.assertEqual(feed['latest_check_status'], 'error')
        self.assertEqual(feed['records'][0]['modal_price'], 2300)

    def test_workflow_passes_all_feed_secrets_and_builds_snapshot(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/update.yml').read_text()
        for name in ('DATA_GOV_IN_API_KEY', 'ENAM_TRADE_FEED_URL', 'ENAM_TRADE_API_KEY',
                     'UP_EMANDI_TRADE_FEED_URL', 'UP_EMANDI_TRADE_API_KEY'):
            self.assertIn('secrets.' + name, workflow)
        self.assertIn('run: python update_data.py', workflow)
        self.assertIn('run: python scripts/build_dashboard_snapshot.py', workflow)

if __name__ == '__main__':
    unittest.main()
