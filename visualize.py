"""Build an offline interactive dashboard. Run this file in PyCharm after generate.py."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from hackowatt.behaviour import ACTIVITIES, PEOPLE

def build_dashboard(folder):
    folder=Path(folder)
    df=pd.read_csv(folder/'hourly.csv',dtype={'vacation_block':'string'},low_memory=False)
    people=pd.read_csv(folder/'residents_hourly.csv')
    report=json.loads((folder/'validation.json').read_text())
    energy=[c for c in df if c.endswith('_kwh') and c not in ('total_kwh','hot_water_unmet_kwh','thermal_residual_kwh')]
    data={'time':df.timestamp_local.tolist(),'energy_names':energy,'activities':ACTIVITIES,'people':{},
          'energy':df[energy].round(5).to_numpy().tolist(),
          'total':df.total_kwh.round(4).tolist(),'outdoor':df.temperature_2m.round(2).tolist(),
          'indoor':df.indoor_c.round(2).tolist(),'tank':df.tank_c.round(2).tolist(),
          'setpoint':df.setpoint_c.round(2).tolist(),'occupancy':df.occupancy_mean.round(3).tolist(),
          'family_vacation':df.family_vacation.astype(bool).tolist(),
          'night_ventilation':df.night_ventilation_active_fraction.round(3).tolist(),
          'comparison':pd.read_csv(folder/'eurostat_comparison.csv').replace({np.nan:None}).to_dict('records'),
          'report':report}
    for person in PEOPLE:
        p=people[people.person==person]
        data['people'][person]={'minutes':p[[a+'_minutes' for a in ACTIVITIES]].to_numpy().tolist(),
                                'home':p.home_minutes.tolist()}
    template=(ROOT/'src/hackowatt/dashboard.html').read_text(encoding='utf-8')
    html=template.replace('/* EMBED_DATA */', 'const D='+json.dumps(data,separators=(',',':'),ensure_ascii=False)+';')
    target=folder/'dashboard.html';target.write_text(html,encoding='utf-8')
    print(target)
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'results/default')
    args=parser.parse_args();build_dashboard(args.input)
