"""Transparent renewable-energy calculations for the household dashboard.

The module deliberately separates physical energy flows from economic
assumptions.  Historical weather supplies the hourly solar shape; the user
controls the annual specific yield because the real roof and modules are not
known.  All timestamps remain on the canonical UTC timeline while tariffs and
habit summaries use Europe/Warsaw local time.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
import pandas as pd

from .devices import cycle_profile


DEVICE_CATEGORY = {
    'washing_machine': 'washing_machine',
    'dishwasher': 'dishwasher',
    'hob': 'cooking', 'oven': 'cooking', 'microwave': 'cooking',
    'kettle': 'cooking', 'coffee_machine': 'cooking',
    'tv': 'tv', 'console': 'tv',
    'desktop': 'computer', 'laptop': 'computer',
}

DEVICE_SETTINGS = {
    'washing_machine': {'maximum_shift_hours': 6, 'enabled': True,
                        'requires_occupancy': False, 'automation': 'automatic'},
    'dishwasher': {'maximum_shift_hours': 6, 'enabled': True,
                   'requires_occupancy': False, 'automation': 'automatic'},
    'cooking': {'maximum_shift_hours': 1, 'enabled': False,
                'requires_occupancy': True, 'automation': 'ask-first'},
    'tv': {'maximum_shift_hours': 2, 'enabled': False,
           'requires_occupancy': True, 'automation': 'ask-first'},
    'computer': {'maximum_shift_hours': 2, 'enabled': False,
                 'requires_occupancy': True, 'automation': 'ask-first'},
    'space_heating': {'maximum_shift_hours': 2, 'enabled': False,
                      'requires_occupancy': False, 'automation': 'model-required'},
    'water_heater': {'maximum_shift_hours': 4, 'enabled': False,
                     'requires_occupancy': False, 'automation': 'model-required'},
}

CATEGORY_COLUMNS = {
    'washing_machine': ['washing_machine_kwh'],
    'dishwasher': ['dishwasher_kwh'],
    'cooking': ['hob_kwh', 'oven_kwh', 'microwave_kwh', 'kettle_kwh', 'coffee_machine_kwh'],
    'tv': ['tv_kwh', 'console_kwh'],
    'computer': ['desktop_kwh', 'laptop_kwh'],
    'space_heating': ['space_heating_kwh'],
    'water_heater': ['water_heater_kwh'],
    'lighting': ['lighting_kwh'],
    'base_load': ['fridge_kwh', 'router_kwh', 'standby_kwh'],
}


@dataclass(frozen=True)
class EconomicMode:
    """Editable defaults for one dashboard economics mode."""

    key: str
    label: str
    currency: str
    capex_per_kwp: float
    export_price_per_kwh: float
    annual_opex_fraction: float
    night_price: float
    day_price: float
    peak_price: float
    late_price: float
    description: str


ECONOMIC_MODES = {
    'hackathon': EconomicMode(
        key='hackathon', label='Hackathon assumptions', currency='EUR',
        capex_per_kwp=1300.0, export_price_per_kwh=0.08,
        annual_opex_fraction=0.01, night_price=0.18, day_price=0.28,
        peak_price=0.40, late_price=0.28,
        description='Fixed organiser assumptions for comparable judging results.'),
    'poland': EconomicMode(
        key='poland', label='Poland scenario', currency='PLN',
        capex_per_kwp=5000.0, export_price_per_kwh=0.35,
        annual_opex_fraction=0.01, night_price=1.10, day_price=1.10,
        peak_price=1.10, late_price=1.10,
        description=('Editable planning defaults. Polish net-billing and the full '
                     'retail bill depend on the contract, market period and operator.')),
}


def local_tariff(index: pd.DatetimeIndex, mode: EconomicMode) -> np.ndarray:
    """Return the mode's purchase price for each physical UTC hour."""
    if index.tz is None:
        raise ValueError('A timezone-aware DatetimeIndex is required')
    hour = index.tz_convert('Europe/Warsaw').hour
    return np.select(
        [hour < 6, hour < 17, hour < 22],
        [mode.night_price, mode.day_price, mode.peak_price],
        default=mode.late_price,
    ).astype(float)


def normalized_pv_profile(hourly: pd.DataFrame,
                          specific_yield_kwh_per_kwp: float = 1000.0) -> np.ndarray:
    """Create an hourly 1-kWp profile normalized to a stated annual yield.

    The supplied short-wave radiation is used only as the production shape.
    Normalization makes the annual yield explicit and avoids pretending that
    horizontal instantaneous irradiance is measured plane-of-array energy.
    """
    if not math.isfinite(specific_yield_kwh_per_kwp) or specific_yield_kwh_per_kwp <= 0:
        raise ValueError('specific_yield_kwh_per_kwp must be positive')
    if 'shortwave_radiation_instant' not in hourly or 'timestamp_utc' not in hourly:
        raise ValueError('hourly data requires timestamp_utc and shortwave_radiation_instant')
    index = pd.DatetimeIndex(pd.to_datetime(hourly.timestamp_utc, utc=True))
    years = np.unique(index.tz_convert('Europe/Warsaw').year)
    radiation = np.maximum(
        pd.to_numeric(hourly.shortwave_radiation_instant, errors='raise').to_numpy(float), 0.0)
    if not np.isfinite(radiation).all() or radiation.sum() <= 0:
        raise ValueError('Solar-shape radiation must be finite and contain daylight')
    return radiation * (specific_yield_kwh_per_kwp * len(years) / radiation.sum())


def energy_balance(load_kwh, pv_kwh, purchase_price, export_price):
    """Calculate simultaneous self-use, import, export and net grid cost."""
    load, pv, price = np.broadcast_arrays(
        np.asarray(load_kwh, float), np.asarray(pv_kwh, float),
        np.asarray(purchase_price, float))
    if (not np.isfinite(load).all() or not np.isfinite(pv).all() or
            not np.isfinite(price).all() or (load < 0).any() or
            (pv < 0).any() or (price < 0).any() or export_price < 0):
        raise ValueError('Energy and prices must be finite and nonnegative')
    self_use = np.minimum(load, pv)
    imported = load - self_use
    exported = pv - self_use
    return {
        'self_used_kwh': self_use,
        'grid_import_kwh': imported,
        'grid_export_kwh': exported,
        'grid_cost': imported * price - exported * export_price,
    }


def learn_habit_constraints(events: pd.DataFrame) -> dict[str, dict]:
    """Learn conservative default windows from historical flexible-device runs.

    Quantiles describe observed behaviour rather than claiming to know the
    family's true comfort constraints.  The dashboard exposes every learned
    value for editing.
    """
    required = {'device', 'start_utc', 'duration_minutes', 'energy_kwh'}
    if not required.issubset(events):
        raise ValueError(f'appliance events missing {sorted(required - set(events))}')
    selected = events[events.device.isin(DEVICE_CATEGORY)].copy()
    selected['category'] = selected.device.map(DEVICE_CATEGORY)
    selected['start'] = pd.to_datetime(selected.start_utc, utc=True).dt.tz_convert('Europe/Warsaw')
    selected['start_hour'] = selected.start.dt.hour + selected.start.dt.minute / 60
    result = {}
    for device, group in selected.groupby('category'):
        duration = float(group.duration_minutes.median()) / 60
        q10 = float(group.start_hour.quantile(.10))
        q50 = float(group.start_hour.quantile(.50))
        q90 = float(group.start_hour.quantile(.90))
        settings = DEVICE_SETTINGS[device]
        result[device] = {
            'events': int(len(group)),
            'energy_kwh': float(group.energy_kwh.sum()),
            'observed_start_p10': q10,
            'observed_start_median': q50,
            'observed_start_p90': q90,
            'earliest_start_hour': max(0, int(math.floor(q10))),
            'latest_finish_hour': min(24, int(math.ceil(q90 + duration))),
            'maximum_shift_hours': settings['maximum_shift_hours'],
            'duration_median_hours': duration,
            'enabled_by_default': settings['enabled'],
            'requires_occupancy': settings['requires_occupancy'],
            'automation': settings['automation'],
        }
    # Heating and tank operation have no appliance-event records. They are
    # exposed as opt-in proxy controls until a stateful controller supplies
    # comfort-safe flexibility windows.
    result['space_heating'] = {
        'events': 0, 'energy_kwh': 0.0, 'observed_start_p10': 0.0,
        'observed_start_median': 12.0, 'observed_start_p90': 23.0,
        'earliest_start_hour': 0, 'latest_finish_hour': 24,
        'maximum_shift_hours': 2, 'duration_median_hours': 1.0,
        'enabled_by_default': False, 'requires_occupancy': False,
        'automation': 'model-required',
    }
    result['water_heater'] = {
        'events': 0, 'energy_kwh': 0.0, 'observed_start_p10': 0.0,
        'observed_start_median': 12.0, 'observed_start_p90': 23.0,
        'earliest_start_hour': 0, 'latest_finish_hour': 24,
        'maximum_shift_hours': 4, 'duration_median_hours': 1.0,
        'enabled_by_default': False, 'requires_occupancy': False,
        'automation': 'model-required',
    }
    return result


def _event_hour_profile(start: pd.Timestamp, duration_minutes: int,
                        energy_kwh: float, shaped_cycle: bool) -> list[float]:
    """Aggregate the generator's minute cycle shape into shifted hourly bins."""
    minute_power = (cycle_profile(int(duration_minutes), float(energy_kwh))
                    if shaped_cycle else
                    np.full(int(duration_minutes), float(energy_kwh) * 60 / duration_minutes))
    offsets = (start.minute + np.arange(len(minute_power))) // 60
    profile = np.bincount(offsets, weights=minute_power / 60)
    return profile.astype(float).tolist()


def prepare_flexible_events(hourly: pd.DataFrame, events: pd.DataFrame) -> tuple[list[dict], np.ndarray]:
    """Encode shiftable cycles and a non-shiftable base load for the browser."""
    index = pd.DatetimeIndex(pd.to_datetime(hourly.timestamp_utc, utc=True))
    if not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError('timestamp_utc must be unique and ordered')
    positions = {stamp: i for i, stamp in enumerate(index)}
    encoded = []
    reconstructed = np.zeros(len(hourly), dtype=float)
    selected = events[events.device.isin(DEVICE_CATEGORY)]
    for row in selected.itertuples(index=False):
        start = pd.Timestamp(row.start_utc)
        start = start.tz_localize('UTC') if start.tzinfo is None else start.tz_convert('UTC')
        hour = start.floor('h')
        if hour not in positions:
            continue
        start_index = positions[hour]
        profile = _event_hour_profile(
            start, int(row.duration_minutes), float(row.energy_kwh),
            row.device in ('washing_machine', 'dishwasher'))
        stop = min(len(hourly), start_index + len(profile))
        reconstructed[start_index:stop] += np.asarray(profile[:stop-start_index])
        encoded.append({
            'category': DEVICE_CATEGORY[row.device],
            'resource': row.device,
            'startIndex': int(start_index),
            'durationMinutes': int(row.duration_minutes),
            'energyKwh': round(float(row.energy_kwh), 6),
            'profile': [round(value, 7) for value in profile],
            'proxy': False,
        })
    # Conservative proxy flexibility. These shares are excluded by default and
    # clearly labelled in the UI because a future thermal/controller model must
    # validate tank temperature and indoor comfort before dispatch.
    for category, column, share in [
            ('space_heating', 'space_heating_kwh', .15),
            ('water_heater', 'water_heater_kwh', .50)]:
        if column not in hourly:
            continue
        values = pd.to_numeric(hourly[column], errors='raise').to_numpy(float)
        for start_index in np.flatnonzero(values > .01):
            energy = float(values[start_index] * share)
            reconstructed[start_index] += energy
            encoded.append({
                'category': category, 'resource': category,
                'startIndex': int(start_index), 'durationMinutes': 60,
                'energyKwh': round(energy, 6), 'profile': [round(energy, 7)],
                'proxy': True,
            })
    load = pd.to_numeric(hourly.total_kwh, errors='raise').to_numpy(float)
    base = load - reconstructed
    if base.min() < -2e-5:
        raise ValueError('Flexible-event reconstruction exceeds total load')
    base = np.maximum(base, 0)
    return encoded, base


def device_insights(hourly: pd.DataFrame, events: pd.DataFrame) -> dict[str, dict]:
    """Summarise annual energy and the typical 24-hour shape per device group."""
    index = pd.DatetimeIndex(pd.to_datetime(hourly.timestamp_utc, utc=True))
    local = index.tz_convert('Europe/Warsaw')
    years = len(set(local.year))
    days = len(set(local.strftime('%Y-%m-%d')))
    categories = events.assign(category=events.device.map(DEVICE_CATEGORY)).dropna(subset=['category'])
    insights = {}
    for category, columns in CATEGORY_COLUMNS.items():
        available = [column for column in columns if column in hourly]
        if not available:
            continue
        values = hourly[available].apply(pd.to_numeric, errors='raise').sum(axis=1).to_numpy(float)
        by_hour = pd.Series(values).groupby(local.hour).sum().reindex(range(24), fill_value=0)
        group = categories[categories.category == category]
        insights[category] = {
            'annualKwh': round(float(values.sum() / years), 2),
            'typicalDayKwh': [round(float(v / days), 5) for v in by_hour],
            'peakHour': int(by_hour.to_numpy().argmax()),
            'events': int(len(group)),
            'sourceColumns': available,
        }
    return insights


def build_dashboard_data(hourly: pd.DataFrame, events: pd.DataFrame) -> dict:
    """Build the compact, source-backed payload embedded in the offline UI."""
    index = pd.DatetimeIndex(pd.to_datetime(hourly.timestamp_utc, utc=True))
    pv_unit = normalized_pv_profile(hourly, 1000.0)
    encoded_events, base_load = prepare_flexible_events(hourly, events)
    learned = learn_habit_constraints(events)
    local = index.tz_convert('Europe/Warsaw')
    occupancy = pd.to_numeric(hourly.occupancy_mean, errors='raise').to_numpy(float)
    day_type = np.where(local.dayofweek < 5, 'weekday', 'weekend')
    occupancy_profiles = {}
    for kind in ('weekday', 'weekend'):
        profile = pd.Series(occupancy[day_type == kind]).groupby(
            local.hour[day_type == kind]).mean().reindex(range(24), fill_value=0)
        occupancy_profiles[kind] = [round(float(value), 2) for value in profile]
    years = sorted(set(local.year))
    return {
        'timestampUtc': index.strftime('%Y-%m-%dT%H:%M:%SZ').tolist(),
        'localHour': local.hour.astype(int).tolist(),
        'localDate': local.strftime('%Y-%m-%d').tolist(),
        'localDayType': day_type.tolist(),
        'occupancyPeople': np.round(occupancy, 3).tolist(),
        'occupancyProfiles': occupancy_profiles,
        'loadKwh': np.round(pd.to_numeric(hourly.total_kwh).to_numpy(float), 6).tolist(),
        'baseLoadKwh': np.round(base_load, 6).tolist(),
        'pvKwhPerKwpAt1000Yield': np.round(pv_unit, 7).tolist(),
        'flexibleEvents': encoded_events,
        'learnedConstraints': learned,
        'deviceInsights': device_insights(hourly, events),
        'years': years,
        'yearCount': len(years),
        'modes': {key: asdict(value) for key, value in ECONOMIC_MODES.items()},
        'capacityOptions': [0, 2, 4, 6, 8, 10],
        'sources': {
            'household': 'Generated hourly.csv and appliance_events.csv',
            'challenge': 'HackoWatt Common Challenge Assumptions',
            'solar': ('Hourly daylight shape from supplied Silesia weather; annual output '
                      'normalized to the editable specific-yield assumption.'),
        },
        'modelContract': {
            'required': ['timestamp_utc', 'load_kwh'],
            'optional': ['occupancy_people', 'model_id', 'issued_at_utc'],
            'activeLoadSource': str(hourly.attrs.get('load_source', 'historical total_kwh')),
        },
    }
