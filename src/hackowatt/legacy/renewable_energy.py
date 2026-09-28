"""Archived offline Renewable Energy Simulator exporter.

The maintained presentation path is the unified Streamlit dashboard.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..components.base import ProjectContext
from ..renewable import build_dashboard_data, normalized_pv_profile


def apply_model_profile(hourly: pd.DataFrame, profile_path: Path | None) -> pd.DataFrame:
    """Apply a colleague model through a small, explicit interchange contract."""
    if profile_path is None:
        hourly.attrs['load_source'] = 'historical total_kwh'
        return hourly
    profile = pd.read_csv(profile_path)
    required = {'timestamp_utc', 'load_kwh'}
    if not required.issubset(profile):
        raise ValueError(f'Model profile requires columns {sorted(required)}')
    source_time = pd.to_datetime(hourly.timestamp_utc, utc=True)
    model_time = pd.to_datetime(profile.timestamp_utc, utc=True)
    if model_time.duplicated().any() or len(profile) != len(hourly) or not model_time.equals(source_time):
        raise ValueError('Model profile timestamps must uniquely match hourly.csv in the current dashboard version')
    load = pd.to_numeric(profile.load_kwh, errors='raise')
    if not np.isfinite(load).all() or (load < 0).any():
        raise ValueError('Model load_kwh must be finite and nonnegative')
    result = hourly.copy()
    result['total_kwh'] = load.to_numpy(float)
    if 'occupancy_people' in profile:
        occupancy = pd.to_numeric(profile.occupancy_people, errors='raise')
        if (not np.isfinite(occupancy).all() or (occupancy < 0).any() or
                (occupancy > 4).any()):
            raise ValueError('occupancy_people must stay between 0 and 4')
        result['occupancy_mean'] = occupancy.to_numpy(float)
    model_id = (str(profile.model_id.iloc[0]) if 'model_id' in profile and
                profile.model_id.nunique(dropna=False) == 1 else profile_path.name)
    result.attrs['load_source'] = f'model profile: {model_id}'
    return result


def build_forecast_payload(hourly: pd.DataFrame, forecast_folder: Path | None) -> dict:
    """Load the latest leakage-safe rolling forecast as an inspectable demo horizon."""
    if forecast_folder is None:
        return {'available': False, 'reason': 'No forecast folder configured'}
    predictions_path = Path(forecast_folder) / 'forecast_predictions.csv'
    metrics_path = Path(forecast_folder) / 'forecast_metrics.csv'
    if not predictions_path.exists() or not metrics_path.exists():
        return {'available': False, 'reason': 'Run `python main.py forecast` first'}
    predictions = pd.read_csv(predictions_path)
    metrics = pd.read_csv(metrics_path)
    required = {'origin_utc', 'timestamp_utc', 'horizon_h', 'model_id',
                'actual_kwh', 'load_hat'}
    if not required.issubset(predictions):
        raise ValueError(f'Forecast predictions require columns {sorted(required)}')
    candidates = metrics[(metrics.bucket == 'hours_1_24') &
                         (metrics.model_id != 'seasonal_naive')]
    if candidates.empty:
        candidates = metrics[metrics.bucket == 'hours_1_24']
    best = candidates.sort_values(['wape_pct', 'mae_kwh']).iloc[0]
    model_id = str(best.model_id)
    model_rows = predictions[predictions.model_id == model_id].copy()
    model_rows['origin_time'] = pd.to_datetime(model_rows.origin_utc, utc=True)
    latest_origin = model_rows.origin_time.max()
    horizon = model_rows[model_rows.origin_time == latest_origin].sort_values('horizon_h')
    if len(horizon) < 24:
        raise ValueError('Latest forecast origin contains fewer than 24 hours')

    # Empirical forecast intervals use only rolling-origin residuals for the
    # same model and horizon step. They are labelled as backtest intervals.
    model_rows['residual'] = (pd.to_numeric(model_rows.actual_kwh) -
                              pd.to_numeric(model_rows.load_hat))
    earlier = model_rows[(model_rows.origin_time < latest_origin) &
                         (pd.to_datetime(model_rows.timestamp_utc, utc=True) < latest_origin)]
    quantiles = earlier.groupby('horizon_h').residual.quantile([.1, .9]).unstack()
    lower, upper = [], []
    for row in horizon.itertuples():
        q = quantiles.loc[row.horizon_h] if row.horizon_h in quantiles.index else pd.Series({.1: 0, .9: 0})
        lower.append(max(0.0, float(row.load_hat + q.get(.1, 0))))
        upper.append(max(lower[-1], float(row.load_hat + q.get(.9, 0))))

    modular = predictions[(predictions.model_id == 'modular_component_gbdt') &
                          (pd.to_datetime(predictions.origin_utc, utc=True) == latest_origin)]
    modular = modular.sort_values('horizon_h').set_index('horizon_h')
    index = pd.DatetimeIndex(pd.to_datetime(hourly.timestamp_utc, utc=True))
    source_lookup = {value: i for i, value in enumerate(index)}
    forecast_time = pd.DatetimeIndex(pd.to_datetime(horizon.timestamp_utc, utc=True))
    source_indices = [source_lookup.get(value, -1) for value in forecast_time]
    if any(i < 0 for i in source_indices):
        raise ValueError('Forecast horizon timestamps must exist in hourly history for demo backtest')

    origin_index = source_lookup.get(latest_origin)
    training = hourly.iloc[:origin_index] if origin_index is not None else hourly
    training_index = pd.DatetimeIndex(pd.to_datetime(training.timestamp_utc, utc=True))
    training_local = training_index.tz_convert('Europe/Warsaw')
    training_kind = np.where(training_local.dayofweek < 5, 'weekday', 'weekend')
    draw = (pd.to_numeric(training['hot_water_mixed_l'], errors='coerce').fillna(0)
            if 'hot_water_mixed_l' in training else
            pd.Series(np.zeros(len(training)), index=training.index))
    draw_profile = pd.DataFrame({'draw': draw.to_numpy(float), 'kind': training_kind,
                                 'hour': training_local.hour}).groupby(['kind', 'hour']).draw.mean()
    local = forecast_time.tz_convert('Europe/Warsaw')
    draws = [float(draw_profile.get(('weekday' if t.dayofweek < 5 else 'weekend', t.hour), 0))
             for t in local]

    def component(name: str) -> list[float]:
        result = []
        for h in horizon.horizon_h.astype(int):
            value = modular.at[h, name] if h in modular.index and name in modular else np.nan
            result.append(0.0 if pd.isna(value) else max(0.0, float(value)))
        return result

    metric_payload = {}
    for bucket in ('hours_1_24', 'hours_25_72', 'hours_73_168', 'hours_1_168'):
        row = metrics[(metrics.model_id == model_id) & (metrics.bucket == bucket)]
        if not row.empty:
            metric_payload[bucket] = {
                'maeKwh': round(float(row.iloc[0].mae_kwh), 3),
                'wapePct': round(float(row.iloc[0].wape_pct), 1),
                'peakTimingMaeH': round(float(row.iloc[0].peak_timing_mae_h), 1),
            }
    wape = float(best.wape_pct)
    confidence = 'high' if wape < 20 else ('medium' if wape < 40 else 'low')
    return {
        'available': True,
        'kind': 'historical rolling-origin backtest',
        'isLive': False,
        'modelId': model_id,
        'issueTimeUtc': latest_origin.isoformat(),
        'timestampUtc': forecast_time.strftime('%Y-%m-%dT%H:%M:%SZ').tolist(),
        'sourceIndex': source_indices,
        'localHour': local.hour.astype(int).tolist(),
        'localDayType': np.where(local.dayofweek < 5, 'weekday', 'weekend').tolist(),
        'pvKwhPerKwpAt1000Yield': np.round(normalized_pv_profile(hourly)[source_indices], 7).tolist(),
        'pvSource': 'Historical radiation shape normalised to the annual yield; hindsight replay only.',
        'thermalInputsAvailable': not modular.empty,
        'componentSource': 'Separate modular model estimates; they do not decompose the direct total forecast.',
        'stateSource': 'Previous simulated hourly mean; approximate starting state, not a sensor.',
        'loadKwh': np.round(pd.to_numeric(horizon.load_hat), 5).tolist(),
        'actualKwh': np.round(pd.to_numeric(horizon.actual_kwh), 5).tolist(),
        'lowerKwh': np.round(lower, 5).tolist(),
        'upperKwh': np.round(upper, 5).tolist(),
        'baseKwh': np.round(component('base_hat'), 5).tolist(),
        'behaviourKwh': np.round(component('behaviour_hat'), 5).tolist(),
        'spaceHeatingKwh': np.round(component('space_heating_hat'), 5).tolist(),
        'waterHeatingKwh': np.round(component('water_heater_hat'), 5).tolist(),
        'outdoorC': np.round(pd.to_numeric(hourly.iloc[source_indices].temperature_2m), 3).tolist(),
        'windMs': np.round(pd.to_numeric(hourly.iloc[source_indices].wind_ms), 3).tolist(),
        'solarRadiationWm2': np.round(pd.to_numeric(
            hourly.iloc[source_indices].shortwave_radiation_instant), 3).tolist(),
        'hotWaterDrawL': np.round(draws, 3).tolist(),
        'initialIndoorC': float(hourly.iloc[max(source_indices[0] - 1, 0)].indoor_c),
        'initialTankC': float(hourly.iloc[max(source_indices[0] - 1, 0)].tank_c),
        'metrics': metric_payload,
        'modelComparison': metrics[['model_id', 'bucket', 'mae_kwh', 'wape_pct',
                                    'peak_timing_mae_h']].round(3).to_dict('records'),
        'confidence': confidence,
        'interval': '10th–90th residual percentiles from earlier completed origins; uncalibrated empirical range',
        'intervalSamples': int(earlier.origin_time.nunique()),
        'weatherAssumption': 'Recorded weather is used as a perfect issued forecast in this validation run.',
    }


def build_issued_forecast_payload(path: Path, sensor_state_path: Path | None = None) -> dict:
    """Read a provider-neutral future forecast contract for production integration."""
    frame = pd.read_csv(path)
    required = {'timestamp_utc', 'load_kwh', 'outdoor_c', 'wind_ms', 'radiation_wm2'}
    if not required.issubset(frame):
        raise ValueError(f'Issued forecast requires columns {sorted(required)}')
    time = pd.DatetimeIndex(pd.to_datetime(frame.timestamp_utc, utc=True))
    if len(frame) < 24 or time.duplicated().any() or not time.is_monotonic_increasing:
        raise ValueError('Issued forecast must contain at least 24 unique, increasing UTC hours')
    if len(time) > 1 and not np.all((time[1:] - time[:-1]) == pd.Timedelta(hours=1)):
        raise ValueError('Issued forecast timestamps must be exactly hourly')
    local = time.tz_convert('Europe/Warsaw')

    def values(name: str, fallback, nonnegative: bool = True) -> list[float]:
        raw = frame[name] if name in frame else fallback
        if np.isscalar(raw):
            raw = np.full(len(frame), raw)
        series = pd.Series(pd.to_numeric(raw, errors='raise'))
        if not np.isfinite(series).all():
            raise ValueError(f'Issued forecast {name} must be finite')
        result = series.to_numpy(float)
        if nonnegative:
            if (result < 0).any():
                raise ValueError(f'Issued forecast {name} must be nonnegative')
        return np.round(result, 5).tolist()

    load = values('load_kwh', 0)
    lower = values('lower_kwh', load)
    upper = values('upper_kwh', load)
    if np.any(np.asarray(lower) > np.asarray(upper)):
        raise ValueError('lower_kwh must not exceed upper_kwh')
    state = {}
    if sensor_state_path:
        state = json.loads(Path(sensor_state_path).read_text(encoding='utf-8'))
        for key, low, high in [('indoor_c', 0, 50), ('tank_c', 0, 95)]:
            if key in state and (not np.isfinite(float(state[key])) or
                                 not low <= float(state[key]) <= high):
                raise ValueError(f'Sensor {key} is outside the supported range')
    issued_at = None
    if 'issued_at_utc' in frame:
        issued_times = pd.to_datetime(frame.issued_at_utc, utc=True, errors='raise')
        if issued_times.isna().any() or issued_times.nunique() != 1 or issued_times.iloc[0] > time[0]:
            raise ValueError('issued_at_utc must be one issue time at or before the forecast start')
        issued_at = issued_times.iloc[0].isoformat()
    return {
        'available': True, 'kind': 'imported external forecast snapshot', 'isLive': False,
        'modelId': (str(frame.model_id.iloc[0]) if 'model_id' in frame else path.name),
        'issueTimeUtc': issued_at,
        'timestampUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ').tolist(),
        'sourceIndex': [-1] * len(frame),
        'localHour': local.hour.astype(int).tolist(),
        'localDayType': np.where(local.dayofweek < 5, 'weekday', 'weekend').tolist(),
        'loadKwh': load, 'actualKwh': [], 'lowerKwh': lower, 'upperKwh': upper,
        'baseKwh': values('base_kwh', 0),
        'behaviourKwh': values('behaviour_kwh', load),
        'spaceHeatingKwh': values('space_heating_kwh', 0),
        'waterHeatingKwh': values('water_heating_kwh', 0),
        'outdoorC': values('outdoor_c', 0, False), 'windMs': values('wind_ms', 0),
        'solarRadiationWm2': values('radiation_wm2', 0),
        'pvKwhPerKwpAt1000Yield': np.round(
            np.asarray(values('radiation_wm2', 0)) / 1000 * .85, 5).tolist(),
        'pvSource': 'Irradiance / 1000 × 0.85 planning proxy; optional pv_kwh_per_kwp replaces it.',
        'thermalInputsAvailable': {'space_heating_kwh', 'water_heating_kwh', 'hot_water_draw_l'}.issubset(frame),
        'componentSource': 'Imported component estimates; missing values are unknown.',
        'stateSource': ('Imported sensor JSON; freshness must be checked before control.' if state else 'Assumed temperatures; manually editable.'),
        'hotWaterDrawL': values('hot_water_draw_l', 0),
        'initialIndoorC': float(state.get('indoor_c', 20)),
        'initialTankC': float(state.get('tank_c', 55)),
        'metrics': {}, 'confidence': 'unquantified',
        'interval': ('provider interval' if 'lower_kwh' in frame else 'not provided'),
        'weatherAssumption': 'Weather and load values come from the issued forecast contract.',
    }


def build_renewable_dashboard(input_folder: Path, output_folder: Path,
                              model_profile_path: Path | None = None,
                              forecast_folder: Path | None = None,
                              issued_forecast_path: Path | None = None,
                              sensor_state_path: Path | None = None) -> Path:
    input_folder, output_folder = Path(input_folder), Path(output_folder)
    hourly_path = input_folder / 'hourly.csv'
    events_path = input_folder / 'appliance_events.csv'
    if not hourly_path.exists() or not events_path.exists():
        raise FileNotFoundError(
            f'Expected {hourly_path} and {events_path}; run `python main.py generate` first.')
    hourly = pd.read_csv(hourly_path, dtype={'vacation_block': 'string'}, low_memory=False)
    hourly = apply_model_profile(hourly, model_profile_path)
    events = pd.read_csv(events_path)
    data = build_dashboard_data(hourly, events)
    data['forecast'] = (build_issued_forecast_payload(issued_forecast_path, sensor_state_path)
                        if issued_forecast_path else
                        build_forecast_payload(hourly, forecast_folder))
    if issued_forecast_path:
        issued = pd.read_csv(issued_forecast_path)
        if 'pv_kwh_per_kwp' in issued:
            pv = pd.to_numeric(issued.pv_kwh_per_kwp, errors='raise').to_numpy(float)
            if not np.isfinite(pv).all() or (pv < 0).any():
                raise ValueError('pv_kwh_per_kwp must be finite and nonnegative')
            data['forecast']['pvKwhPerKwpAt1000Yield'] = pv.tolist()
            data['forecast']['pvSource'] = 'Imported per-kWp PV forecast (annual yield slider does not rescale it).'
            data['forecast']['pvIsProvider'] = True
    house_path, config_path = input_folder / 'resolved_house.json', input_folder / 'run_config.json'
    if house_path.exists() and config_path.exists():
        run_config = json.loads(config_path.read_text(encoding='utf-8'))
        data['thermalModel'] = {
            'available': True,
            'house': json.loads(house_path.read_text(encoding='utf-8')),
            'settings': run_config.get('thermal', {}),
            'status': 'stateful one-zone RC building and well-mixed tank',
        }
    else:
        data['thermalModel'] = {'available': False, 'status': 'House/config files unavailable'}
    source = Path(__file__).resolve().parent / 'assets'
    template = (source / 'renewable_dashboard.html').read_text(
        encoding='utf-8')
    for name in ('renewable_engine.js', 'renewable_ui.js', 'renewable_style.css'):
        template = template.replace('/* EMBED_' + name + ' */', (source / name).read_text(encoding='utf-8'))
    output_folder.mkdir(parents=True, exist_ok=True)
    target = output_folder / 'renewable_energy_simulator.html'
    target.write_text(template.replace(
        '/* EMBED_DATA */',
        'const D=' + json.dumps(data, separators=(',', ':'), ensure_ascii=False, allow_nan=False).replace('<', '\\u003c') + ';'),
        encoding='utf-8')
    (output_folder / 'simulator_methodology.html').write_text(
        (source / 'simulator_methodology.html').read_text(encoding='utf-8'), encoding='utf-8')
    handbook = source.parents[4] / 'output' / 'pdf' / 'HackoWatt_Simulator_Handbook.pdf'
    if handbook.exists():
        (output_folder / handbook.name).write_bytes(handbook.read_bytes())
    return target


class RenewableEnergyComponent:
    name = 'renewable-dashboard'
    help = 'Build the interactive Renewable Energy Simulator dashboard.'

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument('--input', default='results/default',
                            help='Generated household directory relative to the project root.')
        parser.add_argument('--output', default='results/renewable',
                            help='Dashboard output directory relative to the project root.')
        parser.add_argument('--model-profile',
                            help=('Optional CSV relative to the project root with unique '
                                  'timestamp_utc and load_kwh; occupancy_people is optional.'))
        parser.add_argument('--forecast-input', default='results/forecast',
                            help=('Forecast result directory relative to the project root. Run '
                                  '`python main.py forecast` first for the Tomorrow view.'))
        parser.add_argument('--issued-forecast',
                            help='Optional future hourly CSV using the live forecast contract.')
        parser.add_argument('--sensor-state',
                            help='Optional JSON with indoor_c and tank_c for the forecast start.')
        parser.set_defaults(component=self)

    def run(self, args, context: ProjectContext) -> int:
        target = build_renewable_dashboard(
            context.path(args.input), context.path(args.output),
            context.path(args.model_profile) if args.model_profile else None,
            context.path(args.forecast_input) if args.forecast_input else None,
            context.path(args.issued_forecast) if args.issued_forecast else None,
            context.path(args.sensor_state) if args.sensor_state else None)
        print(target)
        return 0
