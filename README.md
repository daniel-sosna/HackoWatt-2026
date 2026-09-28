# HackoWatt Family

A local Python project for PyCharm Community Edition. It simulates a four-person family, appliances, direct electric space heating, and a separate electric boiler. Weather, Eurostat time-use data, and calendars are included. The scope excludes PV, batteries, grid export, and other electricity generation.

## Quick start

Create and activate a Python 3.11+ virtual environment from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Use `requirements.txt` for normal development and runtime installs. Use `requirements-tested.txt` instead when reproducing the exact dependency versions used by the retained validation checks. On Windows, activate with `.venv\\Scripts\\activate`.

Run `main.py` with the required component. Generation dates come from the weather file and are not set separately. After running `dashboard`, open `results/default/dashboard.html`; no server or internet connection is required.

```bash
python main.py generate
python main.py dashboard
python main.py forecast
python main.py forecast-dashboard
python -m unittest discover -s tests -v
```

A generated example is already available in `results/default`. It contains 17,544 physical hours for local calendar years 2024--2025, including 29 February.

## House parameters

Edit `config/default.json`. `house.mode = "sample"` draws only fields that have a distribution definition, once for the whole house; the drawn values remain fixed. `house.overrides` always takes priority:

```json
"overrides": {
  "floor_area_m2": 140,
  "heating_capacity_kw": 8,
  "tank_volume_l": 150
}
```

This is an input example, not a capacity recommendation. The default 3.5 kW capacity preserves the organiser example's upper bound and may be insufficient for a complete house. The model does not artificially force indoor temperature to the setpoint: inadequate heating appears as a comfort deficit in the data.

For a fully manual home, use `config/manual_example.json`: every value is numeric and `mode = "manual"`. This mode rejects remaining sampled fields that have not been replaced manually. The realised house is always saved to `resolved_house.json`.

```bash
python main.py generate --config config/manual_example.json --output results/manual
python main.py dashboard --input results/manual
```

## What to inspect in the dashboard

The dashboard provides a date range, appliance and resident filters, monthly totals, hourly activities and occupancy, indoor and tank temperatures, the heating-weather relationship, and an adult Eurostat comparison. Appliance charts can be saved as PNG. Hover displays the exact timestamp with UTC offset and the energy value.

Inspect winter underheating, summer overheating because there is no air conditioner, unmet hot-water demand, rejected activities, and differences from Eurostat. Automated checks confirm internal consistency; they do not prove that the profile matches a real meter.

## Outputs

| File | Contents |
|---|---|
| `hourly.csv` | Weather, appliance and heating/boiler kWh, total, one-minute power peak, temperatures, occupancy, and calendar. |
| `residents_hourly.csv` | Minutes of each main activity per resident and hour; each resident totals exactly 60 minutes per hour. |
| `resident_events.csv` | Continuous activity intervals and at-home status. |
| `appliance_events.csv` | Event-based appliance runs; background loads are stored in `hourly.csv`. |
| `activity_proposals.csv` | Proposed and accepted activity times, including rejection reasons. |
| `eurostat_comparison.csv` | Adult participation and duration compared with the input Eurostat table. |
| `calendar.csv` | Applied weekends, breaks, shifts, and working-from-home days. |
| `validation.json` | Checks, diagnostics, constraints, source hashes, and DST handling. |
| `resolved_house.json`, `run_config.json` | Realised house parameters and run configuration. |

In `hourly.csv`, the `_kwh` suffix means energy for the hour and `_kw` means power. `mean_kw` is numerically equal to `total_kwh` only because intervals are one physical hour. `peak_1min_kw` is the maximum minute-level power. `hot_water_unmet_kwh` is unmet thermal demand and is not consumed electricity. `thermal_residual_kwh` is a numerical balance residual, also not a load.

## Forecasting

`main.py forecast` trains and compares the two architectures from the supplied coding brief: Modular (`base + behaviour + thermal`) and Direct total load. Both make recursive forecasts for 24 hours, 3 days, and 7 days and are compared with a weekly seasonal-naive baseline. `main.py forecast-dashboard` creates the offline comparison dashboard at `results/forecast/forecast_dashboard.html`. The detailed method, leakage policy, and deployment inputs are in `docs/forecast_models.md`.

## ML training benchmark

Use the new end-to-end benchmark to create separate chronological training and test copies of `hourly.csv`, forecast occupancy, train Random Forest, XGBoost, and CatBoost models, and generate bright comparison charts for direct and modular load forecasts:

```powershell
python main.py model-benchmark
```

Outputs are written to `results/model_benchmark/`. Training ends before 1 May 2025 in Polish local time; forecasts are evaluated at 24, 72, and 168 hours from the start of May. The original hourly data is never changed. See `docs/model_training.md` for the feature policy, files, and recursive test protocol.

## Selected prediction package

The approved operating policy is Direct Random Forest for the 24-hour horizon and Modular CatBoost for the 72- and 168-hour horizons. Run it with:

```powershell
python main.py selected-prediction --forecast-start-local "2025-09-10 00:00:00"
```

It recreates `results/prediction/`. `input/forecast_features.csv` contains only calendar and weather inputs; `output/` contains one selected forecast CSV per horizon and its metrics. `model/` is the developer hand-off: it contains only the selected fitted artifacts, the chronological training dataset, realised house parameters, requirements, and a runbook for using another issue date. `prediction_dashboard.html` and the three PNGs compare the selected backtest forecasts against actual historical demand.

## Sources and time handling

Raw source files are preserved without changes in `data/raw`. Weather time is interpreted as Polish local time and wind as km/h, as confirmed by the user. The raw weather file has no DST entries: two non-existent spring hours are omitted, and two repeated autumn hours receive the same weather. Operations are listed in `validation.json`; the final UTC timeline is unique. Raw weather values are not interpolated. Other missing values cause an error.

The calendar is amended through `data/calendar_corrections.json`, which adds 24 December 2025. The original file is not changed. The correction source is recorded in JSON. Disable `calendar.apply_corrections` if required.

## Rules and reproducibility

The final rules are in English: `docs/rules_v3.pdf`, with editable source in `docs/rules_v3.md`. Rebuild the PDF with `python tools/build_rules.py`. Parameter tables and Eurostat values are inserted from the actual configuration and CSV rather than duplicated manually. The organiser's source documents are in `docs/`.

For current-scenario validation, the complete 55-column `hourly.csv` dictionary, ML rules, and candidate real-home calibration data feeds, see `docs/hourly_data_dictionary.md`.

The configuration supplies the random seed. Separate random streams are used for the house, behaviour, and appliances. The same configuration, code version, and dependency versions reproduce the same result. New weather files must contain continuous hourly data and consistent calendars. Update calendars before generating a different period.

## Code structure

`main.py` is the canonical entry point. It invokes a registered component in `src/hackowatt/components/`: `generate`, `dashboard`, `forecast`, or `forecast-dashboard`. The generator remains reusable as the library function in `pipeline.py`; future components can call it or read its `hourly.csv` without modifying simulation code. `inputs.py` validates sources and parameters; `behaviour.py` creates schedules; `devices.py` maps activities to appliances; `thermal.py` solves the house and tank balances. Visualisation is fully local, rendered on Canvas, and has no CDN or telemetry. See `docs/architecture.md` for the complete diagram and a component example.

This is a **local Git repository**. Source data, rules, and code are tracked by Git. `results/` and `.venv/` are excluded to avoid large commits, while generated files remain on the computer. No remote repository is configured.
