"""Open the local validation dashboard directly from PyCharm."""
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hackowatt.app import main  # noqa: E402


# ===== EDIT THESE VALUES BEFORE RUNNING =====
GENERATED_DATA_DIRECTORY = "results/default"
FORECAST_RESULTS_DIRECTORY = "results/forecast"
# ============================================


if __name__ == "__main__":
    raise SystemExit(main([
        "dashboard",
        "--input", GENERATED_DATA_DIRECTORY,
        "--forecast-input", FORECAST_RESULTS_DIRECTORY,
    ]))
