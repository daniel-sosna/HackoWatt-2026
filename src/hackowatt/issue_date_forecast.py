"""Portable issue-date forecasting API.

This module is the integration boundary for applications that need to ask for
a forecast at a user-selected Polish local date. It trains only on preceding
rows, selects the approved model for the requested horizon, and returns an
in-memory result. The source ``hourly.csv`` is never modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import tempfile

import pandas as pd

from .forecasting.issue_date import SELECTED_MODELS, run_selected_model


@dataclass(frozen=True)
class ForecastRequest:
    """Inputs required for one forecast issued at a manually selected date."""

    hourly_path: Path
    forecast_start_local: str
    horizon_hours: int = 24
    forecast_weather_path: Path | None = None


@dataclass
class ForecastResult:
    """In-memory response returned to another Python application."""

    forecast: pd.DataFrame
    backtest_actual: pd.Series
    model_id: str
    manifest: dict


def selected_model_for_horizon(horizon_hours: int) -> str:
    """Return the approved model identifier for an exact supported horizon."""
    try:
        return SELECTED_MODELS[horizon_hours]
    except KeyError as error:
        raise ValueError('horizon_hours must be exactly 24, 72, or 168') from error


def forecast_from_issue_date(request: ForecastRequest) -> ForecastResult:
    """Train through ``forecast_start_local`` and return one selected forecast.

    ``hourly_path`` must contain a continuous hourly history, at least 168
    hours before the issue time, and the requested horizon after it. The latter
    condition makes this API an honest historical backtest today. A future
    live run needs issued weather/calendar rows for the requested horizon and
    is deliberately not filled with future measured load.
    """
    hourly_path = Path(request.hourly_path)
    if not hourly_path.is_file():
        raise FileNotFoundError(f'Hourly data file was not found: {hourly_path}')
    model_id = selected_model_for_horizon(request.horizon_hours)

    # The benchmark owns feature creation, recursive lag handling, occupancy
    # prediction, and boiler simulation. Its temporary files stay private.
    with tempfile.TemporaryDirectory(prefix='hackowatt_issue_date_') as directory:
        work_dir = Path(directory)
        _, load_metrics, spec = run_selected_model(
            hourly_path, work_dir, request.forecast_start_local, horizon_hours=request.horizon_hours,
            forecast_weather_path=request.forecast_weather_path)
        loads = pd.read_csv(work_dir/'load_predictions.csv')
        occupancy = pd.read_csv(work_dir/'occupancy_predictions.csv')

        selected = loads.loc[loads['model_id'].eq(model_id)].head(request.horizon_hours).copy()
        if len(selected) != request.horizon_hours:
            raise RuntimeError('Selected model did not return every requested forecast hour')
        occupancy_model = 'random_forest' if model_id == 'direct_random_forest' else 'catboost'
        occupancy_hat = occupancy.loc[occupancy['model_id'].eq(occupancy_model), 'occupancy_hat']
        selected.insert(4, 'occupancy_hat', occupancy_hat.head(request.horizon_hours).to_numpy())

        actual = selected.pop('actual_total_kwh').rename('actual_total_kwh')
        selected = selected.rename(columns={'load_hat': 'forecast_kwh'})
        metric = load_metrics.loc[
            load_metrics['model_id'].eq(model_id) &
            load_metrics['horizon_hours'].eq(request.horizon_hours)
        ].iloc[0].to_dict()

    manifest = {
        'forecast_start_local': spec['forecast_start_local'],
        'horizon_hours': request.horizon_hours,
        'model_id': model_id,
        'training_ends_before_forecast': True,
        'training_rows': spec['rows_train'],
        'forecast_weather_source': spec['forecast_weather_source'],
        'selection_policy': {str(hours): model for hours, model in SELECTED_MODELS.items()},
        'load_feature_rule': spec['load_feature_rule'],
        'recursive_test_policy': spec['recursive_test_policy'],
        'metric': metric,
    }
    return ForecastResult(selected.reset_index(drop=True), actual.reset_index(drop=True), model_id, manifest)


def write_issue_date_forecast(result: ForecastResult, output_dir: Path) -> None:
    """Persist the portable API response without changing the source data."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result.forecast.to_csv(output_dir/'forecast.csv', index=False, float_format='%.6f')
    result.backtest_actual.to_frame().to_csv(output_dir/'backtest_actual.csv', index=False, float_format='%.6f')
    (output_dir/'manifest.json').write_text(json.dumps(result.manifest, indent=2), encoding='utf-8')
    _write_comparison_chart(result, output_dir/'forecast_vs_actual.png')


def _write_comparison_chart(result: ForecastResult, target: Path) -> None:
    """Render the historical backtest comparison in a directly shareable PNG."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    timestamps = pd.to_datetime(result.forecast['timestamp_local'])
    fig, axis = plt.subplots(figsize=(15, 5.5))
    axis.plot(timestamps, result.backtest_actual, color='#151515', linewidth=2.5,
              label='Actual load')
    forecast_colour = '#FF006E' if result.model_id == 'direct_random_forest' else '#3A86FF'
    axis.plot(timestamps, result.forecast['forecast_kwh'], color=forecast_colour,
              linewidth=2.0, label=f"Forecast: {result.model_id.replace('_', ' ')}")
    axis.set(
        title=f"Actual and forecast load: {result.manifest['horizon_hours']}-hour horizon",
        xlabel='Polish local time',
        ylabel='Energy per hour (kWh)',
    )
    axis.grid(alpha=0.25)
    axis.legend(loc='upper right')
    locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    fig.tight_layout()
    fig.savefig(target, dpi=160)
    plt.close(fig)
