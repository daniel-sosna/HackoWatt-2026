"""Strict input validation, auditable civil-time normalization and parameters."""
import hashlib
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd

WEATHER_COLUMNS = ['temperature_2m', 'cloud_cover', 'relative_humidity_2m',
                   'wind_speed_10m', 'precipitation', 'snowfall', 'shortwave_radiation_instant']

def load_config(path):
    c = json.loads(Path(path).read_text(encoding='utf-8'))
    if c['weather']['wind_unit'] not in ('km/h', 'm/s'):
        raise ValueError('wind_unit must be km/h or m/s')
    if c['behaviour']['duration_distribution'] not in ('gamma', 'uniform'):
        raise ValueError('duration_distribution must be gamma or uniform')
    if not 0 < c['behaviour']['duration_cv'] <= 0.55:
        raise ValueError('duration_cv must be in (0, .55]')
    for key in ['holiday_shift_probability', 'shower_probability', 'dishwasher_probability',
                'child_screen_school_probability', 'child_screen_free_probability']:
        if not 0 <= c['behaviour'][key] <= 1:
            raise ValueError(f'{key} must be between 0 and 1')
    blocks = c['behaviour'].get('vacation_blocks', [])
    if sum(int(block.get('workdays', 0)) for block in blocks) != 20:
        raise ValueError('vacation_blocks must contain exactly 20 parental workdays')
    for block in blocks:
        if not block.get('name') or int(block['workdays']) <= 0:
            raise ValueError('Each vacation block needs a name and positive workdays')
        for key in ['start', 'end']:
            if not re.fullmatch(r'\d{2}-\d{2}', str(block.get(key, ''))):
                raise ValueError(f'Vacation block {key} must use MM-DD')
    ventilation = c['thermal'].get('night_ventilation', {})
    if not isinstance(ventilation.get('enabled'), bool):
        raise ValueError('night_ventilation.enabled must be boolean')
    if not all(1 <= int(month) <= 12 for month in ventilation['months']):
        raise ValueError('night_ventilation.months must be calendar months')
    if not (0 <= int(ventilation['start_hour']) <= 23 and 0 <= int(ventilation['end_hour']) <= 23):
        raise ValueError('night_ventilation hours must be in 0..23')
    if ventilation['additional_ach'] < 0 or ventilation['minimum_outdoor_delta_c'] < 0:
        raise ValueError('night_ventilation values must be nonnegative')
    return c

def resolve_house(config, rng):
    spec = config['house']
    if spec['mode'] not in ('sample', 'manual'):
        raise ValueError('house.mode must be sample or manual')
    unknown = set(spec['overrides']) - set(spec['parameters'])
    if unknown:
        raise ValueError(f'Unknown house overrides: {unknown}')
    result = {}
    for key, value in spec['parameters'].items():
        if key in spec['overrides']:
            value = spec['overrides'][key]
        if isinstance(value, dict):
            if spec['mode'] == 'manual':
                raise ValueError(f'Manual mode requires a numeric value/override for {key}')
            if value['distribution'] == 'triangular':
                value = rng.triangular(value['low'], value['mode'], value['high'])
            elif value['distribution'] == 'uniform':
                value = rng.uniform(value['low'], value['high'])
            else:
                raise ValueError(f'Unknown house distribution for {key}')
        result[key] = float(value)
        if not np.isfinite(result[key]) or result[key] <= 0:
            raise ValueError(f'House parameter {key} must be positive and finite')
    if not 0 < result['heating_efficiency'] <= 1:
        raise ValueError('Direct electric heating efficiency must be in (0,1]')
    if not (result['away_setpoint_c'] <= result['sleep_setpoint_c'] <= result['occupied_setpoint_c']):
        raise ValueError('Expected away <= sleep <= occupied setpoint')
    if result['tank_setpoint_c'] <= result['water_use_temperature_c']:
        raise ValueError('Tank setpoint must exceed use temperature')
    return result

def load_weather(path, config):
    raw = pd.read_csv(path)
    if not set(['time'] + WEATHER_COLUMNS) <= set(raw.columns):
        raise ValueError('Missing required weather columns')
    labels = pd.DatetimeIndex(pd.to_datetime(raw['time'], errors='raise'))
    if labels.tz is not None or labels.has_duplicates or not labels.is_monotonic_increasing:
        raise ValueError('Expected sorted unique naive source timestamps')
    if not (labels == labels.floor('h')).all():
        raise ValueError('Weather must be aligned to hourly boundaries')
    vals = raw[WEATHER_COLUMNS].apply(pd.to_numeric, errors='raise')
    if not np.isfinite(vals.to_numpy()).all():
        raise ValueError('Missing/nonfinite weather values; no silent interpolation')
    for name in ['cloud_cover', 'relative_humidity_2m']:
        if not vals[name].between(0, 100).all():
            raise ValueError(f'Invalid {name}')
    if (vals[['wind_speed_10m','precipitation','snowfall','shortwave_radiation_instant']] < 0).any().any():
        raise ValueError('Negative nonnegative weather variable')
    mode = config['weather']['time_mode']
    if mode not in ('Europe/Warsaw', 'UTC'):
        raise ValueError('time_mode must be Europe/Warsaw or UTC')
    start = labels[0].tz_localize(mode)
    end = (labels[-1] + pd.Timedelta(hours=1)).tz_localize(mode)
    utc = pd.date_range(start.tz_convert('UTC'), end.tz_convert('UTC'), freq='h', inclusive='left')
    wanted = utc.tz_convert(mode).tz_localize(None)
    missing = wanted.difference(labels)
    if len(missing):
        raise ValueError(f'Missing weather hours, e.g. {missing[:5].tolist()}')
    dropped = labels.difference(wanted)
    if len(dropped):
        nonexistent = labels[labels.tz_localize(mode, ambiguous=True, nonexistent='NaT').isna()]
        if len(dropped.difference(nonexistent)):
            raise ValueError('Unexpected excluded source rows')
    frame = vals.set_axis(labels).reindex(wanted).set_axis(utc)
    frame['wind_ms'] = frame.wind_speed_10m / (3.6 if config['weather']['wind_unit'] == 'km/h' else 1)
    audit = {'source_rows': len(raw), 'output_hours': len(frame), 'time_mode': mode,
             'dropped_nonexistent_local_hours': dropped.astype(str).tolist(),
             'reused_ambiguous_local_hours': wanted[wanted.duplicated()].astype(str).tolist(),
             'start_utc': str(utc[0]), 'last_utc': str(utc[-1]), 'wind_unit': config['weather']['wind_unit']}
    return frame, audit

def load_calendars(root, config):
    raw = root / 'data/raw'
    public = set(re.findall(r'^\d{4}-\d{2}-\d{2}', (raw/'poland_public_holidays_2024_2025.txt').read_text(), re.M))
    school = set()
    for a, b in re.findall(r'(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})', (raw/'poland_school_holidays_2024_2025.txt').read_text()):
        school.update(pd.date_range(a, b).strftime('%Y-%m-%d'))
    correction = json.loads((root/'data/calendar_corrections.json').read_text())
    if config['calendar']['apply_corrections']:
        public.update(correction['add_public_holidays'])
    return public, school

def load_reference(path):
    rows = pd.read_csv(path)
    def minutes(s):
        h, m = map(int, s.split(':'))
        return h*60+m
    return {r.Activity: {'p': float(r.Participation_rate_pct)/100,
                        'mean': minutes(r.Participation_time_only_participants),
                        'all': minutes(r.Time_spent_all)} for r in rows.itertuples()}

def hashes(paths):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
