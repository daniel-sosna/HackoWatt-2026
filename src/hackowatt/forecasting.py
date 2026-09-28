"""Two leakage-safe, recursive hourly forecasting architectures.

Option A follows the supplied brief: base + behaviour + thermal components.
Option B is a direct total-load model.  The tree learner is implemented with
NumPy so the project has no undeclared CatBoost/LightGBM dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd

BASE_COLUMNS = ['fridge_kwh', 'router_kwh', 'standby_kwh']
THERMAL_COLUMNS = ['space_heating_kwh', 'water_heater_kwh']
FORBIDDEN_DIRECT_COLUMNS = {
    'total_kwh', 'mean_kw', 'peak_1min_kw', 'occupancy_mean',
    'awake_at_home_mean', 'indoor_c', 'indoor_min_c', 'indoor_max_c',
    'tank_c', 'tank_min_c', 'setpoint_c', 'internal_gain_kw',
    'hot_water_mixed_l', *BASE_COLUMNS, *THERMAL_COLUMNS,
}


class HistogramBoostingRegressor:
    """Small squared-error gradient-boosted decision-stump regressor.

    It is intentionally transparent and serialisable. It is not presented as
    a replacement for CatBoost/LightGBM when those libraries are available.
    """
    def __init__(self, n_estimators=160, learning_rate=0.07, n_bins=24,
                 min_samples_leaf=48, l2=8.0, clip_nonnegative=True):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.n_bins = n_bins
        self.min_samples_leaf = min_samples_leaf
        self.l2 = l2
        self.clip_nonnegative = clip_nonnegative

    def fit(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        if x.ndim != 2 or len(x) != len(y) or len(y) == 0:
            raise ValueError('Expected nonempty aligned two-dimensional features and target')
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError('Training data contains nonfinite values')
        self.bias_ = float(np.mean(y))
        self.edges_ = []
        bins = []
        grid = np.linspace(0, 1, self.n_bins + 1)[1:-1]
        for j in range(x.shape[1]):
            edge = np.unique(np.quantile(x[:, j], grid))
            self.edges_.append(edge)
            bins.append(np.searchsorted(edge, x[:, j], side='right'))
        self.bin_counts_ = [len(edge) + 1 for edge in self.edges_]
        prediction = np.full(len(y), self.bias_)
        self.stumps_ = []
        for _ in range(self.n_estimators):
            residual = y - prediction
            best = None
            for j, b in enumerate(bins):
                count = self.bin_counts_[j]
                n = np.bincount(b, minlength=count).astype(float)
                s = np.bincount(b, weights=residual, minlength=count)
                n_left = np.cumsum(n)[:-1]
                n_right = n.sum() - n_left
                s_left = np.cumsum(s)[:-1]
                s_right = s.sum() - s_left
                valid = (n_left >= self.min_samples_leaf) & (n_right >= self.min_samples_leaf)
                if not valid.any():
                    continue
                gain = s_left**2/(n_left+self.l2) + s_right**2/(n_right+self.l2)
                gain[~valid] = -np.inf
                split = int(np.argmax(gain))
                candidate = float(gain[split])
                if best is None or candidate > best[0]:
                    best = (candidate, j, split, n_left[split], n_right[split],
                            s_left[split], s_right[split])
            if best is None or best[0] <= 1e-10:
                break
            _, j, split, n_l, n_r, s_l, s_r = best
            left = self.learning_rate * s_l/(n_l+self.l2)
            right = self.learning_rate * s_r/(n_r+self.l2)
            mask = bins[j] <= split
            prediction[mask] += left
            prediction[~mask] += right
            self.stumps_.append((j, float(self.edges_[j][split]), float(left), float(right)))
        return self

    def predict(self, x):
        x = np.asarray(x, dtype=float)
        result = np.full(len(x), self.bias_)
        for j, threshold, left, right in self.stumps_:
            result += np.where(x[:, j] <= threshold, left, right)
        return np.maximum(result, 0.0) if self.clip_nonnegative else result

    def state(self):
        return {'bias': self.bias_, 'stumps': self.stumps_, 'n_estimators': self.n_estimators,
                'learning_rate': self.learning_rate, 'n_bins': self.n_bins,
                'min_samples_leaf': self.min_samples_leaf, 'l2': self.l2,
                'clip_nonnegative': self.clip_nonnegative}


def load_hourly(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    utc = pd.to_datetime(df['timestamp_utc'], utc=True, errors='raise')
    if not utc.is_monotonic_increasing or utc.duplicated().any():
        raise ValueError('hourly.csv must have sorted unique UTC timestamps')
    if not (utc.diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError('hourly.csv must be continuous at hourly UTC frequency')
    df.index = utc
    return df


def exogenous_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Features known at forecast issue time, excluding simulated future state."""
    local = df.index.tz_convert('Europe/Warsaw')
    hour = local.hour.to_numpy()
    dow = local.dayofweek.to_numpy()
    doy = local.dayofyear.to_numpy()
    shift = df['marek_shift'].astype(str)
    result = pd.DataFrame(index=df.index)
    result['hour_sin'] = np.sin(2*np.pi*hour/24)
    result['hour_cos'] = np.cos(2*np.pi*hour/24)
    result['weekday_sin'] = np.sin(2*np.pi*dow/7)
    result['weekday_cos'] = np.cos(2*np.pi*dow/7)
    result['year_sin'] = np.sin(2*np.pi*doy/365.25)
    result['year_cos'] = np.cos(2*np.pi*doy/365.25)
    result['is_weekend'] = (dow >= 5).astype(float)
    for name in ['temperature_2m', 'cloud_cover', 'relative_humidity_2m', 'wind_speed_10m',
                 'precipitation', 'snowfall', 'shortwave_radiation_instant',
                 'public_holiday', 'school_break', 'school_day', 'ania_wfh']:
        result[name] = pd.to_numeric(df[name], errors='raise').astype(float)
    result['heating_degree_c'] = np.maximum(0, 18 - result['temperature_2m'])
    for name in ['morning', 'evening', 'night', 'off']:
        result['shift_'+name] = (shift == name).astype(float)
    if set(result.columns) & FORBIDDEN_DIRECT_COLUMNS:
        raise AssertionError('Future-state/target leakage in exogenous feature frame')
    return result


LAG_NAMES = ('lag_1', 'lag_24', 'lag_168', 'mean_24', 'mean_168')


def history_vector(history: list[float]) -> list[float]:
    if len(history) < 168:
        raise ValueError('168 hours of history are required')
    return [history[-1], history[-24], history[-168],
            float(np.mean(history[-24:])), float(np.mean(history[-168:]))]


@dataclass
class ComponentModel:
    feature_names: list[str]
    regressor: HistogramBoostingRegressor

    def fit(self, exog: pd.DataFrame, target: np.ndarray, end: int):
        rows = np.arange(168, end)
        x = np.column_stack([exog.iloc[rows].to_numpy(float),
                             np.asarray([history_vector(target[:i].tolist()) for i in rows])])
        # The direct/recursive forecast is a weather- and calendar-adjusted
        # seasonal-naive forecast.  This preserves the weekly household rhythm
        # instead of allowing a multi-day recursive forecast to collapse to a
        # global mean.
        self.regressor.clip_nonnegative = False
        self.regressor.fit(x, target[rows]-target[rows-168])
        return self

    def forecast_one(self, exog_row: np.ndarray, history: list[float]) -> float:
        x = np.asarray([np.r_[exog_row, history_vector(history)]])
        return max(0.0, float(history[-168] + self.regressor.predict(x)[0]))


@dataclass
class DirectForecast:
    model: ComponentModel

    @classmethod
    def fit(cls, exog, total, end):
        names = list(exog.columns) + list(LAG_NAMES)
        return cls(ComponentModel(names, HistogramBoostingRegressor()).fit(exog, total, end))

    def forecast(self, exog, total_history, origin, horizon):
        history = list(np.asarray(total_history[:origin], dtype=float))
        values = []
        for i in range(origin, origin+horizon):
            value = self.model.forecast_one(exog.iloc[i].to_numpy(float), history)
            values.append(value)
            history.append(value)
        return np.asarray(values)


@dataclass
class ModularForecast:
    base_by_hour: np.ndarray
    behaviour: ComponentModel
    space_heating: ComponentModel
    water_heater: ComponentModel

    @classmethod
    def fit(cls, exog, df, end):
        local_hour = exog.index.tz_convert('Europe/Warsaw').hour
        base = df[BASE_COLUMNS].sum(axis=1).to_numpy(float)
        behaviour_cols = [c for c in df if c.endswith('_kwh') and c not in
                          set(BASE_COLUMNS+THERMAL_COLUMNS+['total_kwh','hot_water_unmet_kwh','thermal_residual_kwh'])]
        behaviour = df[behaviour_cols].sum(axis=1).to_numpy(float)
        space = df['space_heating_kwh'].to_numpy(float)
        water = df['water_heater_kwh'].to_numpy(float)
        profile = np.asarray([base[:end][local_hour[:end] == hour].mean() for hour in range(24)])
        names = list(exog.columns) + list(LAG_NAMES)
        return cls(profile,
                   ComponentModel(names, HistogramBoostingRegressor()).fit(exog, behaviour, end),
                   ComponentModel(names, HistogramBoostingRegressor()).fit(exog, space, end),
                   ComponentModel(names, HistogramBoostingRegressor()).fit(exog, water, end))

    def forecast(self, exog, df, origin, horizon):
        local_hour = exog.index.tz_convert('Europe/Warsaw').hour
        behaviour_history = list(df['_behaviour_target'].iloc[:origin])
        space_history = list(df['space_heating_kwh'].iloc[:origin])
        water_history = list(df['water_heater_kwh'].iloc[:origin])
        components = {'base_hat': [], 'behaviour_hat': [], 'space_heating_hat': [], 'water_heater_hat': []}
        for i in range(origin, origin+horizon):
            x = exog.iloc[i].to_numpy(float)
            b = self.behaviour.forecast_one(x, behaviour_history)
            s = self.space_heating.forecast_one(x, space_history)
            w = self.water_heater.forecast_one(x, water_history)
            base = float(self.base_by_hour[local_hour[i]])
            components['base_hat'].append(base); components['behaviour_hat'].append(b)
            components['space_heating_hat'].append(s); components['water_heater_hat'].append(w)
            behaviour_history.append(b); space_history.append(s); water_history.append(w)
        result = {k: np.asarray(v) for k, v in components.items()}
        result['thermal_hat'] = result['space_heating_hat'] + result['water_heater_hat']
        result['load_hat'] = result['base_hat'] + result['behaviour_hat'] + result['thermal_hat']
        return result


def seasonal_naive(total: np.ndarray, origin: int, horizon: int) -> np.ndarray:
    if origin < 168:
        raise ValueError('Seasonal baseline requires 168 history hours')
    return total[origin-168:origin-168+horizon].copy()


def metrics(actual: np.ndarray, prediction: np.ndarray) -> dict:
    """Metrics over a matrix with one row per forecast origin."""
    if actual.shape != prediction.shape or actual.ndim != 2:
        raise ValueError('Expected matching forecast-origin by horizon matrices')
    mask = np.isfinite(actual) & np.isfinite(prediction)
    a, p = actual[mask], prediction[mask]
    values = {'mae_kwh': float(np.mean(np.abs(p-a))),
              'rmse_kwh': float(np.sqrt(np.mean((p-a)**2))),
              'wape_pct': float(100*np.abs(p-a).sum()/a.sum()),
              'total_error_pct': float(100*(p.sum()-a.sum())/a.sum())}
    peak_errors=[]; timing_errors=[]
    for aa, pp in zip(actual, prediction):
        peak_errors.append(abs(pp[int(np.argmax(aa))] - aa.max()))
        timing_errors.append(abs(int(np.argmax(pp))-int(np.argmax(aa))))
    values['peak_hour_mae_kwh'] = float(np.mean(peak_errors))
    values['peak_timing_mae_h'] = float(np.mean(timing_errors))
    values['n_hours'] = int(len(a)); values['n_forecasts'] = int(len(actual)); values['horizon_hours'] = int(actual.shape[1])
    return values


def run_forecast_experiment(hourly_path: Path, output_dir: Path, test_days=90, origin_stride_h=168):
    df = load_hourly(hourly_path).copy()
    exog = exogenous_frame(df)
    total = df['total_kwh'].to_numpy(float)
    behaviour_cols = [c for c in df if c.endswith('_kwh') and c not in
                      set(BASE_COLUMNS+THERMAL_COLUMNS+['total_kwh','hot_water_unmet_kwh','thermal_residual_kwh'])]
    df['_behaviour_target'] = df[behaviour_cols].sum(axis=1)
    n = len(df); cutoff = n-test_days*24
    if cutoff <= 168 or n-cutoff < 168:
        raise ValueError('Need 168 history hours and 168 holdout hours')
    direct = DirectForecast.fit(exog, total, cutoff)
    modular = ModularForecast.fit(exog, df, cutoff)
    origins = list(range(cutoff, n-168+1, origin_stride_h))
    rows=[]
    for origin in origins:
        actual = total[origin:origin+168]
        naive = seasonal_naive(total, origin, 168)
        direct_hat = direct.forecast(exog, total, origin, 168)
        modular_hat = modular.forecast(exog, df, origin, 168)
        for model_id, values in [('seasonal_naive', {'load_hat': naive}),
                                 ('direct_total_gbdt', {'load_hat': direct_hat}),
                                 ('modular_component_gbdt', modular_hat)]:
            for h in range(168):
                row = {'origin_utc': df.index[origin].isoformat(),
                       'timestamp_utc': df.index[origin+h].isoformat(), 'horizon_h': h+1,
                       'model_id': model_id, 'actual_kwh': actual[h], 'load_hat': values['load_hat'][h]}
                for key in ['base_hat','behaviour_hat','thermal_hat','space_heating_hat','water_heater_hat']:
                    row[key] = values.get(key, np.nan if isinstance(values,dict) else np.nan)
                    if isinstance(row[key], np.ndarray): row[key] = row[key][h]
                rows.append(row)
    predictions = pd.DataFrame(rows)
    metric_rows=[]
    for model_id, group in predictions.groupby('model_id'):
        pivot = group.pivot(index='origin_utc', columns='horizon_h', values=['actual_kwh','load_hat']).sort_index(axis=1)
        actual_matrix = pivot['actual_kwh'].to_numpy(); pred_matrix = pivot['load_hat'].to_numpy()
        for name, slc in [('hours_1_24',slice(0,24)),('hours_25_72',slice(24,72)),('hours_73_168',slice(72,168)),('hours_1_168',slice(0,168))]:
            m = metrics(actual_matrix[:,slc], pred_matrix[:,slc])
            metric_rows.append({'model_id':model_id,'bucket':name,**m})
    metrics_df=pd.DataFrame(metric_rows)
    output_dir.mkdir(parents=True,exist_ok=True)
    predictions.to_csv(output_dir/'forecast_predictions.csv',index=False,float_format='%.6f')
    metrics_df.to_csv(output_dir/'forecast_metrics.csv',index=False,float_format='%.6f')
    feature_doc={'architecture_A':'base_hat + behaviour_hat + thermal_hat; base is a deterministic hourly profile, the other components use recursive histogram-boosted decision stumps.',
                 'architecture_B':'recursive direct total-load histogram-boosted decision-stump model.',
                 'feature_columns':list(exog.columns)+list(LAG_NAMES),
                 'excluded_for_leakage':sorted(FORBIDDEN_DIRECT_COLUMNS),
                 'train_end_utc':df.index[cutoff-1].isoformat(), 'test_start_utc':df.index[cutoff].isoformat(),
                 'test_end_utc':df.index[-1].isoformat(), 'test_days':test_days,
                 'origin_stride_hours':origin_stride_h, 'origins':len(origins), 'max_horizon_hours':168,
                 'weather_assumption':'Validation uses recorded weather as a perfect forecast. Replace with archived issued forecasts for a production score.',
                 'submeter_requirement':'Modular behaviour, space-heating and water-heater lags require their corresponding real sub-meters after deployment.',
                 'direct_model_state':direct.model.regressor.state(),
                 'modular_model_state':{'behaviour':modular.behaviour.regressor.state(),'space_heating':modular.space_heating.regressor.state(),
                                        'water_heater':modular.water_heater.regressor.state(),'base_by_hour':modular.base_by_hour.tolist()}}
    (output_dir/'forecast_model_spec.json').write_text(json.dumps(feature_doc,indent=2),encoding='utf-8')
    return predictions,metrics_df,feature_doc
