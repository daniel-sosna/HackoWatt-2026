# Application structure

`main.py` is the PyCharm entry point. It dispatches named components through
`hackowatt.app`, so the application does not depend on the historical-data
generator being its only feature.

```text
main.py / python -m hackowatt
    -> hackowatt.app
        -> ComponentRegistry
            -> generate           historical-data component
            -> dashboard          historical-data dashboard component
            -> forecast           load-forecast component
            -> forecast-dashboard forecast-dashboard component

components -> domain implementation
    historical_data -> pipeline -> inputs, behaviour, devices, thermal
    load_forecasting -> forecasting
```

The generator remains a library function: `hackowatt.pipeline.generate(root,
config_path, output_path)`. Components call it; they do not duplicate its
simulation logic. This preserves the existing `hourly.csv` contract for later
components such as model training, calibration, tariff analysis or API import.

## Running components

From the project root:

```powershell
python main.py generate
python main.py dashboard
python main.py forecast
python main.py forecast-dashboard
```

With editable installation, the same commands use `hackowatt` instead of
`python main.py`:

```powershell
pip install -e .
hackowatt generate --config config/manual_example.json --output results/manual
```

When invoking the installed command outside the repository, provide the root
before the component name: `hackowatt --project-root C:\path\to\HackoWatt_Family generate`.

`generate.py`, `visualize.py` and `forecast.py` remain compatibility wrappers
for existing PyCharm run configurations.

## Adding a component

Create a module under `src/hackowatt/components/`. A component declares a
unique command name, adds its own command-line arguments, and receives a
`ProjectContext` with a stable project root.

```python
class TariffAnalysisComponent:
    name = "tariff-analysis"
    help = "Estimate electricity cost from hourly data."

    def add_arguments(self, subparsers):
        parser = subparsers.add_parser(self.name, help=self.help)
        parser.add_argument("--input", default="results/default/hourly.csv")
        parser.set_defaults(component=self)

    def run(self, args, context):
        hourly_path = context.path(args.input)
        # Read the existing generated data and write this component's outputs.
        return 0
```

Register an instance once in `built_in_registry()` in
`src/hackowatt/components/__init__.py`. The main parser discovers it
automatically. Keep simulation/domain code in dedicated modules and put only
argument handling and orchestration in the component.
