from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from hackowatt.components.renewable_energy import (apply_model_profile,
                                                    build_issued_forecast_payload)
from hackowatt.renewable import (ECONOMIC_MODES, energy_balance, local_tariff,
                                 normalized_pv_profile, prepare_flexible_events)


class RenewableEnergyTests(unittest.TestCase):
    def test_tariff_and_energy_balance(self):
        index = pd.date_range('2025-01-01', periods=24, freq='h', tz='UTC')
        tariff = local_tariff(index, ECONOMIC_MODES['hackathon'])
        local_hours = index.tz_convert('Europe/Warsaw').hour
        expected = np.select([local_hours < 6, local_hours < 17, local_hours < 22],
                             [.18, .28, .40], default=.28)
        np.testing.assert_allclose(tariff, expected)
        result = energy_balance([1, 1, 1], [0, .4, 1.5], [.2, .2, .2], .08)
        np.testing.assert_allclose(result['grid_import_kwh'], [1, .6, 0])
        np.testing.assert_allclose(result['grid_export_kwh'], [0, 0, .5])
        self.assertAlmostEqual(result['grid_cost'].sum(), .28)

    def test_pv_profile_preserves_stated_specific_yield(self):
        index = pd.date_range('2023-12-31 23:00', '2024-12-31 22:00',
                              freq='h', tz='UTC')
        radiation = np.maximum(np.sin(np.arange(len(index)) * np.pi / 12), 0)
        hourly = pd.DataFrame({'timestamp_utc': index,
                               'shortwave_radiation_instant': radiation})
        profile = normalized_pv_profile(hourly, 975)
        self.assertAlmostEqual(profile.sum(), 975, places=8)

    def test_flexible_event_encoding_preserves_energy(self):
        index = pd.date_range('2025-01-01', periods=8, freq='h', tz='UTC')
        events = pd.DataFrame({
            'device': ['washing_machine'], 'person': ['household'],
            'start_utc': ['2025-01-01T01:30:00+00:00'],
            'end_utc': ['2025-01-01T03:00:00+00:00'],
            'duration_minutes': [90], 'energy_kwh': [.9], 'trigger': ['laundry'],
        })
        seed = pd.DataFrame({'timestamp_utc': index, 'total_kwh': np.full(8, 2.)})
        encoded, provisional_base = prepare_flexible_events(seed, events)
        hourly = seed.copy()
        hourly['total_kwh'] = seed.total_kwh.to_numpy() - provisional_base + .2
        encoded, base = prepare_flexible_events(hourly, events)
        self.assertAlmostEqual(sum(encoded[0]['profile']), .9, places=6)
        self.assertEqual(encoded[0]['startMinute'], 30)
        self.assertAlmostEqual(base.sum() + encoded[0]['energyKwh'],
                               hourly.total_kwh.sum(), places=5)

    def test_external_profile_contracts(self):
        index = pd.date_range('2026-09-29', periods=24, freq='h', tz='UTC')
        hourly = pd.DataFrame({'timestamp_utc': index, 'total_kwh': 1.,
                               'occupancy_mean': 1.})
        profile = pd.DataFrame({'timestamp_utc': index,
                                'load_kwh': np.linspace(.5, 2, 24),
                                'occupancy_people': 2, 'model_id': 'team-v1'})
        forecast = profile.copy()
        forecast['outdoor_c'] = np.linspace(-5, 8, 24)
        forecast['wind_ms'] = 2
        forecast['radiation_wm2'] = np.maximum(
            0, 700 * np.sin(np.arange(24) * np.pi / 24))
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            profile_path = folder / 'profile.csv'
            forecast_path = folder / 'forecast.csv'
            sensor_path = folder / 'sensor.json'
            profile.to_csv(profile_path, index=False)
            forecast.to_csv(forecast_path, index=False)
            sensor_path.write_text('{"indoor_c": 20.7, "tank_c": 51}', encoding='utf-8')
            applied = apply_model_profile(hourly, profile_path)
            payload = build_issued_forecast_payload(forecast_path, sensor_path)
            self.assertFalse(payload['isLive'])
            self.assertFalse(payload['thermalInputsAvailable'])
            self.assertIsNone(payload['issueTimeUtc'])
            for column, value in [('load_kwh', -1), ('wind_ms', -2),
                                  ('radiation_wm2', float('nan'))]:
                with self.subTest(column=column):
                    broken = forecast.copy()
                    broken.loc[0, column] = value
                    broken.to_csv(forecast_path, index=False)
                    with self.assertRaises(ValueError):
                        build_issued_forecast_payload(forecast_path)
            forecast['lower_kwh'], forecast['upper_kwh'] = 2., 1.
            forecast.to_csv(forecast_path, index=False)
            with self.assertRaisesRegex(ValueError, 'lower_kwh'):
                build_issued_forecast_payload(forecast_path)
        self.assertEqual(applied.attrs['load_source'], 'model profile: team-v1')
        self.assertEqual(payload['modelId'], 'team-v1')
        self.assertEqual(payload['initialIndoorC'], 20.7)
        self.assertEqual(payload['outdoorC'][0], -5)


if __name__ == '__main__':
    unittest.main()
