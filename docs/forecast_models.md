# Two hourly load-forecasting models

This implementation follows `HackoWatt_Two_Model_Architectures.pdf`. PV, grid export, and electricity price are intentionally outside this phase. The shared target is `total_kwh`, the household energy used in one physical hour.

## Shared experiment

Data through 2 October 2025 is used for training. The final 90 days are an isolated test. The test uses 12 forecast origins, seven days apart. Each origin creates one recursive 168-hour forecast. Results are calculated separately for hours 1--24, 25--72, and 73--168, as required by the brief.

After the issue time, the models do not receive future `total_kwh`, appliance loads, indoor temperature, tank temperature, actual occupancy, or future activity. Lags at 1, 24, and 168 hours and rolling means become the models' own predictions beyond the corresponding horizon. Evaluation uses recorded historical weather as a perfect forecast. This makes the result more optimistic than a production assessment, which must retain the weather forecast and its issue time.

The main metrics are MAE and RMSE in kWh/hour; WAPE; error in total forecast energy; error at the actual peak-hour value; and peak-time error. `seasonal_naive` repeats the same hour from the preceding week. It is not one of the two main architectures; it is a required honest baseline.

## Architecture A: modular component model

`load_hat = base_hat + behaviour_hat + thermal_hat`.

`base_hat` is the mean hourly profile of the fridge, router, and standby load in the training period. `behaviour_hat` forecasts the remaining household appliances. `thermal_hat` is the sum of separate space-heating and boiler forecasts. Behaviour, heating, and boiler use separate recursive histogram-gradient-boosting models. Each learns a correction to the corresponding load in the preceding week rather than the absolute load level, preserving the weekly rhythm.

Inputs include cyclic hour, weekday, and annual features; weekend; temperature, cloud cover, humidity, wind, precipitation, snowfall, radiation; degree-hours; public holidays, school breaks, school days, joint family vacation, WFH, and known shifts; and its own 1/24/168-hour lags plus 24/168-hour means.

The advantage is that `base_hat`, `behaviour_hat`, `space_heating_hat`, `water_heater_hat`, and `thermal_hat` explain a peak. The limitation is that, after moving to a real home, component lags require separate metering for household, heating, and boiler demand. Without this, use a physical thermal model calibrated with temperature and the main meter, or mark component estimates as uncertain.

## Architecture B: direct total model

One recursive histogram-gradient-boosting model forecasts `total_kwh` directly. Inputs use the same calendar, weather, and planned-schedule features, but the history contains only the total meter. It also learns a correction to the prior week.

The advantage is that a real deployment needs only a main smart meter, calendar, and weather. The limitation is that it cannot reliably attribute demand to the boiler or heating.

## Why CatBoost or LightGBM is not used yet

The project environment does not include CatBoost, LightGBM, XGBoost, or scikit-learn. The repository therefore includes a compact NumPy histogram-gradient-boosting implementation so it runs offline without implicit package installation. The architecture contract, chronological split, recursive forecast, and leakage protection remain the same. When CatBoost or LightGBM becomes available, replace only the regressor while preserving inputs, outputs, and backtesting.

## Running the models

```bash
python main.py forecast
python main.py dashboard
```

`results/forecast/forecast_predictions.csv` follows the required contract: `timestamp_utc`, `horizon_h`, `load_hat`, `model_id`, plus component forecasts for the modular model. `forecast_metrics.csv` contains the comparison. `forecast_model_spec.json` records the split, features, explicitly excluded leakage columns, and model state. The unified dashboard's **Forecast quality** page shows a selected forecast origin and horizon.

## Moving to a real home

For an honest day-ahead run, provide only the published weather forecast, known calendar, planned shifts/WFH, and past real measurements. Do not provide future actual indoor temperature, future occupancy, or actual future appliance demand. Once a real meter is available, retrain chronologically and store each prediction with its observation, issue time, and model version.

## Renewable simulator presentation and import contract

The renewable view labels the saved run as a historical backtest. Its empirical
10th–90th residual range uses only earlier origins with target observations
strictly before the displayed issue time. The range is uncalibrated; the model
is selected retrospectively by validation WAPE, not on an independent holdout.
Direct-total predictions and modular component estimates are displayed as
separate estimates and must not be described as an exact decomposition.

The archived offline renewable exporter accepts an `--issued-forecast` static CSV snapshot with at
least 24 consecutive UTC hours: `timestamp_utc`, `load_kwh`, `outdoor_c`,
`wind_ms` and `radiation_wm2`. Energy, wind and irradiance must be finite and
nonnegative; temperature may be negative. Optional `issued_at_utc` must be one
issue time at or before the target start; an omitted issue time is unknown.
Optional interval bounds must be nonnegative and ordered. Optional
`pv_kwh_per_kwp` replaces the irradiance proxy without annual-yield rescaling.
Thermal planning is enabled only with `space_heating_kwh`, `water_heating_kwh`
and `hot_water_draw_l`. Sensor temperature ranges are checked, but freshness
checks and an automatic refresh/control service remain future work. See the
presentation handbook and `docs/renewable_energy_simulator.md` for full fields.
