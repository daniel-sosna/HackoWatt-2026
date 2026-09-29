# Issue-date forecast API

`hackowatt.issue_date_forecast` is the stable Python integration boundary for
an application that lets a user select a forecast start date. Its internal
training code is `hackowatt.forecasting.issue_date`; applications should call the
public API rather than import that implementation module.

For every call, it trains on rows strictly earlier than the requested Polish
local issue time, forecasts the requested exact horizon, and uses the approved
model policy:

| Horizon | Model |
|---:|---|
| 24 hours | Direct Random Forest |
| 72 hours | Modular CatBoost |
| 168 hours | Modular CatBoost |

## Python integration

```python
from pathlib import Path

from hackowatt.issue_date_forecast import ForecastRequest, forecast_from_issue_date

request = ForecastRequest(
    hourly_path=Path("data/hourly.csv"),
    forecast_start_local="2025-09-10 00:00:00",
    horizon_hours=72,
    forecast_weather_path=Path("data/raw/katowice_weather_forecast.csv"),
)
result = forecast_from_issue_date(request)
payload = result.forecast.to_dict(orient="records")
```

`result.forecast` contains timestamps, the chosen model identifier,
`forecast_kwh`, `occupancy_hat`, and modular component estimates where the
chosen architecture supplies them. `result.manifest` records the issue time,
model policy, training row count, recursive-lag policy, and backtest metric.
`result.backtest_actual` is separate so an application cannot accidentally use
future actual load as a forecast feature.

When `forecast_weather_path` is supplied, its issued weather replaces only the
future weather feature rows. Training rows always retain observed weather. The
file must cover the requested future horizon. Missing precipitation in the
current forecast source is explicitly represented as zero.

## Command-line use

```powershell
.venv\Scripts\python.exe main.py issue-date-forecast `
  --input results/default/hourly.csv `
  --forecast-start-local "2025-09-10 00:00:00" `
  --horizon-hours 72 `
  --forecast-weather data/raw/katowice_weather_forecast.csv `
  --output results/issue_date_forecast
```

The command writes `forecast.csv`, `backtest_actual.csv`, `manifest.json`, and
`forecast_vs_actual.png`. The PNG compares actual and predicted load with
clearly different colours. It does not alter `hourly.csv`.

## PyCharm one-file runner

For a workflow without command-line parameters, open
`tools/run_issue_date_forecast.py`. Change
`FORECAST_START_LOCAL` and `HORIZON_HOURS` in the clearly marked settings
block, then right-click the file in PyCharm and choose **Run**. It writes the
same three output files as the command-line adapter.

## Current data boundary

The bundled generated dataset is used as a backtest: it must contain the
selected issue date, at least 168 preceding hours, and all requested future
hours. Calendar values are treated as known inputs. Supply an issued weather
file for the future horizon; otherwise the generated weather columns are used.
For a live version, withhold future measured energy, occupancy, tank
temperature, and appliance values.
