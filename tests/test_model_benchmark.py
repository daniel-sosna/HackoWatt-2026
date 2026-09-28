from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from hackowatt.ml_benchmark import LAG_NAMES, prepare_training_data


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


if __name__ == '__main__':
    unittest.main()
