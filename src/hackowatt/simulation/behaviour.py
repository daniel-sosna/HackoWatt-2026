"""Minute schedules with exclusive primary activities and separate location."""
from datetime import timedelta
import numpy as np
import pandas as pd

PEOPLE = ['Marek', 'Ania', 'Kuba', 'Zosia']
ACTIVITIES = ['free', 'sleep', 'work', 'school', 'commute', 'eating', 'personal_care',
              'cooking', 'dish_washing', 'laundry', 'cleaning', 'tv', 'computing',
              'gaming', 'shopping', 'walking', 'visiting', 'child_help', 'homework']
CODE = {name: i for i, name in enumerate(ACTIVITIES)}
REFERENCES = {
    'sleep': 'Sleep', 'eating': 'Eating', 'personal_care': 'Other and/or unspecified personal care',
    'cooking': 'Food management except dish washing', 'dish_washing': 'Dish washing',
    'laundry': 'Laundry', 'cleaning': 'Cleaning dwelling', 'tv': 'Television and video',
    'computing': 'Computing', 'gaming': 'Computer games', 'shopping': 'Shopping and services',
    'walking': 'Walking and hiking', 'visiting': 'Visiting and feasts',
    'child_help': 'Teaching, reading and talking with child'}

def draw_duration(rng, mean, settings):
    cv = settings['duration_cv']
    if settings['duration_distribution'] == 'gamma':
        return max(1, int(round(rng.gamma(1/cv**2, mean*cv**2))))
    half = mean*cv*np.sqrt(3)
    return max(1, int(round(rng.uniform(mean-half, mean+half))))

def calibrate_probabilities(base, delta):
    lo, hi = -2., 2.
    for _ in range(60):
        mid = (lo+hi)/2
        if np.clip(base+delta+mid, 0, 1).mean() < base:
            lo = mid
        else:
            hi = mid
    return np.clip(base+delta+(lo+hi)/2, 0, 1)


def schedule_family_vacations(day_labels, public, settings, rng):
    """Return all-away calendar dates and reproducible named leave blocks.

    A leave block consumes the stated number of Monday-Friday, non-public work
    days for both parents. Weekends between those days are part of the trip but
    do not consume leave. Starts are sampled from the configured seasonal
    windows, so the fixed 10+5+5 allocation remains reproducible from the seed.
    """
    dates = pd.DatetimeIndex(pd.to_datetime(day_labels))
    available_years = sorted(set(dates.year))
    vacation = {}
    for year in available_years:
        for block in settings['vacation_blocks']:
            lower = pd.Timestamp(f'{year}-{block["start"]}')
            upper = pd.Timestamp(f'{year}-{block["end"]}')
            candidates = []
            for start in pd.date_range(lower, upper, freq='W-MON'):
                workdays = [d for d in pd.date_range(start, upper, freq='D')
                            if d.weekday() < 5 and d.strftime('%Y-%m-%d') not in public]
                if len(workdays) >= int(block['workdays']):
                    candidates.append((start, workdays[:int(block['workdays'])]))
            if not candidates:
                # The two buffer years around the supplied weather range do not
                # contain a complete seasonal window and intentionally get none.
                continue
            start, leave_days = candidates[int(rng.integers(len(candidates)))]
            name = f'{block["name"]}_{year}'
            for date in pd.date_range(start, leave_days[-1], freq='D'):
                vacation[date.strftime('%Y-%m-%d')] = name
    return vacation

def simulate_behaviour(weather, public, school_break, reference, config, rng):
    start = weather.index[0] - pd.Timedelta(days=2)
    stop = weather.index[-1] + pd.Timedelta(hours=1, days=2)
    index = pd.date_range(start, stop, freq='min', inclusive='left')
    local = index.tz_convert('Europe/Warsaw')
    labels = np.asarray(local.strftime('%Y-%m-%d'))
    day_labels, first = np.unique(labels, return_index=True)
    day_slices = {d: np.arange(a,b) for d,a,b in zip(day_labels,first,np.r_[first[1:],len(index)])}
    minute = np.asarray(local.hour*60+local.minute)
    activity = np.zeros((4,len(index)), dtype=np.uint8)
    home = np.ones_like(activity, dtype=bool)
    settings = config['behaviour']
    proposals = []
    calendars = []
    shifts = {}
    wfh = {}
    anchor = pd.Timestamp(settings['shift_anchor_monday'])
    vacations = schedule_family_vacations(day_labels, public, settings, rng)
    for d in day_labels:
        date = pd.Timestamp(d)
        week = (date - pd.Timedelta(days=date.weekday())).strftime('%Y-%m-%d')
        if week not in wfh:
            candidates = [x.strftime('%Y-%m-%d') for x in pd.date_range(week, periods=5)
                          if x.strftime('%Y-%m-%d') not in public and x.strftime('%Y-%m-%d') not in vacations]
            k = min(int(rng.choice(settings['wfh_days_choices'])),len(candidates))
            wfh[week] = set(rng.choice(candidates,k,replace=False))
        shift = settings['shift_cycle'][((date-anchor).days//7) % len(settings['shift_cycle'])]
        if d in vacations or date.weekday() >= 5 or (d in public and rng.random() >= settings['holiday_shift_probability']):
            shift = 'off'
        shifts[d] = shift
        calendars.append({'date':d,'public_holiday':d in public,'school_break':d in school_break,
                          'family_vacation':d in vacations, 'vacation_block':vacations.get(d),
                          'school_day':date.weekday()<5 and d not in public and d not in school_break and d not in vacations,
                          'ania_wfh':d in wfh[week] and d not in vacations, 'marek_shift':shift})
    cal = {x['date']:x for x in calendars}

    def idx(d, minutes):
        stamp = pd.Timestamp(d) + pd.Timedelta(minutes=float(minutes))
        stamp = stamp.tz_localize('Europe/Warsaw', ambiguous=False, nonexistent='shift_forward').tz_convert('UTC')
        return int((stamp-start).total_seconds()//60)

    def reserve(person, a, b, code, at_home=True, free_only=False):
        inds = np.arange(max(0,a),min(len(index),b))
        if free_only:
            inds = inds[activity[person,inds] == CODE['free']]
        activity[person,inds] = CODE[code]
        home[person,inds] = at_home

    # Hard work/school constraints first, including overnight shift tails.
    for d in day_labels:
        c = cal[d]
        if c['marek_shift'] != 'off':
            hour = {'morning':6,'evening':14,'night':22}[c['marek_shift']]
            a,b = idx(d,hour*60),idx(d,(hour+8)*60)
            trip = int(round(rng.uniform(45,73)))
            reserve(0,a-trip//2,a,'commute',False)
            reserve(0,a,b,'work',False)
            reserve(0,b,b+trip-trip//2,'commute',False)
            reserve(0,a+4*60,a+4*60+30,'eating',False)
        date = pd.Timestamp(d)
        if date.weekday()<5 and d not in public and not c['family_vacation']:
            a,b = idx(d,480),idx(d,960)
            reserve(1,a,b,'work',c['ania_wfh'])
            reserve(1,idx(d,750),idx(d,780),'eating',c['ania_wfh'])
            if c['ania_wfh']:
                reserve(1,idx(d,600),idx(d,610),'free')
                reserve(1,idx(d,900),idx(d,910),'free')
            else:
                trip = int(round(rng.uniform(45,73)))
                reserve(1,a-trip//2,a,'commute',False)
                reserve(1,b,b+trip-trip//2,'commute',False)
        if c['school_day']:
            for person in [2,3]:
                a,b = idx(d,480),idx(d,int(rng.integers(810,901)))
                trip = int(rng.integers(10,31))
                reserve(person,a-trip,a,'commute',False)
                reserve(person,a,b,'school',False)
                reserve(person,b,b+trip,'commute',False)
                reserve(person,idx(d,720),idx(d,750),'eating',False)

    # Sleep has lower priority than fixed work, but cannot be overwritten by optional events.
    for d in day_labels:
        previous = (pd.Timestamp(d)-pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        for person in range(4):
            mean = reference['Sleep']['mean'] if person<2 else settings['child_sleep_minutes']
            length = int(round(rng.triangular(mean-30,mean,mean+30)))
            if person==0 and shifts.get(previous)=='night':
                a=idx(d,420)
                reserve(person,a,a+length,'sleep',free_only=True)
            else:
                wake = 285 if person==0 and shifts[d]=='morning' else (405 if person<2 else 420)
                if not cal[d]['school_day'] and shifts[d]=='off':
                    wake = 480
                if person==0 and shifts.get(previous)=='evening':
                    wake = 525
                b=idx(d,wake)
                reserve(person,b-length,b,'sleep',free_only=True)

    local_weather = weather.copy()
    local_weather['date'] = weather.index.tz_convert('Europe/Warsaw').strftime('%Y-%m-%d')
    daily = local_weather.groupby('date').agg(temperature=('temperature_2m','mean'),
                                             rain=('precipitation','sum'), wind=('wind_ms','mean'), snow=('snowfall','sum'))
    delta=[]
    for d in day_labels:
        x=daily.loc[d] if d in daily.index else daily.iloc[0 if d<daily.index[0] else -1]
        delta.append((settings['walking_free_day_adjustment'] if pd.Timestamp(d).weekday()>=5 or d in public else 0)
                     +(settings['walking_rain_adjustment'] if x.rain>1 else 0)
                     +(settings['walking_cold_adjustment'] if x.temperature<0 else 0)
                     +(settings['walking_wind_adjustment'] if x.wind>10 else 0)
                     +(settings['walking_snow_adjustment'] if x.snow>0 and x.rain<=1 else 0))
    walking_p=calibrate_probabilities(reference[REFERENCES['walking']]['p'],np.asarray(delta))

    def allocate(person, d, name, duration, windows, min_chunk=5, allow_split=True):
        inds=day_slices[d]
        allowed=np.zeros(len(inds),dtype=bool)
        for a,b in windows:
            allowed |= (minute[inds]>=a)&(minute[inds]<b)
        mask=allowed & (activity[person,inds]==CODE['free']) & home[person,inds]
        if mask.sum()<duration:
            return np.array([],dtype=int)
        # Randomized contiguous free runs; accepted allocations preserve the full daily budget.
        positions=np.flatnonzero(mask)
        groups=np.split(positions,np.where(np.diff(positions)>1)[0]+1)
        groups=[g for g in groups if len(g)>=min_chunk]
        rng.shuffle(groups)
        chosen=[]; remaining=duration
        for g in groups:
            if not allow_split and len(g)<remaining:
                continue
            take=min(remaining,len(g))
            offset=int(rng.integers(0,len(g)-take+1))
            chosen.extend(inds[g[offset:offset+take]])
            remaining-=take
            if remaining==0:break
        if remaining:return np.array([],dtype=int)
        selected=np.sort(np.asarray(chosen,dtype=int))
        activity[person,selected]=CODE[name]
        return selected

    optional=[('cooking',[(360,540),(660,840),(960,1230)],True),
              ('dish_washing',[(420,600),(780,900),(1080,1350)],True),
              ('laundry',[(480,1260)],True),('cleaning',[(480,1200)],True),
              ('shopping',[(540,1200)],False),('walking',[(540,1200)],False),
              ('visiting',[(720,1320)],False),('child_help',[(900,1230)],True),
              ('tv',[(480,1410)],True),('computing',[(480,1410)],True),('gaming',[(480,1410)],True)]
    for di,d in enumerate(day_labels):
        inds=day_slices[d]
        if cal[d]['family_vacation']:
            continue
        for person in range(4):
            # Existing off-site lunch is part of the daily eating budget.
            already=int((activity[person,inds]==CODE['eating']).sum())
            total=int(round(rng.triangular(78,93,108)))
            remain=max(0,total-already)
            for portion,window in [(min(23,remain),[(270,660)]),(max(0,remain-min(23,remain)),[(720,1410)])]:
                if portion: allocate(person,d,'eating',portion,window,min_chunk=1)
            personal=int(round(rng.triangular(41,56,71))) if person<2 else int(rng.integers(35,56))
            allocate(person,d,'personal_care',personal,[(270,660),(1020,1440)],min_chunk=5)
        # Child homework/screen proposals are separate from adult time-use evidence.
        for person in [2,3]:
            length=int(rng.integers(45,76)) if cal[d]['school_day'] else int(rng.integers(0,46))
            if length:allocate(person,d,'homework',length,[(840,1200)])
            prob=settings['child_screen_school_probability'] if cal[d]['school_day'] else settings['child_screen_free_probability']
            if rng.random()<prob:
                duration=int(rng.integers(45,91)) if cal[d]['school_day'] else int(rng.integers(60,121))
                allocate(person,d,str(rng.choice(['tv','computing','gaming'])),duration,[(900,1260)])
        order=[0,1];rng.shuffle(order)
        for name,windows,split in optional:
            for person in order:
                r=reference[REFERENCES[name]]
                probability=walking_p[di] if name=='walking' else r['p']
                proposed=rng.random()<probability
                duration=draw_duration(rng,r['mean'],settings) if proposed else 0
                away=name in ('shopping','walking') or (name=='visiting' and rng.random()<0.5)
                travel=0
                if away and name!='walking' and duration:
                    travel_source='Travel related to shopping and services' if name=='shopping' else 'Travel related to leisure, social and associative life'
                    travel=draw_duration(rng,reference[travel_source]['mean'],settings)
                # Reserve the complete outing including both journeys in one feasible free run.
                selected=allocate(person,d,name,duration+travel,windows,allow_split=split) if duration else np.array([],dtype=int)
                if travel and len(selected):
                    before=travel//2;after=travel-before
                    journey=np.r_[selected[:before],selected[-after:]]
                    activity[person,journey]=CODE['commute'];home[person,journey]=False
                    selected=selected[before:len(selected)-after]
                if name=='child_help' and len(selected):
                    # Match help to a child at home and awake; unmatched time returns to free.
                    okay=(home[2:,selected] & (activity[2:,selected]!=CODE['sleep'])).any(axis=0)
                    activity[person,selected[~okay]]=CODE['free']
                    selected=selected[okay]
                if away and len(selected):
                    home[person,selected]=False
                proposals.append({'date':d,'person':PEOPLE[person],'activity':name,'p_used':probability,
                                  'proposed_minutes':duration,'accepted_minutes':len(selected),
                                  'reason':'accepted' if len(selected)==duration else 'insufficient_free_time_or_partner'})
    # The whole family is away for every calendar day inside a selected trip.
    # Sleep/free activity is retained as a diary state, while no home activity
    # can trigger domestic appliances or domestic hot-water draws.
    for d in day_labels:
        if cal[d]['family_vacation']:
            home[:, day_slices[d]] = False
    keep=(index>=weather.index[0])&(index<weather.index[-1]+pd.Timedelta(hours=1))
    out_index=index[keep]
    full_dates=set(out_index.tz_convert('Europe/Warsaw').strftime('%Y-%m-%d'))
    return {'index':out_index,'activity':activity[:,keep],'home':home[:,keep],
            'proposals':pd.DataFrame([p for p in proposals if p['date'] in full_dates]),
            'calendar':pd.DataFrame([c for c in calendars if c['date'] in full_dates])}
