import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as dashboard
from configuration import load_beaches


class DashboardChecks(unittest.TestCase):
    def setUp(self):
        dashboard.app.config['TESTING'] = True
        dashboard.cache['data'] = None
        dashboard.cache['timestamp'] = 0
        self.client = dashboard.app.test_client()

    def test_health_exposes_release_identity_without_contacting_providers(self):
        with patch.dict('os.environ', {'ATRIA_GIT_SHA': 'fixture-revision'}), \
             patch.object(dashboard, 'build_dashboard') as provider:
            response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'status': 'ok', 'revision': 'fixture-revision'})
        provider.assert_not_called()

    def test_home_navigation_comes_from_runtime_configuration(self):
        with patch.dict('os.environ', {'HOME_URL': 'https://example.invalid/home'}):
            response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'https://example.invalid/home', response.data)
        self.assertNotIn(b'jealrodos', response.data)

    def test_successful_data_is_cached_between_requests(self):
        fixture = {'tide': {'current': 'fixture'}, 'beaches': [{'name': 'Example beach'}]}
        with patch.object(dashboard, 'build_dashboard', return_value=fixture) as provider:
            first = self.client.get('/api/beaches')
            second = self.client.get('/api/beaches')
        self.assertEqual(first.get_json(), fixture)
        self.assertEqual(second.get_json(), fixture)
        self.assertEqual(provider.call_count, 1)

    def test_shared_provider_failure_is_an_api_error_and_does_not_poison_cache(self):
        with patch.object(dashboard, 'build_dashboard', side_effect=RuntimeError('Fixture provider unavailable')):
            response = self.client.get('/api/beaches')
        self.assertEqual(response.status_code, 500)
        self.assertIsNone(dashboard.cache['data'])

    def test_partial_location_failure_preserves_other_locations_and_order(self):
        locations = [{'name': 'Example one', 'type': 'sea', 'lat': 1, 'lon': 1},
                     {'name': 'Example two', 'type': 'sea', 'lat': 2, 'lon': 2}]

        def collect(beach, weather):
            if beach['name'] == 'Example two':
                raise RuntimeError('Fixture regional provider unavailable')
            return {**beach, 'weather': weather}

        with patch.object(dashboard, 'BEACHES', locations), \
             patch.object(dashboard, 'get_all_weather', return_value=[{'temperature': 15}, {'temperature': 16}]), \
             patch.object(dashboard, 'get_beach_data', side_effect=collect), \
             patch.object(dashboard, 'get_tide', return_value={'current': 'fixture'}):
            result = dashboard.build_dashboard()
        self.assertEqual([item['name'] for item in result['beaches']], ['Example one', 'Example two'])
        self.assertNotIn('error', result['beaches'][0])
        self.assertIn('error', result['beaches'][1])
        self.assertEqual(result['beaches'][1]['weather'], {'temperature': 16})

    def test_private_location_file_and_invalid_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'locations.json'
            values = [{'name': 'Example coast', 'type': 'sea', 'lat': 40, 'lon': -8}]
            path.write_text(json.dumps(values), encoding='utf-8')
            with patch.dict('os.environ', {'BEACH_CONFIG_FILE': str(path)}):
                self.assertEqual(load_beaches(), values)
            path.write_text(json.dumps(values + values), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'unique'):
                load_beaches(path)
            path.write_text(json.dumps([{**values[0], 'lat': 150}]), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'coordinates'):
                load_beaches(path)


if __name__ == '__main__':
    unittest.main()
