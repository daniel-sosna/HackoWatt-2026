from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hackowatt.data import load_weather
from hackowatt.weather import OpenMeteoForecastProvider


class OpenMeteoForecastTests(unittest.TestCase):
    def test_response_uses_canonical_weather_columns_and_utc_times(self):
        payload = {
            "hourly": {
                "time": ["2026-09-29T10:00", "2026-09-29T11:00"],
                "temperature_2m": [12.0, 13.0],
                "relative_humidity_2m": [70, 65],
                "wind_speed_10m": [10, 12],
                "cloud_cover": [80, 60],
                "precipitation": [0.2, 0.0],
                "snowfall": [0, 0],
                "shortwave_radiation": [100, 200],
            }
        }

        result = OpenMeteoForecastProvider.parse_response(
            payload, "2026-09-29T07:00:00+00:00")

        self.assertEqual(list(result.columns), [
            "time", "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
            "cloud_cover", "precipitation", "snowfall",
            "shortwave_radiation_instant", "issue_time_utc",
        ])
        self.assertEqual(result.loc[0, "time"], "2026-09-29 10:00:00")
        self.assertEqual(result.loc[0, "shortwave_radiation_instant"], 100)
        self.assertTrue((pd.to_datetime(result["time"], utc=True).diff().dropna()
                         == pd.Timedelta(hours=1)).all())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecast.csv"
            result.to_csv(path, index=False)
            weather, _ = load_weather(path, {
                "weather": {"time_mode": "UTC", "wind_unit": "km/h"},
            })
        self.assertEqual(len(weather), 2)
        self.assertAlmostEqual(weather.iloc[0]["wind_ms"], 10 / 3.6)

    def test_response_rejects_missing_hourly_values(self):
        payload = {"hourly": {
            "time": ["2026-09-29T10:00"],
            "temperature_2m": [12.0],
        }}
        with self.assertRaisesRegex(ValueError, "relative_humidity_2m"):
            OpenMeteoForecastProvider.parse_response(
                payload, "2026-09-29T07:00:00+00:00")

    def test_forecast_length_is_bounded(self):
        for days in (0, 17):
            with self.subTest(days=days), self.assertRaises(ValueError):
                OpenMeteoForecastProvider(days)


if __name__ == "__main__":
    unittest.main()
