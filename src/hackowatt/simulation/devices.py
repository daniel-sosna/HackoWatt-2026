"""Appliance powers in kW; human time and appliance cycle time are distinct."""
import numpy as np
import pandas as pd
from .behaviour import CODE, PEOPLE

def runs(mask):
    edges=np.diff(np.r_[False,mask,False].astype(np.int8))
    return zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1))

def cycle_profile(minutes, kwh):
    # Heating, wash/circulation and rinse phases; exact requested integrated energy.
    weights=np.ones(minutes,dtype=float)*0.15
    weights[:max(1,minutes//5)]=1.0
    weights[minutes*2//3:minutes*3//4]=0.65
    return weights*(kwh*60/weights.sum())

def simulate_devices(behaviour, weather, config, rng):
    idx=behaviour['index']; a=behaviour['activity']; home=behaviour['home']; n=len(idx)
    d=config['devices']; awake=home & (a!=CODE['sleep'])
    names=['fridge','router','standby','lighting','tv','console','desktop','laptop',
           'kettle','coffee_machine','hob','oven','microwave','washing_machine','dishwasher','vacuum','charging']
    power={name:np.zeros(n,dtype=np.float32) for name in names}
    events=[]
    def event(name,start,values,person='household',reason='activity'):
        stop=min(n,start+len(values))
        if stop<=start:return
        power[name][start:stop]+=np.asarray(values[:stop-start],dtype=np.float32)
        events.append({'device':name,'person':person,'start_utc':idx[start].isoformat(),
                       'end_utc':(idx[stop-1]+pd.Timedelta(minutes=1)).isoformat(),
                       'duration_minutes':stop-start,'energy_kwh':float(np.sum(values[:stop-start])/60),
                       'trigger':reason})
    # A cyclic compressor is normalized to the organiser's daily fridge energy.
    phase=np.arange(n)%60
    power['fridge'][phase<20]=d['fridge_daily_kwh']/8
    power['router'][:]=d['router_kw']; power['standby'][:]=d['standby_kw']
    rad=np.repeat(weather.shortwave_radiation_instant.to_numpy(),60)
    dark=False
    for k in range(0,n,60):
        if rad[k]<70:dark=True
        elif rad[k]>100:dark=False
        if dark:
            power['lighting'][k:k+60]=d['lighting_max_kw']*np.minimum(1,awake[:,k:k+60].sum(axis=0)/3)
    gaming=((a==CODE['gaming'])&home).any(axis=0)
    television=((a==CODE['tv'])&home).any(axis=0) | gaming
    power['tv'][television]=d['tv_kw'];power['console'][gaming]=d['console_kw']
    power['desktop'][((a==CODE['computing'])&home).any(axis=0)]=d['desktop_kw']
    power['laptop'][(a[1]==CODE['work'])&home[1]]=d['laptop_kw']
    # Shared desktop/console use is modeled as co-use, one powered device per household.
    for name in ['tv','console','desktop','laptop']:
        for s,e in runs(power[name]>0):
            events.append({'device':name,'person':'household','start_utc':idx[s].isoformat(),
                           'end_utc':(idx[e-1]+pd.Timedelta(minutes=1)).isoformat(),
                           'duration_minutes':e-s,'energy_kwh':float(power[name][s:e].sum()/60),'trigger':'scheduled_screen_or_work'})
    local=idx.tz_convert('Europe/Warsaw'); dates=np.asarray(local.strftime('%Y-%m-%d')); hours=np.asarray(local.hour)
    water=np.zeros(n,dtype=np.float32)
    day_names,first=np.unique(dates,return_index=True)
    for day,begin,end in zip(day_names,first,np.r_[first[1:],n]):
        ii=np.arange(begin,end)
        # Breakfast drinks: a household opportunity, not four coincident kettle loads.
        candidates=ii[((a[:,ii]==CODE['eating'])&home[:,ii]).any(axis=0)&(hours[ii]<11)]
        if len(candidates):
            s=int(candidates[0])
            if rng.random()<0.8:event('kettle',s,np.full(int(rng.integers(3,6)),d['kettle_kw']),reason='breakfast')
            if rng.random()<0.5:event('coffee_machine',s,np.full(int(rng.integers(5,11)),d['coffee_kw']),reason='breakfast')
        cooking=ii[((a[:,ii]==CODE['cooking'])&home[:,ii]).any(axis=0)]
        # At most three home cooking sessions per day, using actual preparation windows.
        for low,high in [(5,11),(11,16),(16,24)]:
            positions=cooking[(hours[cooking]>=low)&(hours[cooking]<high)]
            if not len(positions):continue
            mode=str(rng.choice(['cold','hob','oven','microwave'],p=np.asarray(d['cooking_mode_weights'])/sum(d['cooking_mode_weights'])))
            if mode=='cold':continue
            mask=np.zeros(len(ii),dtype=bool);mask[positions-begin]=True
            s,e=max(runs(mask),key=lambda pair:pair[1]-pair[0]);s+=begin;e+=begin
            target={'hob':int(rng.integers(15,36)),'oven':int(rng.integers(25,51)),'microwave':int(rng.integers(3,11))}[mode]
            length=min(target,e-s)
            event(mode,s,np.full(length,d[mode+'_kw']),reason='home_food_preparation')
        for name,code,probability in [('washing_machine','laundry',1.0),('dishwasher','dish_washing',config['behaviour']['dishwasher_probability'])]:
            care=((a[:2,ii]==CODE[code])&home[:2,ii]).any(axis=0)
            positions=ii[care]
            if len(positions)<10 or rng.random()>=probability:continue
            # One or two laundry loads, at most one dishwashing programme per day.
            loads=int(rng.integers(1,3)) if name=='washing_machine' else 1
            loads=min(loads,len(positions)//10)
            next_free=0
            for _ in range(loads):
                options=positions[positions>=next_free]
                if not len(options):break
                s=int(options[0]); duration=d[name+'_minutes']
                if s+duration>n:continue  # no invented post-coverage cycle energy
                if np.any(power[name][s:s+duration]>0):continue
                kwh=float(rng.uniform(*d[name+'_cycle_kwh']))
                event(name,s,cycle_profile(duration,kwh),reason=code)
                next_free=s+duration
                positions=options[10:]
        cleaning=ii[((a[:2,ii]==CODE['cleaning'])&home[:2,ii]).any(axis=0)]
        count=int(len(cleaning)*config['behaviour']['vacuum_fraction_cleaning'])
        power['vacuum'][cleaning[:count]]=d['vacuum_kw']
        for person in range(4):
            personal=ii[(a[person,ii]==CODE['personal_care'])&home[person,ii]]
            if len(personal) and rng.random()<config['behaviour']['shower_probability']:
                length=min(len(personal),int(round(rng.triangular(4,7,10))))
                # Shower occupies an existing contiguous personal-care block when possible.
                mask=np.zeros(len(ii),dtype=bool);mask[np.isin(ii,personal)]=True
                s,e=max(runs(mask),key=lambda x:x[1]-x[0]);length=min(length,e-s)
                water[ii[s:s+length]]+=config['behaviour']['shower_flow_l_min']
            # A small washbasin allowance inside personal care, separate from shower demand.
            if len(personal):water[personal[:min(3,len(personal))]]+=1.0
            evening=ii[home[person,ii] & (hours[ii]>=19)]
            if len(evening):
                s=int(evening[0]); kwh=float(rng.uniform(*d['charging_kwh_per_device']))
                event('charging',s,np.full(min(120,n-s),kwh/2),PEOPLE[person],'daily_portable_device')
        dish=ii[((a[:2,ii]==CODE['dish_washing'])&home[:2,ii]).any(axis=0)]
        if len(dish):water[dish[:min(10,len(dish))]]+=0.6
    return power,water,pd.DataFrame(events)
