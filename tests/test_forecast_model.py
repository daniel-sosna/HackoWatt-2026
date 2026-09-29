from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from hackowatt.forecasting.issue_date import (LAG_NAMES, _recursive_residual_forecast,
                                               prepare_training_data)
from hackowatt.issue_date_forecast import selected_model_for_horizon


class ZeroRegressor:
    def predict(self, x):
        return np.zeros(len(x))


class ForecastModelPreparationTests(unittest.TestCase):
    @staticmethod
    def write_hourly_fixture(path: Path) -> None:
        """Write a minimal complete hourly contract without generated outputs."""
        index = pd.date_range('2025-01-01', periods=400, freq='h', tz='UTC')
        local = index.tz_convert('Europe/Warsaw')
        hour = np.arange(len(index))
        frame = pd.DataFrame({
            'timestamp_utc': index.astype(str),
            'timestamp_local': local.astype(str),
            'temperature_2m': 5.0 + np.sin(hour/24),
            'cloud_cover': 45.0,
            'relative_humidity_2m': 70.0,
            'wind_speed_10m': 12.0,
            'precipitation': 0.0,
            'snowfall': 0.0,
            'shortwave_radiation_instant': np.maximum(0.0, 300*np.sin((local.hour-6)*np.pi/12)),
            'wind_ms': 12.0/3.6,
            'public_holiday': False,
            'school_break': False,
            'family_vacation': False,
            'school_day': True,
            'ania_wfh': False,
            'marek_shift': 'off',
            'vacation_block': '',
            'fridge_kwh': 0.04,
            'router_kwh': 0.012,
            'standby_kwh': 0.035,
            'lighting_kwh': 0.08,
            'space_heating_kwh': 0.4,
            'water_heater_kwh': 0.3,
            'hot_water_mixed_l': 10.0,
            'occupancy_mean': 2.0,
        })
        frame['total_kwh'] = frame[['fridge_kwh', 'router_kwh', 'standby_kwh', 'lighting_kwh',
                                    'space_heating_kwh', 'water_heater_kwh']].sum(axis=1)
        frame.to_csv(path, index=False)

    def test_preparation_writes_separate_bounded_forecast_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'hourly.csv'
            self.write_hourly_fixture(source)
            source_bytes = source.read_bytes()
            issue_time = '2025-01-10 04:00:00+01:00'
            prepared = prepare_training_data(source, Path(directory)/'prepared', issue_time)
            self.assertEqual(len(prepared.test), 168)
            self.assertEqual(prepared.manifest['forecast_start_local'], pd.Timestamp(issue_time).isoformat())
            self.assertEqual(prepared.manifest['reported_horizons_hours'], [24, 72, 168])
            self.assertTrue((Path(directory)/'prepared'/'train_model_dataset.csv').exists())
            self.assertTrue((Path(directory)/'prepared'/'test_model_dataset.csv').exists())
            self.assertTrue((Path(directory)/'prepared'/'feature_manifest.json').exists())
            self.assertIn('month', prepared.base_features.columns)
            self.assertIn('day_of_week', prepared.base_features.columns)
            self.assertIn('hour', prepared.base_features.columns)
            self.assertIn('vacation_summer', prepared.base_features.columns)
            self.assertNotIn('occupancy_mean', prepared.base_features.columns)
            self.assertTrue(set(LAG_NAMES).issubset(prepared.train.columns))
            self.assertLess(prepared.manifest['train_end_utc'], prepared.manifest['test_start_utc'])
            self.assertEqual(source.read_bytes(), source_bytes)

    def test_selected_policy_accepts_only_exact_supported_horizons(self):
        self.assertEqual(selected_model_for_horizon(24), 'direct_random_forest')
        self.assertEqual(selected_model_for_horizon(72), 'modular_catboost')
        self.assertEqual(selected_model_for_horizon(168), 'modular_catboost')
        with self.assertRaises(ValueError):
            selected_model_for_horizon(48)

    def test_issued_weather_replaces_only_future_feature_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'hourly.csv'
            forecast_path = Path(directory) / 'issued_weather.csv'
            self.write_hourly_fixture(source)
            issue = pd.Timestamp('2025-01-10 04:00:00+01:00')
            local = pd.date_range(issue, periods=24, freq='h').tz_localize(None)
            pd.DataFrame({
                'time': local,
                'temperature_2m_C': 99.0,
                'relative_humidity_2m_pct': 70.0,
                'wind_speed_10m_kmh': 12.0,
                'cloud_cover_pct': 45.0,
                'snowfall_cm': 0.0,
                'shortwave_radiation_wm2': 0.0,
            }).to_csv(forecast_path, index=False)

            prepared = prepare_training_data(
                source, Path(directory) / 'prepared', issue.isoformat(), 24, forecast_path)

            cutoff = prepared.cutoff
            self.assertEqual(prepared.base_features['temperature_2m'].iloc[cutoff], 99.0)
            self.assertNotEqual(prepared.base_features['temperature_2m'].iloc[cutoff - 1], 99.0)
            self.assertIn('issued forecast:', prepared.manifest['forecast_weather_source'])

    def test_residual_forecast_preserves_prior_week_when_correction_is_zero(self):
        index = pd.date_range('2025-01-01', periods=400, freq='h', tz='UTC')
        base = pd.DataFrame({'hour': index.hour, 'temperature': 10.0}, index=index)
        weekly_pattern = np.arange(168, dtype=float) / 10
        target = np.resize(weekly_pattern, len(index))

        forecast = _recursive_residual_forecast(ZeroRegressor(), base, np.zeros(len(index)), target, 220, 388)

        np.testing.assert_allclose(forecast, target[52:220])


if __name__ == '__main__':
    unittest.main()
