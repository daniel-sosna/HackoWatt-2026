# Instructions for future AI contributors

## Project purpose and entry points

This repository generates synthetic hourly electricity demand for a Silesian
family home and provides a configurable issue-date forecast model. Use Python
3.11+ and run commands from the repository root.

Create and activate a local virtual environment before installing dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Use `main.py` for the retained components:

```bash
python main.py generate
python main.py dashboard
python main.py issue-date-forecast --forecast-start-local "2025-09-10 00:00:00"
```

For non-technical PyCharm use, edit and run `run_issue_date_forecast.py`.

## Data and scenario rules

- Treat `data/raw/` and supplied organiser PDFs/DOCX files as immutable source material.
- Treat `results/` as generated output. Do not hand-edit it.
- Keep timestamps unambiguous. `timestamp_utc` is the canonical physical-hour index; source weather timestamps are Polish local time (`Europe/Warsaw`) and wind speed is km/h.
- The default scenario has direct electric heating and a separate electric boiler. It has improved insulation and passive night ventilation, but no PV, battery, heat pump, or air conditioner.
- Maintain the jointly planned family-vacation policy: 20 working days per parent each year in blocks of 10 summer days, 5 winter days, and 5 spring/autumn days. The whole family is away during a vacation.

## Forecast safeguards

- The public integration boundary is `hackowatt.issue_date_forecast`.
- Forecasts may use only values known at issue time: past measurements, issued weather forecasts, calendars, and planned schedules.
- Never use future measured `total_kwh`, appliance loads, occupancy, indoor temperature, or boiler temperature as model features.
- Keep the selected-model policy: Direct Random Forest for 24 hours and Modular CatBoost for 72 or 168 hours.

## Testing policy

- Keep only compact, self-contained validation tests for input data contracts and the forecasting, behaviour, device, and thermal models.
- Do not add tests that depend on files under `results/`.
- At minimum run `python -m unittest discover -s tests -v`, `python main.py --help`, and `git diff --check` after code or documentation changes.

## Documentation and verification

- Keep authored documentation and user-facing text in English. Preserve the original language of external source files.
- Update `docs/rules_v3.md` when changing behavioural or physical assumptions; rebuild and visually review `docs/rules_v3.pdf` if the rules document changes.
- Update `docs/hourly_data_dictionary.md` when the hourly schema changes and `docs/issue_date_forecast_api.md` when the forecast contract changes.
