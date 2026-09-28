from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from hackowatt.forecasting import (
    ComponentModel,
    FORBIDDEN_DIRECT_COLUMNS,
    HistogramBoostingRegressor,
    exogenous_frame,
    history_vector,
    load_hourly,
    metrics,
    seasonal_naive,
)


class ForecastingTests(unittest.TestCase):
    def test_feature_frame_excludes_target_and_future_state(self):
        timestamps = pd.date_range('2024-01-01', periods=200, freq='h', tz='UTC')
        frame = pd.DataFrame({
            'timestamp_utc': timestamps,
            'marek_shift': ['off'] * len(timestamps),
            'temperature_2m': 5.0,
            'total_kwh': 1.0,
            'indoor_temperature': 20.0,
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'hourly.csv'
            frame.to_csv(path, index=False)
            df = load_hourly(path)
        features = exogenous_frame(df)
        self.assertEqual(len(features), len(df))
        self.assertFalse(set(features.columns) & FORBIDDEN_DIRECT_COLUMNS)
        self.assertTrue(np.isfinite(features.to_numpy(float)).all())

    def test_stump_boosting_learns_a_nonconstant_signal(self):
        x = np.linspace(-1, 1, 240).reshape(-1, 1)
        y = np.where(x[:, 0] < 0, 0.2, 1.4)
        model = HistogramBoostingRegressor(n_estimators=40, learning_rate=.15,
                                           n_bins=12, min_samples_leaf=12).fit(x, y)
        prediction = model.predict(x)
        self.assertLess(np.mean((prediction-y)**2), np.var(y)*.08)
        self.assertGreater(prediction[-1], prediction[0])

    def test_component_model_keeps_weekly_pattern_without_future_actuals(self):
        index = pd.date_range('2024-01-01', periods=400, freq='h', tz='UTC')
        exog = pd.DataFrame({'calendar': np.zeros(400)}, index=index)
        target = 1.0 + .35*np.sin(2*np.pi*np.arange(400)/24)
        component = ComponentModel(['calendar'], HistogramBoostingRegressor(n_estimators=25)).fit(exog, target, 300)
        history = target[:300].tolist()
        predicted = []
        for i in range(300, 360):
            value = component.forecast_one(exog.iloc[i].to_numpy(float), history)
            predicted.append(value)
            history.append(value)
        np.testing.assert_allclose(predicted, target[132:192], atol=1e-8)

    def test_history_baseline_and_metrics_contract(self):
        values = np.arange(400, dtype=float)
        self.assertEqual(history_vector(values[:168].tolist()), [167., 144., 0., 155.5, 83.5])
        np.testing.assert_array_equal(seasonal_naive(values, 200, 24), values[32:56])
        actual = np.array([[1., 2.], [2., 4.]])
        result = metrics(actual, actual.copy())
        self.assertEqual(result['mae_kwh'], 0.0)
        self.assertEqual(result['rmse_kwh'], 0.0)
        self.assertEqual(result['n_forecasts'], 2)
        with self.assertRaises(ValueError):
            metrics(actual, np.array([1., 2.]))


if __name__ == '__main__':
    unittest.main()
