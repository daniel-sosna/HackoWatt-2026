import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hackowatt.data import load_config,load_weather,load_calendars,load_reference,resolve_house
from hackowatt.simulation.behaviour import simulate_behaviour,CODE,calibrate_probabilities,schedule_family_vacations
from hackowatt.simulation.devices import simulate_devices,cycle_profile
from hackowatt.simulation.thermal import rc_step,simulate_thermal

class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=load_config(ROOT/'config/default.json')
        cls.weather,cls.audit=load_weather(ROOT/'data/raw/silesia_weather_full.csv',cls.config)
        cls.public,cls.school=load_calendars(ROOT,cls.config)
        cls.ref=load_reference(ROOT/'data/raw/activity_time_use_full.csv')

    def test_dst_and_coverage(self):
        self.assertEqual(len(self.weather),17544)
        dates=self.weather.index.tz_convert('Europe/Warsaw').strftime('%Y-%m-%d')
        for d,n in [('2024-03-31',23),('2024-10-27',25),('2025-03-30',23),('2025-10-26',25)]:
            self.assertEqual(sum(dates==d),n)
        self.assertEqual(len(self.audit['dropped_nonexistent_local_hours']),2)
        self.assertEqual(len(self.audit['reused_ambiguous_local_hours']),2)
        self.assertAlmostEqual(self.weather.wind_ms.iloc[0],8.4/3.6)

    def test_missing_weather_fails(self):
        with tempfile.TemporaryDirectory() as td:
            raw=pd.read_csv(ROOT/'data/raw/silesia_weather_full.csv').drop(index=50)
            p=Path(td)/'weather.csv';raw.to_csv(p,index=False)
            with self.assertRaisesRegex(ValueError,'Missing weather'):
                load_weather(p,self.config)

    def test_calendar_correction_and_school(self):
        self.assertIn('2025-12-24',self.public)
        self.assertNotIn('2024-12-24',self.public)
        self.assertIn('2024-02-11',self.school)
        self.assertNotIn('2024-02-12',self.school)

    def test_manual_overrides_and_reproducibility(self):
        c=copy.deepcopy(self.config);c['house']['overrides']['floor_area_m2']=111
        first=resolve_house(c,np.random.default_rng(4));second=resolve_house(c,np.random.default_rng(4))
        self.assertEqual(first,second);self.assertEqual(first['floor_area_m2'],111)
        c['house']['mode']='manual'
        with self.assertRaises(ValueError):resolve_house(c,np.random.default_rng(4))
        c['house']['overrides']=first
        self.assertEqual(resolve_house(c,np.random.default_rng(900)),first)
        self.assertEqual(load_config(ROOT/'config/manual_example.json')['house']['mode'],'manual')

    def test_joint_vacation_uses_twenty_parental_workdays_per_year(self):
        labels=pd.date_range('2024-01-01','2025-12-31',freq='D').strftime('%Y-%m-%d').to_numpy()
        plan=schedule_family_vacations(labels,self.public,self.config['behaviour'],np.random.default_rng(12))
        for year in [2024,2025]:
            trip_dates=[pd.Timestamp(day) for day in plan if day.startswith(str(year))]
            charged=[day for day in trip_dates if day.weekday()<5 and day.strftime('%Y-%m-%d') not in self.public]
            self.assertEqual(len(charged),20)
            self.assertEqual({plan[d.strftime('%Y-%m-%d')].split('_')[0] for d in charged},{'summer','winter','spring'})
            self.assertEqual(sum(plan[d.strftime('%Y-%m-%d')].startswith('summer') for d in charged),10)

    def test_rc_analytic_energy_and_timestep_consistency(self):
        self.assertAlmostEqual(rc_step(20,0,0,.2,10,1),20*np.exp(-.02))
        direct=rc_step(20,0,4,.2,10,1)
        split=20
        for _ in range(60):split=rc_step(split,0,4,.2,10)
        self.assertAlmostEqual(direct,split,places=10)
        self.assertGreater(rc_step(15,-10,8,.2,10),rc_step(15,-10,3.5,.2,10))

    def test_cycle_energy_and_weather_probability(self):
        for minutes,kwh in [(90,.6),(90,1),(150,.8),(150,1.2)]:
            p=cycle_profile(minutes,kwh)
            self.assertAlmostEqual(p.sum()/60,kwh,places=12)
            self.assertTrue((p>=0).all())
        delta=np.array([0,.06,-.12,.03]*100)
        p=calibrate_probabilities(.136,delta)
        self.assertAlmostEqual(p.mean(),.136,places=10)
        self.assertTrue(np.all((p>=0)&(p<=1)))

    def test_three_day_integration_and_repeatability(self):
        weather=self.weather.iloc[:72]
        b=simulate_behaviour(weather,self.public,self.school,self.ref,self.config,np.random.default_rng(20))
        b2=simulate_behaviour(weather,self.public,self.school,self.ref,self.config,np.random.default_rng(20))
        np.testing.assert_array_equal(b['activity'],b2['activity'])
        np.testing.assert_array_equal(b['home'],b2['home'])
        self.assertEqual(b['activity'].shape,(4,4320))
        self.assertFalse(np.any((b['activity']==CODE['sleep'])&~b['home']))
        p,water,events=simulate_devices(b,weather,self.config,np.random.default_rng(21))
        awake=(b['home']&(b['activity']!=CODE['sleep'])).any(axis=0)
        self.assertFalse(np.any((p['lighting']>0)&~awake))
        h=resolve_house(self.config,np.random.default_rng(22))
        thermal=simulate_thermal(weather,b,p,water,h,self.config)
        for arr in list(p.values())+list(thermal.values()):self.assertTrue(np.isfinite(arr).all())
        self.assertTrue((thermal['space_heating']<=h['heating_capacity_kw']).all())
        self.assertTrue((thermal['water_heater']<=h['boiler_power_kw']).all())
        self.assertLess(float(np.abs(thermal['thermal_residual_kwh']).max()),1e-9)

if __name__=='__main__':unittest.main()
