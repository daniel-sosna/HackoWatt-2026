"""Orchestration and documented hourly exports."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .inputs import load_config, load_weather, load_calendars, load_reference, resolve_house, hashes
from .behaviour import simulate_behaviour, PEOPLE, ACTIVITIES, CODE, REFERENCES
from .devices import simulate_devices, runs
from .thermal import simulate_thermal

def generate(root, config_path, output_override=None):
    root=Path(root);config=load_config(config_path)
    out=Path(output_override) if output_override else root/config['output']['directory']
    out.mkdir(parents=True,exist_ok=True)
    streams=[np.random.default_rng(s) for s in np.random.SeedSequence(config['seed']).spawn(3)]
    house=resolve_house(config,streams[0])
    weather,audit=load_weather(root/'data/raw/silesia_weather_full.csv',config)
    public,school=load_calendars(root,config)
    reference=load_reference(root/'data/raw/activity_time_use_full.csv')
    print(f'Weather: {len(weather):,} physical hours. Generating family schedules...',flush=True)
    behaviour=simulate_behaviour(weather,public,school,reference,config,streams[1])
    print('Generating appliance events and hot-water draws...',flush=True)
    power,water,events=simulate_devices(behaviour,weather,config,streams[2])
    print('Solving building and water-tank heat balances...',flush=True)
    thermal=simulate_thermal(weather,behaviour,power,water,house,config)
    power.update({k:thermal.pop(k) for k in ['space_heating','water_heater']})
    count=len(weather)
    hourly=weather.copy()
    hourly.insert(0,'timestamp_local',weather.index.tz_convert('Europe/Warsaw').astype(str))
    hourly.index.name='timestamp_utc'
    for name,array in power.items():
        hourly[name+'_kwh']=array.reshape(count,60).sum(axis=1)/60
    energy_cols=[c for c in hourly if c.endswith('_kwh')]
    hourly['total_kwh']=hourly[energy_cols].sum(axis=1)
    hourly['peak_1min_kw']=sum(power.values()).reshape(count,60).max(axis=1)
    hourly['mean_kw']=hourly['total_kwh']
    for name,array in thermal.items():
        block=array.reshape(count,60)
        hourly[name]=block.sum(axis=1) if name in ['unmet_comfort_degree_minutes','hot_water_unmet_kwh','thermal_residual_kwh'] else block.mean(axis=1)
    hourly['indoor_min_c']=thermal['indoor_c'].reshape(count,60).min(axis=1)
    hourly['indoor_max_c']=thermal['indoor_c'].reshape(count,60).max(axis=1)
    hourly['tank_min_c']=thermal['tank_c'].reshape(count,60).min(axis=1)
    hourly['hot_water_mixed_l']=water.reshape(count,60).sum(axis=1)
    hourly['occupancy_mean']=behaviour['home'].sum(axis=0).reshape(count,60).mean(axis=1)
    hourly['awake_at_home_mean']=(behaviour['home'] & (behaviour['activity']!=CODE['sleep'])).sum(axis=0).reshape(count,60).mean(axis=1)
    dates=weather.index.tz_convert('Europe/Warsaw').strftime('%Y-%m-%d')
    calendar=behaviour['calendar'].set_index('date')
    for column in calendar.columns:
        hourly[column]=calendar[column].reindex(dates).to_numpy()
    person_frames=[];person_events=[]
    for i,person in enumerate(PEOPLE):
        arr=behaviour['activity'][i];loc=behaviour['home'][i]
        frame=pd.DataFrame({'timestamp_utc':weather.index.astype(str),'timestamp_local':hourly.timestamp_local.to_numpy(),'person':person})
        for code,name in enumerate(ACTIVITIES):
            frame[name+'_minutes']=(arr==code).reshape(count,60).sum(axis=1)
        frame['home_minutes']=loc.reshape(count,60).sum(axis=1)
        person_frames.append(frame)
        combined=arr.astype(np.int16)+loc.astype(np.int16)*100
        boundaries=np.r_[0,np.flatnonzero(np.diff(combined)!=0)+1,len(arr)]
        for start,end in zip(boundaries[:-1],boundaries[1:]):
            person_events.append((person,ACTIVITIES[arr[start]],bool(loc[start]),behaviour['index'][start].isoformat(),
                                  (behaviour['index'][end-1]+pd.Timedelta(minutes=1)).isoformat(),end-start))
    persons=pd.concat(person_frames,ignore_index=True)
    hourly.to_csv(out/'hourly.csv',float_format='%.6f')
    persons.to_csv(out/'residents_hourly.csv',index=False)
    pd.DataFrame(person_events,columns=['person','activity','at_home','start_utc','end_utc','minutes']).to_csv(out/'resident_events.csv',index=False)
    events.to_csv(out/'appliance_events.csv',index=False,float_format='%.6f')
    behaviour['proposals'].to_csv(out/'activity_proposals.csv',index=False,float_format='%.6f')
    behaviour['calendar'].to_csv(out/'calendar.csv',index=False)
    # Include all adult diary days, with zero-minute nonparticipants, in survey comparisons.
    persons['date']=persons.timestamp_local.str[:10]
    comparisons=[]
    for name,source in REFERENCES.items():
        for person in PEOPLE[:2]:
            daily=persons[persons.person==person].groupby('date')[name+'_minutes'].sum()
            positive=daily[daily>0];r=reference[source]
            comparisons.append({'person':person,'activity':name,'source_activity':source,
                                'reference_participation':r['p'],'realized_participation':float((daily>0).mean()),
                                'reference_all_minutes':r['all'],'realized_all_minutes':float(daily.mean()),
                                'reference_participant_minutes':r['mean'],'realized_participant_minutes':float(positive.mean()) if len(positive) else None})
    pd.DataFrame(comparisons).to_csv(out/'eurostat_comparison.csv',index=False,float_format='%.4f')
    totals=hourly[energy_cols].sum().to_dict()
    check_minutes=persons[[x+'_minutes' for x in ACTIVITIES]].sum(axis=1)
    assertions={
        'all_hourly_energy_finite_nonnegative':bool(np.isfinite(hourly[energy_cols]).all().all() and (hourly[energy_cols]>=0).all().all()),
        'person_minutes_sum_to_60':bool((check_minutes==60).all()),
        'total_equals_appliance_sum':bool(np.allclose(hourly.total_kwh,hourly[energy_cols].sum(axis=1),atol=1e-6)),
        'timestamps_unique_hourly_utc':bool(hourly.index.is_unique and (hourly.index.to_series().diff().dropna()==pd.Timedelta(hours=1)).all()),
        'weather_and_output_same_length':len(hourly)==len(weather),
        'space_heating_within_capacity':bool((hourly.space_heating_kwh<=house['heating_capacity_kw']+1e-5).all()),
        'no_heat_pump_or_generation_columns':not any('pv_' in c or 'cop_' in c for c in hourly),
        'all_temperatures_finite':bool(np.isfinite(hourly[['indoor_c','tank_c']]).all().all())}
    vacation_calendar = behaviour['calendar']
    vacation_workdays = vacation_calendar[vacation_calendar.family_vacation &
                                          (pd.to_datetime(vacation_calendar.date).dt.dayofweek < 5) &
                                          ~vacation_calendar.public_holiday]
    vacation_by_year = vacation_workdays.assign(year=pd.to_datetime(vacation_workdays.date).dt.year).groupby('year').size()
    assertions.update({
        'family_vacation_is_away':bool((hourly.loc[hourly.family_vacation,'occupancy_mean'] == 0).all()),
        'twenty_vacation_workdays_per_parent_per_year':bool((vacation_by_year == 20).all()),
    })
    if not all(assertions.values()):raise AssertionError(assertions)
    occupied = hourly.occupancy_mean > 0
    awake_home = hourly.awake_at_home_mean > 0
    report={'version':'3.1.0','seed':config['seed'],'weather':audit,'checks':assertions,
            'house':house,'device_totals_kwh':totals,'total_kwh':float(hourly.total_kwh.sum()),
            'indoor_min_c':float(hourly.indoor_min_c.min()),'indoor_max_c':float(hourly.indoor_max_c.max()),
            'occupied_indoor_min_c':float(hourly.loc[occupied,'indoor_min_c'].min()),
            'occupied_indoor_max_c':float(hourly.loc[occupied,'indoor_max_c'].max()),
            'awake_home_indoor_max_c':float(hourly.loc[awake_home,'indoor_max_c'].max()),
            'night_ventilation_hours':float(hourly.night_ventilation_active_fraction.sum()),
            'occupied_under_setpoint_degree_hours':float(hourly.unmet_comfort_degree_minutes.sum()/60),
            'hours_with_unmet_occupied_comfort':int((hourly.unmet_comfort_degree_minutes>0).sum()),
            'hot_water_unmet_kwh':float(hourly.hot_water_unmet_kwh.sum()),
            'proposed_activity_minutes':int(behaviour['proposals'].proposed_minutes.sum()),
            'rejected_activity_minutes':int((behaviour['proposals'].proposed_minutes-behaviour['proposals'].accepted_minutes).sum()),
            'family_vacation_calendar_days':int(vacation_calendar.family_vacation.sum()),
            'family_vacation_parental_workdays':int(len(vacation_workdays)),
            'family_vacation_blocks':vacation_calendar.loc[vacation_calendar.family_vacation,
                                                            ['vacation_block','date']].groupby('vacation_block').date.agg(['min','max']).reset_index().to_dict('records'),
            'source_sha256':hashes(list((root/'data/raw').iterdir())),
            'limitations':['Synthetic, uncalibrated household; passing checks does not validate realism.',
                           'Single thermal zone; no room-level temperatures or cooling system. Summer cooling is passive night ventilation only.',
                           'Outing travel uses aggregate adult trip durations; no routes or travel modes are modeled.',
                           'One TV/desktop/console; concurrent residents are treated as shared use.',
                           'School dates are taken from the supplied regional file; no school-specific closure days.',
                           'Annual leave is a configured 10+5+5 family-away schedule; illness and other long holidays are not modeled.',
                           'Hourly weather is held constant during each model hour; instantaneous radiation is a proxy.',
                           'Appliance events list triggered devices; continuously driven loads are in hourly.csv.']}
    for name,obj in [('resolved_house.json',house),('run_config.json',config),('validation.json',report)]:
        (out/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'Saved {count:,} hours to {out}. Total {report["total_kwh"]:,.0f} kWh.',flush=True)
    return out
