"""One-zone RC heat balance and well-mixed electric domestic-hot-water tank."""
import math
import numpy as np
from .behaviour import CODE

def rc_step(temp, outdoor, gains_kw, h_kw_k, c_kwh_k, dt_h=1/60):
    decay=math.exp(-h_kw_k*dt_h/c_kwh_k)
    equilibrium=outdoor+gains_kw/h_kw_k
    return equilibrium+(temp-equilibrium)*decay

def simulate_thermal(weather, behaviour, base_power, water_l, house, config):
    n=len(water_l);a=behaviour['activity'];home=behaviour['home']
    awake=(home & (a!=CODE['sleep'])).sum(axis=0)
    sleeping=(home & (a==CODE['sleep'])).sum(axis=0)
    h=house;c_house=h['floor_area_m2']*h['thermal_capacity_wh_m2k']/1000
    volume=h['floor_area_m2']*h['height_m'];c_tank=h['tank_volume_l']*0.001163
    t=h['initial_indoor_c'];tank=h['initial_tank_c'];heat_on=False;boiler_on=False
    nonthermal=sum(base_power.values()).astype(float)
    outdoor=weather.temperature_2m.to_numpy();wind=weather.wind_ms.to_numpy()
    radiation=weather.shortwave_radiation_instant.to_numpy()
    local=weather.index.tz_convert('Europe/Warsaw')
    day=np.asarray(local.dayofyear)
    mains=10+5*np.sin(2*np.pi*(day-120)/365.25)
    shade=np.where(np.isin(local.month,[5,6,7,8,9]),0.35,1.0)
    result={k:np.zeros(n,dtype=np.float32) for k in ['space_heating','water_heater','indoor_c','tank_c','setpoint_c',
            'unmet_comfort_degree_minutes','hot_water_unmet_kwh','heat_loss_kw','solar_gain_kw','internal_gain_kw','thermal_residual_kwh']}
    ts=config['thermal'];dt=1/60
    warmup=min(n,int(ts['warmup_days']*1440))
    # First segment repeated only to condition storage; its energy is never exported twice.
    for iteration in range(warmup+n):
        k=iteration if iteration<warmup else iteration-warmup
        w=k//60
        setpoint=h['occupied_setpoint_c'] if awake[k]>0 else (h['sleep_setpoint_c'] if sleeping[k]>0 else h['away_setpoint_c'])
        half=h['thermostat_deadband_c']/2
        if t<setpoint-half:heat_on=True
        elif t>setpoint+half:heat_on=False
        heat=h['heating_capacity_kw'] if heat_on else 0.
        # Mixed-water demand extracts heat from the tank through a mixing valve.
        required=max(0,h['water_use_temperature_c']-mains[w])
        before_tank=tank
        demand=water_l[k]*0.001163*required
        above=max(0,(tank-h['water_use_temperature_c'])*c_tank)
        if demand<=above:
            tank-=demand/c_tank
        else:
            remaining=max(0,water_l[k]-above/max(0.001163*required,1e-9))
            tank=min(tank,h['water_use_temperature_c'])
            tank=mains[w]+(tank-mains[w])*math.exp(-remaining/h['tank_volume_l'])
        extracted=max(0,(before_tank-tank)*c_tank)
        unmet=max(0,water_l[k]*0.001163*required-extracted)
        if tank<h['tank_setpoint_c']-h['tank_deadband_c']:boiler_on=True
        elif tank>=h['tank_setpoint_c']:boiler_on=False
        boiler=h['boiler_power_kw'] if boiler_on else 0.
        tank_ua=h['tank_loss_w_k']/1000
        old_tank=tank
        tank=rc_step(tank,t,boiler,tank_ua,c_tank)
        tank_gain=boiler-(tank-old_tank)*c_tank/dt
        ach=h['air_changes_per_hour']+h['wind_ach_per_ms']*wind[w]
        if awake[k]>0 and t>h['window_open_above_c'] and outdoor[w]<t:
            ach+=h['window_open_ach']
        conductance=(h['floor_area_m2']*h['fabric_loss_w_m2k']+0.33*volume*ach)/1000
        solar=h['effective_solar_area_m2']*radiation[w]*shade[w]/1000
        internal=(awake[k]*ts['person_awake_w']+sleeping[k]*ts['person_sleep_w'])/1000
        internal+=nonthermal[k]*ts['internal_electric_gain_fraction']+tank_gain
        total_gain=heat*h['heating_efficiency']+solar+internal
        previous=t;t=rc_step(t,outdoor[w],total_gain,conductance,c_house)
        # Exact step-integrated loss follows from the analytic RC solution.
        change=c_house*(t-previous)
        loss_energy=total_gain*dt-change
        if iteration>=warmup:
            result['space_heating'][k]=heat;result['water_heater'][k]=boiler
            result['indoor_c'][k]=t;result['tank_c'][k]=tank;result['setpoint_c'][k]=setpoint
            result['unmet_comfort_degree_minutes'][k]=max(0,setpoint-half-t) if awake[k]>0 else 0
            result['hot_water_unmet_kwh'][k]=unmet
            result['heat_loss_kw'][k]=loss_energy/dt;result['solar_gain_kw'][k]=solar;result['internal_gain_kw'][k]=internal
            result['thermal_residual_kwh'][k]=change-(total_gain*dt-loss_energy)
    return result
