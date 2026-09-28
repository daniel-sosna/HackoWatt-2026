# Model-training benchmark

Run the complete preparation and benchmark pipeline with:

```powershell
python main.py model-benchmark
```

The source `results/default/hourly.csv` is read only. By default, training ends immediately before `2025-05-01 00:00` in Polish local time. The command then makes one recursive forecast from that point, limited to 168 hours. Metrics are reported at 24, 72, and 168 hours; it never predicts beyond seven days.

The command creates an independent `results/model_benchmark/` directory containing:

| Output | Purpose |
|---|---|
| `train_model_dataset.csv` | Chronological training copy, beginning after the 168-hour lag warm-up and ending before May 2025. |
| `test_model_dataset.csv` | The 168-hour May 2025 hold-out copy, retaining targets for evaluation and observed lag values for inspection. |
| `feature_manifest.json` | Feature list, target list, training boundary, forecast start, and lag policy. |
| `occupancy_predictions.csv`, `occupancy_metrics.csv` | Actual and predicted occupancy, with 24/72/168-hour metrics. |
| `load_predictions.csv`, `load_metrics.csv` | Actual and predicted whole-home load, with 24/72/168-hour metrics. The modular rows also show base, behaviour, space-heating, boiler, predicted draw, and tank-temperature estimates. |
| `hot_water_draw_predictions.csv` | Predicted hot-water event probability, threshold, litre draw, simulated tank temperature, and boiler-energy comparison for each algorithm. |
| `models/` | Pickled fitted occupancy, direct-load, and modular component models. |
| `occupancy_forecast_24h.png`, `occupancy_forecast_72h.png`, `occupancy_forecast_168h.png` | Separate occupancy comparison charts for each forecast horizon. |
| `load_forecast_24h.png`, `load_forecast_72h.png`, `load_forecast_168h.png` | Separate load comparison charts for each forecast horizon. |
| `benchmark_dashboard.html` | Offline dashboard with all six horizon-specific charts. |

## Feature policy

The prepared data explicitly includes month number, weekday, hour, day of year, weekend, cyclic versions of time fields, every weather variable, public/school/vacation flags, planned WFH and shifts, and vacation-block flags. It also contains observed total-load lags at 1, 24, and 168 hours, plus 24/168-hour means.

`occupancy_mean` is saved as an evaluation target. It is never passed as an actual future value to a load model. Random Forest, XGBoost, and CatBoost each forecast occupancy from calendar, schedule, and weather features. Each direct or modular load model receives the matching model's `occupancy_hat` prediction.

## Models and forecast policy

The benchmark compares six forecasts with Random Forest, XGBoost, and CatBoost:

- **Direct residual load:** the model predicts a correction to the observed total load at the same local hour one week earlier. This retains the household's weekly routine while allowing weather and calendar features to correct it.
- **Modular physical boiler:** base load and resident behaviour use the same weekly-residual method. Space heating is forecast directly from weather, calendar, and predicted occupancy, so a warm week does not inherit heating from a cold prior week. Hot-water use is forecast as an event probability plus conditional litre volume, using only the observed equivalent hour one week earlier as historical input. A physical tank/thermostat simulation then converts the predicted draw into boiler electricity.

Each forecast begins at the first hour of May 2025 and runs for at most 168 hours. At every later forecast hour, load lags and rolling means are calculated from earlier model predictions, never from future actual demand. The CSV's observed lag columns are retained for transparent data inspection only.

The boiler simulation starts from the tank temperature and heater state observed immediately before forecast issue. It does not receive future observed tank temperature, hot-water draw, or occupancy. Occupancy is always supplied by the separate occupancy forecast.

To forecast from another local start time:

```powershell
python main.py model-benchmark --input results/manual/hourly.csv --output results/manual_benchmark --forecast-start-local "2025-04-10 00:00:00"
```
