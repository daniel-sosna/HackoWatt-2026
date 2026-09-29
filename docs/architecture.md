# Application structure

HackoWatt is one local Python application with static JSON and CSV files as its
only source of household data. `main.py` is the canonical command entry point;
the local web dashboard is a presentation adapter, not a second pipeline.

```text
config/default.json + data/raw/*.csv
              |
              v
data/ + config/ -----> weather/CsvWeatherProvider
              |                    |
              +--------------------+
                                   v
                  simulation/ (behaviour, devices, thermal, profile)
                                   |
                                   v
                       results/<run>/*.csv
                         |        |       |
                         v        v       v
                   forecasting/ analysis/ renewable/ + optimisation/
                         \        |       /
                          \       |      /
                           services/ (orchestration and view models)
                                      |
                                      v
                  web.py (native HTML + JSON endpoints) and CLI components/
```

## Package responsibilities

| Package | Responsibility |
| --- | --- |
| `config` | Project paths and configuration conventions. |
| `data` | JSON/CSV parsing, validation, and repositories for generated/forecast artifacts. |
| `domain` | Small shared result objects only where they improve the service boundary. |
| `weather` | Provider contract and the current static CSV provider. |
| `simulation` | Behaviour, appliances, thermal model, and hourly profile export. |
| `forecasting` | Leakage-safe issue-date feature preparation and selected Random Forest/CatBoost models. |
| `analysis` | Downstream peak analysis. |
| `optimisation` | Conservative flexible-load recommendations; it does not change demand. |
| `renewable` | PV energy-flow and economic calculations. |
| `services` | Thin use cases that join data/providers and domain modules. |
| `components` | CLI argument adapters only. |
| `presentation` | Dashboard renderers and visual assets, with no business rules. |
| `web` | Local HTTP adapter: native dashboard views and narrowly-scoped API endpoints. |

Business packages do not import web/UI packages. The dashboard calls
`DashboardService`; `POST /api/issue-date-forecast` calls the public
`hackowatt.issue_date_forecast` boundary; commands call `generate_historical`
or that same public forecast API.
This keeps new weather providers, models, analysis, and dashboard views local to
their own package.

## Running the application

```bash
python main.py generate
python main.py issue-date-forecast --forecast-start-local "2025-09-10 00:00:00"
python main.py dashboard
```

`dashboard` starts a local FastAPI/Uvicorn server and accepts `--input` and an
optional `--port`. The dashboard has polished interactive Historical profile,
issue-date Forecast, and PV planning views backed by the same generated dataset.
The richer HTML/CSS/JavaScript visualisations live in
`presentation/assets` and are pure renderers: services supply DataFrames and
small view models, while the browser only hosts the rendered interface.

Standalone dashboard commands and compatibility facades have been removed. The
retained visual assets are embedded by the unified dashboard rather than forming
another pipeline. New features must target the packages above and the unified
dashboard.

## Extending a capability

1. Put new business logic in its owning package, with no web/UI dependency.
2. Add/extend a small service if the feature joins multiple packages or files.
3. Add one UI view/control or one CLI component that invokes the service.
4. Add a focused contract/model test only when business logic changed.

For example, a real weather provider implements `WeatherProvider`; the
generation service can receive it without changing the simulation. A new
forecast model belongs in `forecasting` and is selected through the public
issue-date contract without changing the dashboard or its caller.
