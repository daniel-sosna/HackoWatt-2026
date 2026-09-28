# Instructions for future AI contributors

## Project purpose and entry points

This repository models and forecasts synthetic hourly electricity demand for a Silesian family home. Use Python 3.11+ and run commands from the repository root.

Create and activate a local virtual environment before installing dependencies or running the application:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Keep the environment in `.venv/`; it is local-only and must not be committed. When shell activation is unavailable, run commands with `.venv/bin/python` explicitly.

Use `requirements.txt` for normal development and runtime installs. Use `requirements-tested.txt` when reproducing the exact dependency versions used by the retained validation checks.

Use the application entry point for routine work:

```bash
python main.py generate
python main.py dashboard
python main.py forecast
python main.py forecast-dashboard
```

`main.py` delegates to components in `src/hackowatt/components/`. Put a new user-facing capability in a component and register it in the application; do not add business logic to a legacy root wrapper. The generator is reusable from Python as `hackowatt.pipeline.generate(...)`.

## Data and scenario rules

- Treat `data/raw/` and supplied organiser PDFs/DOCX files as immutable source material. Do not edit, translate, or overwrite them.
- Treat `results/` as generated output. Do not hand-edit it; regenerate it after changing rules, configuration, or generator code.
- Keep timestamps unambiguous. `timestamp_utc` is the canonical physical-hour index; source weather timestamps are Polish local time (`Europe/Warsaw`), and source wind speed is km/h.
- The default scenario has direct electric heating and a separate electric boiler. It has improved insulation and passive night ventilation, but no PV, battery, heat pump, or air conditioner. Do not introduce these technologies silently.
- Maintain the jointly planned family-vacation policy: 20 working days per parent each year in blocks of 10 summer days, 5 winter days, and 5 spring/autumn days. The whole family is away during a vacation.

## Forecasting safeguards

- Forecasts may use only values known at the issue time: past measurements, issued weather forecasts, calendars, and planned schedules.
- Never train or evaluate with future measured `total_kwh`, appliance loads, occupancy, indoor temperature, or boiler temperature as a feature.
- Keep the seasonal-naive baseline and report the 24-hour, 3-day, and 7-day horizons when changing forecasting code.

## Testing policy

- Do not write general-purpose tests for application wiring, command registration, dashboards, or end-to-end workflows.
- Keep only simple validation tests for input data contracts and the forecasting, behaviour, device, and thermal models.
- Retained tests must use small self-contained fixtures; do not version generated outputs or add tests that depend on files under `results/`.

## Documentation and verification

- Keep authored documentation and user-facing text in English. Preserve the original language of external source files.
- Update `docs/rules_v3.md` when changing behavioural or physical assumptions; rebuild and visually review `docs/rules_v3.pdf` if the rules document changes.
- Update `docs/hourly_data_dictionary.md` when the hourly schema changes and `docs/forecast_models.md` when the forecasting contract changes.
- At minimum run the retained validation tests with `python -m unittest discover -s tests -v`, `python main.py --help`, and `git diff --check` after code or documentation changes. Regenerate representative outputs when a change affects the data pipeline; do not commit those outputs.

User instructions take precedence over this file.
