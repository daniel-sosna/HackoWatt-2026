from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hackowatt.analysis import peak_hours


class AnalysisTests(unittest.TestCase):
    def test_peak_hours_accepts_generated_local_timestamp(self):
        source = pd.DataFrame({
            "timestamp_utc": pd.date_range("2025-01-01", periods=3, freq="h", tz="UTC"),
            "timestamp_local": ["old"] * 3,
            "total_kwh": [1.0, 3.0, 2.0],
            "space_heating_kwh": [0.2, 1.5, 0.1],
            "water_heater_kwh": [0.1, 0.2, 1.0],
        })
        peaks = peak_hours(source, 2)
        self.assertEqual(peaks.total_kwh.tolist(), [3.0, 2.0])
        self.assertEqual(peaks.dominant_known_load.tolist(), ["space_heating", "water_heater"])
        self.assertNotEqual(peaks.timestamp_local.iloc[0], "old")


if __name__ == "__main__":
    unittest.main()
