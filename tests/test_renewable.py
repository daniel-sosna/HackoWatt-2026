from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from hackowatt.renewable import (ECONOMIC_MODES, energy_balance, local_tariff,
                                 evaluate_pv, normalized_pv_profile, prepare_flexible_events)


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

    def test_pv_evaluation_keeps_energy_flow_and_economics_together(self):
        index = pd.date_range('2025-01-01', periods=24, freq='h', tz='UTC')
        hourly = pd.DataFrame({
            'timestamp_utc': index,
            'total_kwh': np.full(24, 1.0),
            'shortwave_radiation_instant': np.maximum(np.sin(np.arange(24) * np.pi / 24), 0),
        })
        result = evaluate_pv(hourly, 2.0, 900, ECONOMIC_MODES['hackathon'])
        self.assertAlmostEqual(result['pv_kwh'], 1800, places=8)
        self.assertLessEqual(result['self_used_kwh'], 24)
        self.assertEqual(result['capex'], 2600)
        self.assertGreater(result['annual_savings'], 0)

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

if __name__ == '__main__':
    unittest.main()
