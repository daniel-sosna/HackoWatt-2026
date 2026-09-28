# Application structure

`main.py` is the PyCharm entry point. It exposes only the components needed to
generate and inspect synthetic data, and to run the configurable forecast.

```text
main.py / python -m hackowatt
    -> hackowatt.app
        -> generate             synthetic historical data
        -> dashboard            generated-data diagnostics
        -> issue-date-forecast  selected model at a supplied date

historical_data -> pipeline -> inputs, behaviour, devices, thermal
issue_date_forecast -> forecast_model
```

The generator is reusable as `hackowatt.pipeline.generate(root, config_path,
output_path)`. The forecast integration boundary is
`hackowatt.issue_date_forecast.forecast_from_issue_date(request)`.

## Retained commands

```bash
python main.py generate
python main.py dashboard
python main.py issue-date-forecast --forecast-start-local "2025-09-10 00:00:00"
```

For the simplest PyCharm flow, edit the settings at the top of
`run_issue_date_forecast.py` and run that file directly.

## Adding future components

Create a component under `src/hackowatt/components/` only when it operates on
the generator output or forecast API. Register it once in
`built_in_registry()`; keep domain logic outside the CLI adapter.
