# Selected forecast model hand-off

This directory contains only the approved model policy: Direct Random Forest at 24 hours and Modular CatBoost at 72 and 168 hours. The fitted artifacts reproduce the September 2025 backtest. `training_dataset.csv` is the chronological training data ending immediately before the forecast issue time. `feature_manifest.json` defines its features, targets, and time boundary. `resolved_house.json` provides the physical boiler parameters used by the modular forecast.

## Run on another issue date

Use the repository entry point, which retrains from all rows preceding the requested local issue time and then writes the compact package:

```powershell
.venv\Scripts\python.exe main.py selected-prediction --input results/default/hourly.csv --output results/prediction --forecast-start-local "2025-09-10 00:00:00"
```

For a live deployment, replace the historical portion of `hourly.csv` with measured household history and provide issued weather/calendar inputs for the future window. The model must receive at least 168 prior hourly load observations. The modular forecast also needs the current tank temperature, prior heater state, and 168 hours of hot-water-draw history. Do not populate future measured load, occupancy, tank temperature, or hot-water draw.

The pickles require the versions listed in `requirements.txt`. Use the application command for retraining and inference because it applies recursive lag handling and the physical boiler simulation around the fitted estimators.
