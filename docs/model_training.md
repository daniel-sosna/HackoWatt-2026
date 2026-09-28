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
| `load_predictions.csv`, `load_metrics.csv` | Actual and predicted whole-home load, with 24/72/168-hour metrics. |
| `models/` | Pickled fitted occupancy, direct-load, and modular component models. |
| `*.png`, `benchmark_dashboard.html` | Bright-colour comparison charts and an offline dashboard. |

## Feature policy

The prepared data explicitly includes month number, weekday, hour, day of year, weekend, cyclic versions of time fields, every weather variable, public/school/vacation flags, planned WFH and shifts, and vacation-block flags. It also contains observed total-load lags at 1, 24, and 168 hours, plus 24/168-hour means.

`occupancy_mean` is saved as an evaluation target. It is never passed as an actual future value to a load model. Random Forest, XGBoost, and CatBoost each forecast occupancy from calendar, schedule, and weather features. Each direct or modular load model receives the matching model's `occupancy_hat` prediction.

## Models and forecast policy

The benchmark compares six recursive forecasts:

- Direct total-load model with Random Forest, XGBoost, and CatBoost.
- Modular base, behaviour, and thermal models with Random Forest, XGBoost, and CatBoost; their predictions are summed.

Each forecast begins at the first hour of May 2025 and runs for at most 168 hours. At every later forecast hour, load lags and rolling means are calculated from earlier model predictions, never from future actual demand. The CSV's observed lag columns are retained for transparent data inspection only.

To forecast from another local start time:

```powershell
python main.py model-benchmark --input results/manual/hourly.csv --output results/manual_benchmark --forecast-start-local "2025-05-01 00:00:00"
```
