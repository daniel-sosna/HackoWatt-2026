"""Run one selected forecast from PyCharm without command-line parameters.

Edit the settings in the marked section, then right-click this file in
PyCharm and choose Run 'run_issue_date_forecast'.
"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from hackowatt.issue_date_forecast import (  # noqa: E402
    ForecastRequest,
    forecast_from_issue_date,
    write_issue_date_forecast,
)


# ===== EDIT THESE VALUES BEFORE RUNNING =====
FORECAST_START_LOCAL = "2026-09-28 00:00:00"
HORIZON_HOURS = 24  # Allowed values: 24, 72, or 168.
INPUT_HOURLY_CSV = PROJECT_ROOT / "results" / "default" / "hourly.csv"
FORECAST_WEATHER_CSV = PROJECT_ROOT / "data" / "raw" / "katowice_weather_forecast.csv"
OUTPUT_DIRECTORY = PROJECT_ROOT / "results" / "issue_date_forecast"
# ============================================


def main() -> None:
    if not INPUT_HOURLY_CSV.is_file():
        raise FileNotFoundError(
            f'Input data was not found: {INPUT_HOURLY_CSV}. Run main.py generate first, '
            'or change INPUT_HOURLY_CSV to your hourly.csv file.')

    request = ForecastRequest(
        hourly_path=INPUT_HOURLY_CSV,
        forecast_start_local=FORECAST_START_LOCAL,
        horizon_hours=HORIZON_HOURS,
        forecast_weather_path=FORECAST_WEATHER_CSV,
    )
    result = forecast_from_issue_date(request)
    write_issue_date_forecast(result, OUTPUT_DIRECTORY)

    print(f'Model: {result.model_id}')
    print(f'Forecast starts: {result.manifest["forecast_start_local"]}')
    print(f'Horizon: {HORIZON_HOURS} hours')
    print(f'Forecast file: {OUTPUT_DIRECTORY / "forecast.csv"}')
    print(f'Comparison chart: {OUTPUT_DIRECTORY / "forecast_vs_actual.png"}')
    print(f'Manifest file: {OUTPUT_DIRECTORY / "manifest.json"}')


if __name__ == '__main__':
    main()
