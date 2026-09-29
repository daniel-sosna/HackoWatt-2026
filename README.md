# HackoWatt Family

A local Python project for PyCharm Community Edition. It generates a synthetic
hourly electricity profile for a four-person family in Silesia and provides one
configurable load-forecast model.

The repository contains only four product capabilities:

- synthetic household-data generation;
- a local dashboard for checking generated data;
- a forecast from a manually selected Polish local issue date;
- editable rules, source material, configuration, and documentation.

## PyCharm workflow

1. Open `config/default.json` to set or override house parameters.
2. Run `main.py` with the `generate` parameter. This writes the generated data
   to `results/default/`.
3. Optionally run `main.py` with the `dashboard` parameter and open
   `results/default/dashboard.html` to inspect appliances, occupancy, thermal
   state, and validation diagnostics.
4. Open `run_issue_date_forecast.py`, edit its date and horizon settings, then
   run that file directly. The forecast is written to
   `results/issue_date_forecast/`.

## Command-line equivalents

```powershell
.venv\Scripts\python.exe main.py generate
.venv\Scripts\python.exe main.py dashboard
.venv\Scripts\python.exe run_issue_date_forecast.py
```

`main.py issue-date-forecast` is available for developers who prefer explicit
arguments. Its public request/response contract is documented in
`docs/issue_date_forecast_api.md`.

## Generated data

`results/default/hourly.csv` is the canonical model input. It contains weather,
calendar flags, occupancy, appliance loads, direct electric space heating,
electric-boiler load, temperatures, and whole-home energy. The detailed column
dictionary is `docs/hourly_data_dictionary.md`.

Observed weather is loaded from `data/raw/katowice_weather_2024_today.csv`.
The generator uses every continuous hourly observation in that file, currently
covering 2024 through its latest supplied timestamp. The original source files remain unchanged under `data/raw/`. Generated files
under `results/` are intentionally ignored by Git.

## Forecast model

The date runner retrains strictly on rows before `FORECAST_START_LOCAL` and
accepts only 24, 72, or 168 hours. It uses Direct Random Forest for 24 hours
and Modular CatBoost for 72 or 168 hours. It writes:

- `forecast.csv` with the selected forecast and predicted occupancy;
- `backtest_actual.csv` separately for historical evaluation;
- `forecast_vs_actual.png` with actual and predicted load on one chart;
- `manifest.json` with the issue time, training-row count, model policy, and
  error metrics.

The runner reads `data/raw/katowice_weather_forecast.csv` as issued weather for
the future feature rows. It retains observed weather for training. Change
`FORECAST_WEATHER_CSV` in `run_issue_date_forecast.py` if a newer issued forecast is available.

The bundled dataset supports historical backtests. A live deployment must
provide issued weather and calendar values for future hours while withholding
future measured load, occupancy, and thermal state.

## Rules and documentation

The editable household rules are in `docs/rules_v3.md`; the visual review copy
is `docs/rules_v3.pdf`. Rebuild it after editing with:

```powershell
.venv\Scripts\python.exe tools\build_rules.py
```

`docs/architecture.md` describes the retained components. Organiser materials
are retained in `docs/` as immutable source references.
