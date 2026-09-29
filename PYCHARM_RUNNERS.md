# Running from PyCharm

Run these files directly with the green Run button or by right-clicking the
file and selecting **Run**. No command-line arguments are required.

| File | Purpose | Settings to edit |
|---|---|---|
| `run_generate_data.py` | Generate the historical hourly dataset. | `CONFIG_PATH`, `OUTPUT_DIRECTORY` |
| `run_load_forecast.py` | Train and evaluate the load-forecast models. | Input/output paths, test days, origin stride |
| `run_dashboard.py` | Open the local dashboard in a browser. | Generated-data and forecast-results directories |

Each file has a clearly marked settings block at its top. `main.py` remains
available for developers who prefer commands, but it is not required for the
normal PyCharm workflow.
