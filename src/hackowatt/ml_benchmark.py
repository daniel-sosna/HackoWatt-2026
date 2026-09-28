"""Preparation, occupancy forecasting, and benchmark models for hourly demand.

The source hourly.csv is never modified.  This module writes a separate,
chronological training/test copy and evaluates recursive direct and modular
forecasts using predicted occupancy only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import pickle

import numpy as np
import pandas as pd

from .forecasting import BASE_COLUMNS, THERMAL_COLUMNS, load_hourly

WEATHER_COLUMNS = [
    'temperature_2m', 'cloud_cover', 'relative_humidity_2m', 'wind_speed_10m',
    'precipitation', 'snowfall', 'shortwave_radiation_instant', 'wind_ms',
]
FLAG_COLUMNS = [
    'public_holiday', 'school_break', 'family_vacation', 'school_day', 'ania_wfh',
]
LAG_NAMES = ('lag_1h', 'lag_24h', 'lag_168h', 'mean_24h', 'mean_168h')
MODEL_NAMES = ('random_forest', 'xgboost', 'catboost')
BRIGHT_COLOURS = {
    'direct_random_forest': '#FF006E',
    'direct_xgboost': '#FB5607',
    'direct_catboost': '#8338EC',
    'modular_random_forest': '#00B4D8',
    'modular_xgboost': '#06D6A0',
    'modular_catboost': '#3A86FF',
    'random_forest': '#FF006E',
    'xgboost': '#FB5607',
    'catboost': '#8338EC',
}


@dataclass
class PreparedData:
    base_features: pd.DataFrame
    targets: pd.DataFrame
    cutoff: int
    train: pd.DataFrame
    test: pd.DataFrame
    manifest: dict


def _numeric(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.astype(float)
    return pd.to_numeric(series, errors='raise').astype(float)


def make_base_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build only known-in-advance calendar/weather features.

    Occupancy is intentionally absent. It is predicted by a separate model and
    later supplied as ``occupancy_hat`` to the electricity models.
    """
    local = df.index.tz_convert('Europe/Warsaw')
    hour = local.hour.to_numpy()
    weekday = local.dayofweek.to_numpy()
    month = local.month.to_numpy()
    day_of_year = local.dayofyear.to_numpy()
    result = pd.DataFrame(index=df.index)
    # Explicit fields requested for transparent inspection in the saved data.
    result['month'] = month
    result['day_of_week'] = weekday
    result['hour'] = hour
    result['day_of_year'] = day_of_year
    result['is_weekend'] = (weekday >= 5).astype(float)
    # Cyclic equivalents avoid treating December and January as distant values.
    result['month_sin'] = np.sin(2*np.pi*month/12)
    result['month_cos'] = np.cos(2*np.pi*month/12)
    result['weekday_sin'] = np.sin(2*np.pi*weekday/7)
    result['weekday_cos'] = np.cos(2*np.pi*weekday/7)
    result['hour_sin'] = np.sin(2*np.pi*hour/24)
    result['hour_cos'] = np.cos(2*np.pi*hour/24)
    result['year_sin'] = np.sin(2*np.pi*day_of_year/365.25)
    result['year_cos'] = np.cos(2*np.pi*day_of_year/365.25)
    for column in WEATHER_COLUMNS + FLAG_COLUMNS:
        if column not in df:
            raise ValueError(f'hourly.csv is missing required feature column {column}')
        result[column] = _numeric(df[column])
    result['heating_degree_c'] = np.maximum(0.0, 18.0-result['temperature_2m'])
    result['cooling_degree_c'] = np.maximum(0.0, result['temperature_2m']-22.0)
    result['dark_hour'] = (result['shortwave_radiation_instant'] < 20.0).astype(float)
    shift = df['marek_shift'].astype(str).str.lower()
    for value in ('morning', 'evening', 'night', 'off'):
        result[f'marek_shift_{value}'] = (shift == value).astype(float)
    vacation = df['vacation_block'].fillna('').astype(str).str.lower()
    result['vacation_summer'] = vacation.str.contains('summer').astype(float)
    result['vacation_winter'] = vacation.str.contains('winter').astype(float)
    result['vacation_spring_autumn'] = (vacation.str.contains('spring') | vacation.str.contains('autumn')).astype(float)
    if not np.isfinite(result.to_numpy(float)).all():
        raise ValueError('Base features contain a non-finite value')
    return result


def component_targets(df: pd.DataFrame) -> pd.DataFrame:
    excluded = set(BASE_COLUMNS + THERMAL_COLUMNS + [
        'total_kwh', 'hot_water_unmet_kwh', 'thermal_residual_kwh',
    ])
    behaviour_columns = [
        c for c in df.columns if c.endswith('_kwh') and c not in excluded
    ]
    targets = pd.DataFrame(index=df.index)
    targets['total_kwh'] = _numeric(df['total_kwh'])
    targets['occupancy_mean'] = _numeric(df['occupancy_mean'])
    targets['base_kwh'] = df[BASE_COLUMNS].sum(axis=1).astype(float)
    targets['behaviour_kwh'] = df[behaviour_columns].sum(axis=1).astype(float)
    targets['space_heating_kwh'] = _numeric(df['space_heating_kwh'])
    targets['water_heater_kwh'] = _numeric(df['water_heater_kwh'])
    targets['hot_water_mixed_l'] = _numeric(df['hot_water_mixed_l'])
    return targets


def lag_frame(values: pd.Series) -> pd.DataFrame:
    """Observed historical lags retained in the saved preparation data."""
    return pd.DataFrame({
        'lag_1h': values.shift(1),
        'lag_24h': values.shift(24),
        'lag_168h': values.shift(168),
        'mean_24h': values.shift(1).rolling(24).mean(),
        'mean_168h': values.shift(1).rolling(168).mean(),
    }, index=values.index)


def prepare_training_data(hourly_path: Path, output_dir: Path,
                          forecast_start_local: str = '2025-05-01 00:00:00',
                          horizon_hours: int = 168) -> PreparedData:
    """Create separate training/test copies for one bounded forecast window."""
    if horizon_hours not in (24, 72, 168):
        raise ValueError('horizon_hours must be one of 24, 72, or 168')
    df = load_hourly(hourly_path)
    base = make_base_features(df)
    targets = component_targets(df)
    local_start = pd.Timestamp(forecast_start_local)
    if local_start.tzinfo is None:
        local_start = local_start.tz_localize('Europe/Warsaw')
    else:
        local_start = local_start.tz_convert('Europe/Warsaw')
    start_utc = local_start.tz_convert('UTC')
    cutoff = int(df.index.get_indexer([start_utc])[0])
    if cutoff < 168 or cutoff + horizon_hours > len(df):
        raise ValueError('Forecast start/horizon must leave 168 training hours and fit within hourly.csv')
    lags = lag_frame(targets['total_kwh'])
    prepared = base.join(lags).copy()
    prepared.insert(0, 'timestamp_utc', df.index.astype(str))
    prepared['target_occupancy_mean'] = targets['occupancy_mean'].to_numpy()
    prepared['target_total_kwh'] = targets['total_kwh'].to_numpy()
    prepared['target_base_kwh'] = targets['base_kwh'].to_numpy()
    prepared['target_behaviour_kwh'] = targets['behaviour_kwh'].to_numpy()
    prepared['target_space_heating_kwh'] = targets['space_heating_kwh'].to_numpy()
    prepared['target_water_heater_kwh'] = targets['water_heater_kwh'].to_numpy()
    prepared['target_hot_water_mixed_l'] = targets['hot_water_mixed_l'].to_numpy()
    positions = np.arange(len(df))
    prepared['split'] = np.where(positions < cutoff, 'train', np.where(positions < cutoff+horizon_hours, 'test', 'unused'))
    # The first 168 rows have insufficient energy history for any load model.
    train = prepared.iloc[168:cutoff].copy()
    test = prepared.iloc[cutoff:cutoff+horizon_hours].copy()
    if train[list(LAG_NAMES)].isna().any().any() or test[list(LAG_NAMES)].isna().any().any():
        raise AssertionError('Prepared rows after the lag warm-up must have complete lags')
    manifest = {
        'source_hourly_csv': str(hourly_path),
        'source_is_immutable': True,
        'rows_source': len(df),
        'rows_train': len(train),
        'rows_test': len(test),
        'forecast_start_local': local_start.isoformat(),
        'max_forecast_horizon_hours': horizon_hours,
        'reported_horizons_hours': [h for h in (24, 72, 168) if h <= horizon_hours],
        'train_start_utc': str(train['timestamp_utc'].iloc[0]),
        'train_end_utc': str(train['timestamp_utc'].iloc[-1]),
        'test_start_utc': str(test['timestamp_utc'].iloc[0]),
        'test_end_utc': str(test['timestamp_utc'].iloc[-1]),
        'calendar_weather_features': list(base.columns),
        'observed_energy_lag_columns': list(LAG_NAMES),
        'load_feature_rule': 'Load models receive occupancy_hat, never occupancy_mean. Recursive forecast predictions replace future energy lags with model predictions.',
        'targets': list(targets.columns),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    train.to_csv(output_dir/'train_model_dataset.csv', index=False, float_format='%.6f')
    test.to_csv(output_dir/'test_model_dataset.csv', index=False, float_format='%.6f')
    (output_dir/'feature_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return PreparedData(base, targets, cutoff, train, test, manifest)


def _new_regressor(name: str):
    if name == 'random_forest':
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(
            n_estimators=40, max_depth=12, max_features=0.85, min_samples_leaf=6,
            n_jobs=1, random_state=20260928,
        )
    if name == 'xgboost':
        from xgboost import XGBRegressor
        return XGBRegressor(
            n_estimators=100, max_depth=6, learning_rate=0.08,
            subsample=0.85, colsample_bytree=0.9, objective='reg:squarederror',
            n_jobs=4, random_state=20260928, tree_method='hist', verbosity=0,
        )
    if name == 'catboost':
        from catboost import CatBoostRegressor
        return CatBoostRegressor(
            iterations=100, depth=6, learning_rate=0.08, loss_function='RMSE',
            random_seed=20260928, verbose=False, allow_writing_files=False,
            thread_count=4,
        )
    raise ValueError(f'Unknown model {name}')


class ConstantRegressor:
    """Serializable predictor for a component that is constant in training."""
    def __init__(self, value: float):
        self.value = float(value)

    def predict(self, x) -> np.ndarray:
        return np.full(len(x), self.value, dtype=float)


def _fit_regressor(name: str, x: np.ndarray, y: np.ndarray):
    if np.ptp(y) < 1e-12:
        return ConstantRegressor(float(y[0]))
    model = _new_regressor(name)
    model.fit(x, y)
    return model


def _new_classifier(name: str):
    if name == 'random_forest':
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=80, max_depth=12, min_samples_leaf=6, class_weight='balanced',
            n_jobs=1, random_state=20260928,
        )
    if name == 'xgboost':
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=100, max_depth=6, learning_rate=0.08, subsample=0.85,
            colsample_bytree=0.9, objective='binary:logistic', eval_metric='logloss',
            n_jobs=4, random_state=20260928, tree_method='hist', verbosity=0,
        )
    if name == 'catboost':
        from catboost import CatBoostClassifier
        return CatBoostClassifier(
            iterations=100, depth=6, learning_rate=0.08, loss_function='Logloss',
            random_seed=20260928, verbose=False, allow_writing_files=False, thread_count=4,
        )
    raise ValueError(f'Unknown classifier {name}')


def _residual_training_matrix(base: pd.DataFrame, occupancy_hat: np.ndarray,
                              target: np.ndarray, end: int) -> tuple[np.ndarray, np.ndarray]:
    rows = np.arange(168, end)
    return _train_matrix(base, occupancy_hat, target, end), target[rows]-target[rows-168]


def _recursive_residual_forecast(model, base: pd.DataFrame, occupancy_hat: np.ndarray,
                                 target_history: np.ndarray, start: int, end: int) -> np.ndarray:
    history = list(np.asarray(target_history[:start], dtype=float))
    prediction = []
    for row in range(start, end):
        x = np.r_[base.iloc[row].to_numpy(float), occupancy_hat[row], _lag_vector(history)]
        value = max(0.0, float(history[-168] + model.predict(np.asarray([x]))[0]))
        prediction.append(value)
        history.append(value)
    return np.asarray(prediction)


def _forecast_hot_water_draws(algorithm: str, base: pd.DataFrame, occupancy_hat: np.ndarray,
                              draws: np.ndarray, cutoff: int, end: int):
    """Forecast draw probability and conditional litre volume without future state."""
    rows = np.arange(168, cutoff)
    # The same hour one week earlier is observed history throughout a maximum
    # 168-hour forecast. It preserves regular shower and morning-routine timing.
    x_train = np.column_stack([
        base.iloc[rows].to_numpy(float), occupancy_hat[rows], draws[rows-168],
    ])
    x_future = np.column_stack([
        base.iloc[cutoff:end].to_numpy(float), occupancy_hat[cutoff:end],
        draws[cutoff-168:end-168],
    ])
    event = draws[rows] > 0.01
    classifier = _new_classifier(algorithm)
    classifier.fit(x_train, event.astype(int))
    probability = classifier.predict_proba(x_future)[:, 1]
    training_probability = classifier.predict_proba(x_train)[:, 1]
    threshold = float(np.quantile(training_probability, 1-event.mean()))
    volume_model = _fit_regressor(algorithm, x_train[event], draws[rows][event])
    conditional_volume = np.maximum(0.0, volume_model.predict(x_future))
    draw_hat = (probability >= threshold).astype(float)*conditional_volume
    return draw_hat, probability, threshold, classifier, volume_model


def _simulate_boiler_from_draw_forecast(draw_l: np.ndarray, df: pd.DataFrame,
                                        cutoff: int, house: dict) -> tuple[np.ndarray, np.ndarray]:
    """Simulate the boiler from observed pre-forecast tank state and predicted draws."""
    c_tank = house['tank_volume_l']*0.001163
    ua = house['tank_loss_w_k']/1000
    setpoint, deadband = house['tank_setpoint_c'], house['tank_deadband_c']
    use_temperature, power = house['water_use_temperature_c'], house['boiler_power_kw']
    tank = float(df['tank_c'].iloc[cutoff-1])
    room_temperature = float(df['indoor_c'].iloc[cutoff-1])
    boiler_on = bool(float(df['water_heater_kwh'].iloc[cutoff-1]) > power*0.05)
    local = df.index[cutoff:cutoff+len(draw_l)].tz_convert('Europe/Warsaw')
    mains = 10+5*np.sin(2*np.pi*(local.dayofyear.to_numpy()-120)/365.25)
    energy, tank_hat = np.zeros(len(draw_l)), np.zeros(len(draw_l))
    dt = 1/60
    for hour, litres in enumerate(draw_l):
        delivered_per_minute = max(0.0, float(litres))/60
        for _ in range(60):
            required = max(0.0, use_temperature-mains[hour])
            demand = delivered_per_minute*0.001163*required
            above = max(0.0, (tank-use_temperature)*c_tank)
            if demand <= above:
                tank -= demand/c_tank
            else:
                remaining = max(0.0, delivered_per_minute-above/max(0.001163*required, 1e-9))
                tank = min(tank, use_temperature)
                tank = mains[hour]+(tank-mains[hour])*np.exp(-remaining/house['tank_volume_l'])
            if tank < setpoint-deadband:
                boiler_on = True
            elif tank >= setpoint:
                boiler_on = False
            minute_power = power if boiler_on else 0.0
            decay = np.exp(-ua*dt/c_tank)
            equilibrium = room_temperature+minute_power/ua
            tank = equilibrium+(tank-equilibrium)*decay
            energy[hour] += minute_power*dt
        tank_hat[hour] = tank
    return energy, tank_hat


def _load_house_parameters(hourly_path: Path) -> dict:
    path = hourly_path.parent/'resolved_house.json'
    if not path.exists():
        raise FileNotFoundError(f'Boiler simulation needs realised house parameters: {path}')
    return json.loads(path.read_text(encoding='utf-8'))
def _lag_vector(history: list[float]) -> list[float]:
    if len(history) < 168:
        raise ValueError('168 history values are required')
    return [
        history[-1], history[-24], history[-168],
        float(np.mean(history[-24:])), float(np.mean(history[-168:])),
    ]


def _train_matrix(base: pd.DataFrame, occupancy_hat: np.ndarray, target: np.ndarray, end: int) -> np.ndarray:
    rows = np.arange(168, end)
    lag_values = np.asarray([_lag_vector(target[:i].tolist()) for i in rows])
    return np.column_stack([base.iloc[rows].to_numpy(float), occupancy_hat[rows], lag_values])


def _recursive_forecast(model, base: pd.DataFrame, occupancy_hat: np.ndarray,
                        target_history: np.ndarray, start: int, end: int) -> np.ndarray:
    history = list(np.asarray(target_history[:start], dtype=float))
    prediction = []
    for row in range(start, end):
        x = np.r_[base.iloc[row].to_numpy(float), occupancy_hat[row], _lag_vector(history)]
        value = max(0.0, float(model.predict(np.asarray([x]))[0]))
        prediction.append(value)
        history.append(value)
    return np.asarray(prediction)


def _regression_metrics(actual: np.ndarray, prediction: np.ndarray) -> dict:
    actual = np.asarray(actual, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    return {
        'mae': float(np.mean(np.abs(prediction-actual))),
        'rmse': float(np.sqrt(np.mean((prediction-actual)**2))),
        'wape_pct': float(100*np.abs(prediction-actual).sum()/actual.sum()),
        'bias_kwh': float(np.mean(prediction-actual)),
        'n_hours': int(len(actual)),
    }


def _save_model(path: Path, model) -> None:
    with path.open('wb') as handle:
        pickle.dump(model, handle)


def _create_charts(output_dir: Path, occupancy: pd.DataFrame, loads: pd.DataFrame,
                   occupancy_metrics: pd.DataFrame, load_metrics: pd.DataFrame,
                   horizon_hours: int) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    def local_time(frame: pd.DataFrame) -> pd.Series:
        return pd.to_datetime(frame['timestamp_utc'], utc=True).dt.tz_convert('Europe/Warsaw').dt.tz_localize(None)

    def first_window(frame: pd.DataFrame, hours: int) -> pd.DataFrame:
        timestamps = frame['timestamp_utc'].drop_duplicates().iloc[:hours]
        return frame[frame['timestamp_utc'].isin(timestamps)].copy()

    def format_time_axis(axis) -> None:
        locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
        axis.xaxis.set_major_locator(locator)
        axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    output_dir.mkdir(parents=True, exist_ok=True)
    horizons = [h for h in (24, 72, 168) if h <= horizon_hours]
    for hours in horizons:
        occ_window = first_window(occupancy, hours)
        fig, ax = plt.subplots(figsize=(16, 5))
        actual_occupancy = occ_window.drop_duplicates('timestamp_utc')
        ax.plot(local_time(actual_occupancy), actual_occupancy['actual_occupancy_mean'],
                color='#202020', linewidth=2.4, label='Actual occupancy')
        for name, group in occ_window.groupby('model_id', sort=False):
            ax.plot(local_time(group), group['occupancy_hat'], color=BRIGHT_COLOURS[name],
                    linewidth=1.35, label=f'Predicted: {name}')
        ax.set(title=f'Occupancy forecast: {hours}-hour horizon',
               ylabel='Residents at home', xlabel='Polish local time')
        ax.set_ylim(-0.1, 4.1)
        ax.grid(alpha=.25)
        ax.legend(ncol=4, loc='upper right')
        format_time_axis(ax)
        fig.tight_layout()
        fig.savefig(output_dir/f'occupancy_forecast_{hours}h.png', dpi=160)
        plt.close(fig)

        load_window = first_window(loads, hours)
        fig, ax = plt.subplots(figsize=(16, 5))
        actual_load = load_window.drop_duplicates('timestamp_utc')
        ax.plot(local_time(actual_load), actual_load['actual_total_kwh'], color='#202020',
                linewidth=2.3, label='Actual total load')
        for name, group in load_window.groupby('model_id', sort=False):
            ax.plot(local_time(group), group['load_hat'], color=BRIGHT_COLOURS[name],
                    linewidth=1.05, label=name.replace('_', ' '))
        ax.set(title=f'Recursive load forecasts: {hours}-hour horizon',
               ylabel='Energy per hour (kWh)', xlabel='Polish local time')
        ax.grid(alpha=.25)
        ax.legend(ncol=3, loc='upper right')
        format_time_axis(ax)
        fig.tight_layout()
        fig.savefig(output_dir/f'load_forecast_{hours}h.png', dpi=160)
        plt.close(fig)

    chart_sections = ''.join(
        f'<h2>Occupancy forecast: {hours} hours</h2><img src="occupancy_forecast_{hours}h.png">'
        f'<h2>Load forecast: {hours} hours</h2><img src="load_forecast_{hours}h.png">'
        for hours in horizons
    )

    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>HackoWatt model benchmark</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;background:#f5f7fb;color:#172033}}h1,h2{{color:#12263f}}img{{max-width:100%;background:white;padding:8px;border-radius:8px;margin:8px 0 28px}}table{{border-collapse:collapse;background:white;margin-bottom:28px}}th,td{{padding:8px 12px;border:1px solid #d8dee9}}th{{background:#12263f;color:white}}</style>
</head><body><h1>Load and occupancy model benchmark</h1><p>All load models use predicted occupancy, calendar flags, weather, and only energy history available before each recursively predicted hour.</p>
<h2>Occupancy metrics</h2>{occupancy_metrics.round(4).to_html(index=False)}
<h2>Load metrics</h2>{load_metrics.round(4).to_html(index=False)}
{chart_sections}</body></html>'''
    (output_dir/'benchmark_dashboard.html').write_text(html, encoding='utf-8')


def run_model_benchmark(hourly_path: Path, output_dir: Path,
                        forecast_start_local: str = '2025-05-01 00:00:00',
                        horizon_hours: int = 168) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Prepare data and compare residual direct and physical-boiler forecasts."""
    prepared = prepare_training_data(hourly_path, output_dir, forecast_start_local, horizon_hours)
    df = load_hourly(hourly_path)
    house = _load_house_parameters(hourly_path)
    base, targets, cutoff = prepared.base_features, prepared.targets, prepared.cutoff
    end = cutoff + len(prepared.test)
    reported_horizons = [h for h in (24, 72, 168) if h <= horizon_hours]
    models_dir = output_dir/'models'; models_dir.mkdir(exist_ok=True)
    occupancy_rows: list[dict] = []
    water_draw_rows: list[dict] = []
    load_rows: list[dict] = []
    occupancy_metric_rows: list[dict] = []
    load_metric_rows: list[dict] = []
    actual_occupancy = targets['occupancy_mean'].to_numpy(float)
    actual_total = targets['total_kwh'].to_numpy(float)

    for algorithm in MODEL_NAMES:
        occupancy_model = _fit_regressor(algorithm, base.iloc[:cutoff].to_numpy(float), actual_occupancy[:cutoff])
        occupancy_hat = np.clip(occupancy_model.predict(base.to_numpy(float)), 0.0, 4.0)
        _save_model(models_dir/f'occupancy_{algorithm}.pkl', occupancy_model)
        occupancy_test = occupancy_hat[cutoff:]
        for horizon in reported_horizons:
            occupancy_metric_rows.append({'model_id': algorithm, 'horizon_hours': horizon,
                                          **_regression_metrics(actual_occupancy[cutoff:cutoff+horizon], occupancy_test[:horizon])})
        for pos, row in enumerate(range(cutoff, end)):
            occupancy_rows.append({
                'timestamp_utc': base.index[row].isoformat(),
                'timestamp_local': base.index[row].tz_convert('Europe/Warsaw').isoformat(),
                'model_id': algorithm,
                'actual_occupancy_mean': actual_occupancy[row],
                'occupancy_hat': occupancy_test[pos],
            })

        direct_x, direct_y = _residual_training_matrix(base, occupancy_hat, actual_total, cutoff)
        direct_model = _fit_regressor(algorithm, direct_x, direct_y)
        _save_model(models_dir/f'direct_{algorithm}.pkl', direct_model)
        direct_hat = _recursive_residual_forecast(direct_model, base, occupancy_hat, actual_total, cutoff, end)
        direct_id = f'direct_{algorithm}'
        for horizon in reported_horizons:
            load_metric_rows.append({'model_id': direct_id, 'architecture': 'direct_residual', 'algorithm': algorithm, 'horizon_hours': horizon,
                                     **_regression_metrics(actual_total[cutoff:cutoff+horizon], direct_hat[:horizon])})

        component_hats: dict[str, np.ndarray] = {}
        for component in ('base_kwh', 'behaviour_kwh'):
            target = targets[component].to_numpy(float)
            x, y = _residual_training_matrix(base, occupancy_hat, target, cutoff)
            model = _fit_regressor(algorithm, x, y)
            _save_model(models_dir/f'modular_{component}_{algorithm}.pkl', model)
            component_hats[component] = _recursive_residual_forecast(model, base, occupancy_hat, target, cutoff, end)
        # Heating responds to the weather regime itself. A weekly energy baseline
        # is unsafe during spring/fall changes, e.g. a cold prior week followed
        # by a warm week with no heating demand.
        heating_target = targets['space_heating_kwh'].to_numpy(float)
        heating_x_train = np.column_stack([base.iloc[:cutoff].to_numpy(float), occupancy_hat[:cutoff]])
        heating_x_future = np.column_stack([base.iloc[cutoff:end].to_numpy(float), occupancy_hat[cutoff:end]])
        heating_model = _fit_regressor(algorithm, heating_x_train, heating_target[:cutoff])
        _save_model(models_dir/f'modular_space_heating_kwh_{algorithm}.pkl', heating_model)
        component_hats['space_heating_kwh'] = np.maximum(0.0, heating_model.predict(heating_x_future))
        draw_hat, event_probability, event_threshold, event_model, volume_model = _forecast_hot_water_draws(
            algorithm, base, occupancy_hat, targets['hot_water_mixed_l'].to_numpy(float), cutoff, end)
        _save_model(models_dir/f'hot_water_event_{algorithm}.pkl', event_model)
        _save_model(models_dir/f'hot_water_volume_{algorithm}.pkl', volume_model)
        component_hats['water_heater_kwh'], tank_hat = _simulate_boiler_from_draw_forecast(draw_hat, df, cutoff, house)
        modular_hat = sum(component_hats.values())
        modular_id = f'modular_{algorithm}'
        for horizon in reported_horizons:
            load_metric_rows.append({'model_id': modular_id, 'architecture': 'modular_physical_boiler', 'algorithm': algorithm, 'horizon_hours': horizon,
                                     **_regression_metrics(actual_total[cutoff:cutoff+horizon], modular_hat[:horizon])})

        for pos, row in enumerate(range(cutoff, end)):
            common = {
                'timestamp_utc': base.index[row].isoformat(),
                'timestamp_local': base.index[row].tz_convert('Europe/Warsaw').isoformat(),
                'actual_total_kwh': actual_total[row],
            }
            load_rows.append({**common, 'model_id': direct_id, 'load_hat': direct_hat[pos],
                              'base_hat': np.nan, 'behaviour_hat': np.nan, 'space_heating_hat': np.nan,
                              'water_heater_hat': np.nan, 'water_draw_hat_l': np.nan, 'tank_hat_c': np.nan})
            load_rows.append({**common, 'model_id': modular_id, 'load_hat': modular_hat[pos],
                              'base_hat': component_hats['base_kwh'][pos],
                              'behaviour_hat': component_hats['behaviour_kwh'][pos],
                              'space_heating_hat': component_hats['space_heating_kwh'][pos],
                              'water_heater_hat': component_hats['water_heater_kwh'][pos],
                              'water_draw_hat_l': draw_hat[pos], 'tank_hat_c': tank_hat[pos]})
            water_draw_rows.append({
                'timestamp_utc': base.index[row].isoformat(),
                'timestamp_local': base.index[row].tz_convert('Europe/Warsaw').isoformat(),
                'model_id': algorithm,
                'actual_hot_water_mixed_l': targets['hot_water_mixed_l'].iloc[row],
                'event_probability': event_probability[pos],
                'event_threshold': event_threshold,
                'hot_water_draw_hat_l': draw_hat[pos],
                'tank_hat_c': tank_hat[pos],
                'actual_water_heater_kwh': targets['water_heater_kwh'].iloc[row],
                'water_heater_hat_kwh': component_hats['water_heater_kwh'][pos],
            })

    occupancy_predictions = pd.DataFrame(occupancy_rows)
    water_draw_predictions = pd.DataFrame(water_draw_rows)
    load_predictions = pd.DataFrame(load_rows)
    occupancy_metrics = pd.DataFrame(occupancy_metric_rows)
    load_metrics = pd.DataFrame(load_metric_rows).sort_values(['horizon_hours', 'architecture', 'mae']).reset_index(drop=True)
    occupancy_predictions.to_csv(output_dir/'occupancy_predictions.csv', index=False, float_format='%.6f')
    water_draw_predictions.to_csv(output_dir/'hot_water_draw_predictions.csv', index=False, float_format='%.6f')
    load_predictions.to_csv(output_dir/'load_predictions.csv', index=False, float_format='%.6f')
    occupancy_metrics.to_csv(output_dir/'occupancy_metrics.csv', index=False, float_format='%.6f')
    load_metrics.to_csv(output_dir/'load_metrics.csv', index=False, float_format='%.6f')
    _create_charts(output_dir, occupancy_predictions, load_predictions, occupancy_metrics, load_metrics, horizon_hours)
    spec = {
        **prepared.manifest,
        'occupancy_models': list(MODEL_NAMES),
        'load_models': [f'{architecture}_{algorithm}' for architecture in ('direct_residual', 'modular_physical_boiler') for algorithm in MODEL_NAMES],
        'load_features': list(base.columns) + ['occupancy_hat'] + list(LAG_NAMES),
        'direct_model_rule': 'Predict the correction to the observed same hour one week earlier, then add that weekly baseline.',
        'modular_rule': 'Base and behaviour are weekly-residual models. Space heating is a direct weather-response model. The boiler is simulated from thresholded hot-water event probability/volume, the observed same hour one week earlier, and the observed tank state before forecast issue.',
        'boiler_initial_state_rule': 'Uses only tank_c and water_heater_kwh observed at forecast issue; no future tank state, draw, or occupancy is used.',
        'recursive_test_policy': 'At every forecast hour, load lags and rolling means are calculated from earlier predictions, never later actual demand.',
        'forecast_start_local': prepared.manifest['forecast_start_local'],
        'max_forecast_horizon_hours': horizon_hours,
        'reported_horizons_hours': reported_horizons,
        'modular_targets': ['base_kwh', 'behaviour_kwh', 'space_heating_kwh', 'hot_water_mixed_l -> physical water_heater_kwh'],
    }
    (output_dir/'benchmark_spec.json').write_text(json.dumps(spec, indent=2), encoding='utf-8')
    return occupancy_metrics, load_metrics, spec
