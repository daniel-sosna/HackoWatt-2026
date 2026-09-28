# Issue-date forecast API

`hackowatt.issue_date_forecast` is the stable Python integration boundary for
an application that lets a user select a forecast start date.

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

## Command-line use

```powershell
.venv\Scripts\python.exe main.py issue-date-forecast `
  --input results/default/hourly.csv `
  --forecast-start-local "2025-09-10 00:00:00" `
  --horizon-hours 72 `
  --output results/issue_date_forecast
```

The command writes `forecast.csv`, `backtest_actual.csv`, and `manifest.json`.
It does not alter `hourly.csv`.

## Current data boundary

The bundled historical dataset is used as a backtest: it must contain the
selected issue date, at least 168 preceding hours, and all requested future
hours. Weather and calendar columns for these future rows are treated as known
inputs. A live version must supply issued weather and calendar values for the
future horizon while withholding future measured energy, occupancy, tank
temperature, and appliance values.
