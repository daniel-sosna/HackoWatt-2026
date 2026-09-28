from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from hackowatt.renewable import (ECONOMIC_MODES, energy_balance,
                                 learn_habit_constraints, local_tariff,
                                 normalized_pv_profile,
                                 prepare_flexible_events)
from hackowatt.components.renewable_energy import (apply_model_profile,
                                                    build_issued_forecast_payload)


class RenewableEnergyTests(unittest.TestCase):
    def test_dashboard_embeds_data_as_javascript_not_visible_text(self):
        template = (ROOT / 'src' / 'hackowatt' / 'renewable_dashboard.html').read_text(
            encoding='utf-8')
        self.assertIn('<script>/* EMBED_DATA */</script>', template)

    def test_hackathon_tariff_and_energy_balance(self):
        index = pd.date_range('2025-01-01', periods=24, freq='h', tz='UTC')
        tariff = local_tariff(index, ECONOMIC_MODES['hackathon'])
        local_hours = index.tz_convert('Europe/Warsaw').hour
        expected = np.select([local_hours < 6, local_hours < 17, local_hours < 22],
                             [.18, .28, .40], default=.28)
        np.testing.assert_allclose(tariff, expected)
        result = energy_balance([1, 1, 1], [0, .4, 1.5], [.2, .2, .2], .08)
        np.testing.assert_allclose(result['self_used_kwh'], [0, .4, 1])
        np.testing.assert_allclose(result['grid_import_kwh'], [1, .6, 0])
        np.testing.assert_allclose(result['grid_export_kwh'], [0, 0, .5])
        self.assertAlmostEqual(result['grid_cost'].sum(), .28)

    def test_solar_shape_is_normalized_to_explicit_yield(self):
        # Complete Europe/Warsaw calendar years expressed on the UTC timeline.
        index = pd.date_range('2023-12-31 23:00', '2025-12-31 22:00', freq='h', tz='UTC')
        radiation = np.maximum(np.sin(np.arange(len(index)) * np.pi / 12), 0)
        hourly = pd.DataFrame({'timestamp_utc': index, 'shortwave_radiation_instant': radiation})
        profile = normalized_pv_profile(hourly, 975)
        self.assertAlmostEqual(profile.sum(), 1950, places=8)
        self.assertTrue((profile >= 0).all())

    def test_habit_defaults_are_learned_and_remain_editable_values(self):
        events = pd.DataFrame({
            'device': ['washing_machine'] * 5 + ['dishwasher'] * 3,
            'start_utc': pd.date_range('2025-01-01 08:00', periods=8, freq='25h', tz='UTC'),
            'duration_minutes': [90] * 5 + [150] * 3,
            'energy_kwh': [.8] * 5 + [1.] * 3,
        })
        learned = learn_habit_constraints(events)
        self.assertEqual(learned['washing_machine']['events'], 5)
        self.assertEqual(learned['dishwasher']['events'], 3)
        self.assertLess(learned['washing_machine']['earliest_start_hour'],
                        learned['washing_machine']['latest_finish_hour'])
        self.assertEqual(learned['space_heating']['automation'], 'model-required')

    def test_flexible_event_encoding_preserves_energy_and_base_load(self):
        index = pd.date_range('2025-01-01', periods=8, freq='h', tz='UTC')
        events = pd.DataFrame({
            'device': ['washing_machine'], 'person': ['household'],
            'start_utc': ['2025-01-01T01:30:00+00:00'],
            'end_utc': ['2025-01-01T03:00:00+00:00'],
            'duration_minutes': [90], 'energy_kwh': [.9], 'trigger': ['laundry'],
        })
        seed = pd.DataFrame({'timestamp_utc': index, 'total_kwh': np.full(8, 2.)})
        encoded, provisional_base = prepare_flexible_events(seed, events)
        reconstructed = seed.total_kwh.to_numpy() - provisional_base
        hourly = seed.copy()
        hourly['total_kwh'] = reconstructed + .2
        encoded, base = prepare_flexible_events(hourly, events)
        self.assertAlmostEqual(sum(encoded[0]['profile']), .9, places=6)
        self.assertAlmostEqual(base.sum(), 1.6, places=5)
        rebuilt = base.copy()
        start = encoded[0]['startIndex']
        rebuilt[start:start + len(encoded[0]['profile'])] += encoded[0]['profile']
        np.testing.assert_allclose(rebuilt, hourly.total_kwh, atol=1e-6)

    def test_extended_device_and_thermal_proxy_encoding(self):
        index = pd.date_range('2025-01-01', periods=5, freq='h', tz='UTC')
        hourly = pd.DataFrame({
            'timestamp_utc': index, 'total_kwh': [1, 1, 1, 1, 1],
            'space_heating_kwh': [.4, 0, 0, 0, 0],
            'water_heater_kwh': [0, .6, 0, 0, 0],
        })
        events = pd.DataFrame({
            'device': ['tv'], 'person': ['household'],
            'start_utc': ['2025-01-01T02:00:00+00:00'],
            'end_utc': ['2025-01-01T03:00:00+00:00'],
            'duration_minutes': [60], 'energy_kwh': [.11],
            'trigger': ['scheduled_screen_or_work'],
        })
        encoded, base = prepare_flexible_events(hourly, events)
        self.assertEqual({row['category'] for row in encoded},
                         {'tv', 'space_heating', 'water_heater'})
        self.assertEqual(sum(row['proxy'] for row in encoded), 2)
        self.assertAlmostEqual(base.sum() + sum(row['energyKwh'] for row in encoded), 5, places=5)

    def test_colleague_model_profile_contract(self):
        index = pd.date_range('2025-01-01', periods=3, freq='h', tz='UTC')
        hourly = pd.DataFrame({'timestamp_utc': index, 'total_kwh': [1., 1., 1.],
                               'occupancy_mean': [1., 1., 1.]})
        profile = pd.DataFrame({'timestamp_utc': index, 'load_kwh': [2., 3., 4.],
                                'occupancy_people': [0, 2, 4], 'model_id': ['team-v1'] * 3})
        path = ROOT / 'results' / 'model-profile-test.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            profile.to_csv(path, index=False)
            result = apply_model_profile(hourly, path)
            self.assertEqual(result.total_kwh.tolist(), [2., 3., 4.])
            self.assertEqual(result.occupancy_mean.tolist(), [0., 2., 4.])
            self.assertEqual(result.attrs['load_source'], 'model profile: team-v1')
        finally:
            path.unlink(missing_ok=True)

    def test_issued_forecast_and_sensor_contract(self):
        index = pd.date_range('2026-09-29', periods=24, freq='h', tz='UTC')
        forecast = pd.DataFrame({
            'timestamp_utc': index, 'load_kwh': np.linspace(.5, 2, 24),
            'outdoor_c': np.linspace(-5, 8, 24), 'wind_ms': 2,
            'radiation_wm2': np.maximum(0, 700 * np.sin(np.arange(24) * np.pi / 24)),
            'model_id': 'team-live-v1',
        })
        folder = ROOT / 'results'
        forecast_path, sensor_path = folder / 'issued-test.csv', folder / 'sensor-test.json'
        folder.mkdir(parents=True, exist_ok=True)
        try:
            forecast.to_csv(forecast_path, index=False)
            sensor_path.write_text('{"indoor_c": 20.7, "tank_c": 51}', encoding='utf-8')
            payload = build_issued_forecast_payload(forecast_path, sensor_path)
            self.assertTrue(payload['available'])
            self.assertTrue(payload['isLive'])
            self.assertEqual(payload['modelId'], 'team-live-v1')
            self.assertEqual(payload['initialIndoorC'], 20.7)
            self.assertEqual(payload['initialTankC'], 51)
            self.assertEqual(len(payload['pvKwhPerKwpAt1000Yield']), 24)
            self.assertEqual(payload['outdoorC'][0], -5)
        finally:
            forecast_path.unlink(missing_ok=True)
            sensor_path.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
