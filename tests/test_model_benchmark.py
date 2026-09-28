from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from hackowatt.ml_benchmark import LAG_NAMES, _recursive_residual_forecast, prepare_training_data


class ZeroRegressor:
    def predict(self, x):
        return np.zeros(len(x))


class ModelBenchmarkPreparationTests(unittest.TestCase):
    def test_preparation_writes_separate_bounded_forecast_copies(self):
        source = ROOT / 'results/default/hourly.csv'
        source_bytes = source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            prepared = prepare_training_data(source, Path(directory))
            self.assertEqual(len(prepared.test), 168)
            self.assertEqual(prepared.manifest['forecast_start_local'], '2025-05-01T00:00:00+02:00')
            self.assertEqual(prepared.manifest['reported_horizons_hours'], [24, 72, 168])
            self.assertTrue((Path(directory)/'train_model_dataset.csv').exists())
            self.assertTrue((Path(directory)/'test_model_dataset.csv').exists())
            self.assertTrue((Path(directory)/'feature_manifest.json').exists())
            self.assertIn('month', prepared.base_features.columns)
            self.assertIn('day_of_week', prepared.base_features.columns)
            self.assertIn('hour', prepared.base_features.columns)
            self.assertIn('vacation_summer', prepared.base_features.columns)
            self.assertNotIn('occupancy_mean', prepared.base_features.columns)
            self.assertTrue(set(LAG_NAMES).issubset(prepared.train.columns))
        self.assertEqual(source.read_bytes(), source_bytes)

    def test_residual_forecast_preserves_prior_week_when_correction_is_zero(self):
        index = pd.date_range('2025-01-01', periods=400, freq='h', tz='UTC')
        base = pd.DataFrame({'hour': index.hour, 'temperature': 10.0}, index=index)
        weekly_pattern = np.arange(168, dtype=float) / 10
        target = np.resize(weekly_pattern, len(index))

        forecast = _recursive_residual_forecast(ZeroRegressor(), base, np.zeros(len(index)), target, 220, 388)

        np.testing.assert_allclose(forecast, target[52:220])


if __name__ == '__main__':
    unittest.main()
