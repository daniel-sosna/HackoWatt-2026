from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hackowatt.data import load_forecast_weather
from hackowatt.weather import OpenMeteoForecastProvider


class OpenMeteoForecastTests(unittest.TestCase):
    def test_response_matches_issue_date_forecast_weather_contract(self):
        payload = {
            "hourly": {
                "time": ["2026-09-29T08:00", "2026-09-29T09:00"],
                "temperature_2m": [12.0, 13.0],
                "relative_humidity_2m": [70, 65],
                "wind_speed_10m": [10, 12],
                "cloud_cover": [80, 60],
                "snowfall": [0, 0],
                "shortwave_radiation": [100, 200],
            }
        }

        result = OpenMeteoForecastProvider.parse_response(
            payload, "2026-09-29T07:00:00+00:00")

        self.assertEqual(list(result.columns), [
            "time", "temperature_2m_C", "relative_humidity_2m_pct",
            "wind_speed_10m_kmh", "cloud_cover_pct", "snowfall_cm",
            "shortwave_radiation_wm2", "issue_time_utc",
        ])
        self.assertEqual(result.loc[0, "time"], "2026-09-29 10:00:00+02:00")
        self.assertEqual(result.loc[0, "shortwave_radiation_wm2"], 100)
        self.assertTrue((pd.to_datetime(result["time"], utc=True).diff().dropna()
                         == pd.Timedelta(hours=1)).all())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecast.csv"
            result.to_csv(path, index=False)
            weather = load_forecast_weather(path)
        self.assertEqual(len(weather), 2)
        self.assertAlmostEqual(weather.iloc[0]["wind_ms"], 10 / 3.6)
        self.assertEqual(weather.iloc[0]["precipitation"], 0)
        self.assertEqual(weather.index[0], pd.Timestamp("2026-09-29T08:00:00Z"))

    def test_response_preserves_both_fall_back_hours(self):
        payload = {
            "hourly": {
                "time": ["2026-10-25T00:00", "2026-10-25T01:00", "2026-10-25T02:00"],
                "temperature_2m": [8.0, 7.0, 6.0],
                "relative_humidity_2m": [80, 82, 84],
                "wind_speed_10m": [10, 11, 12],
                "cloud_cover": [50, 55, 60],
                "snowfall": [0, 0, 0],
                "shortwave_radiation": [0, 0, 0],
            }
        }

        result = OpenMeteoForecastProvider.parse_response(
            payload, "2026-10-24T22:00:00+00:00")
        self.assertEqual(result["time"].tolist(), [
            "2026-10-25 02:00:00+02:00",
            "2026-10-25 02:00:00+01:00",
            "2026-10-25 03:00:00+01:00",
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecast.csv"
            result.to_csv(path, index=False)
            weather = load_forecast_weather(path)
        self.assertEqual(len(weather.index.unique()), 3)
        self.assertTrue((weather.index[1:] - weather.index[:-1]
                         == pd.Timedelta(hours=1)).all())

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
