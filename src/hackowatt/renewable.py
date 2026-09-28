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
    selected = events[events.device.isin(['washing_machine', 'dishwasher'])].copy()
    selected['start'] = pd.to_datetime(selected.start_utc, utc=True).dt.tz_convert('Europe/Warsaw')
    selected['start_hour'] = selected.start.dt.hour + selected.start.dt.minute / 60
    result = {}
    for device, group in selected.groupby('device'):
        duration = float(group.duration_minutes.median()) / 60
        q10 = float(group.start_hour.quantile(.10))
        q50 = float(group.start_hour.quantile(.50))
        q90 = float(group.start_hour.quantile(.90))
        result[device] = {
            'events': int(len(group)),
            'energy_kwh': float(group.energy_kwh.sum()),
            'observed_start_p10': q10,
            'observed_start_median': q50,
            'observed_start_p90': q90,
            'earliest_start_hour': max(0, int(math.floor(q10))),
            'latest_finish_hour': min(24, int(math.ceil(q90 + duration))),
            'maximum_shift_hours': 6,
            'duration_median_hours': duration,
        }
    return result


def _event_hour_profile(start: pd.Timestamp, duration_minutes: int,
                        energy_kwh: float) -> list[float]:
    """Aggregate the generator's minute cycle shape into shifted hourly bins."""
    minute_power = cycle_profile(int(duration_minutes), float(energy_kwh))
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
    selected = events[events.device.isin(['washing_machine', 'dishwasher'])]
    for row in selected.itertuples(index=False):
        start = pd.Timestamp(row.start_utc)
        start = start.tz_localize('UTC') if start.tzinfo is None else start.tz_convert('UTC')
        hour = start.floor('h')
        if hour not in positions:
            continue
        start_index = positions[hour]
        profile = _event_hour_profile(start, int(row.duration_minutes), float(row.energy_kwh))
        stop = min(len(hourly), start_index + len(profile))
        reconstructed[start_index:stop] += np.asarray(profile[:stop-start_index])
        encoded.append({
            'device': row.device,
            'startIndex': int(start_index),
            'durationMinutes': int(row.duration_minutes),
            'energyKwh': round(float(row.energy_kwh), 6),
            'profile': [round(value, 7) for value in profile],
        })
    load = pd.to_numeric(hourly.total_kwh, errors='raise').to_numpy(float)
    base = load - reconstructed
    if base.min() < -2e-5:
        raise ValueError('Flexible-event reconstruction exceeds total load')
    base = np.maximum(base, 0)
    return encoded, base


def build_dashboard_data(hourly: pd.DataFrame, events: pd.DataFrame) -> dict:
    """Build the compact, source-backed payload embedded in the offline UI."""
    index = pd.DatetimeIndex(pd.to_datetime(hourly.timestamp_utc, utc=True))
    pv_unit = normalized_pv_profile(hourly, 1000.0)
    encoded_events, base_load = prepare_flexible_events(hourly, events)
    learned = learn_habit_constraints(events)
    local = index.tz_convert('Europe/Warsaw')
    years = sorted(set(local.year))
    return {
        'timestampUtc': index.strftime('%Y-%m-%dT%H:%M:%SZ').tolist(),
        'localHour': local.hour.astype(int).tolist(),
        'localDate': local.strftime('%Y-%m-%d').tolist(),
        'loadKwh': np.round(pd.to_numeric(hourly.total_kwh).to_numpy(float), 6).tolist(),
        'baseLoadKwh': np.round(base_load, 6).tolist(),
        'pvKwhPerKwpAt1000Yield': np.round(pv_unit, 7).tolist(),
        'flexibleEvents': encoded_events,
        'learnedConstraints': learned,
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
    }
