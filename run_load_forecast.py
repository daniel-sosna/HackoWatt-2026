"""Train and compare the load-forecast models directly from PyCharm."""
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hackowatt.app import main  # noqa: E402


# ===== EDIT THESE VALUES BEFORE RUNNING =====
INPUT_HOURLY_CSV = "results/default/hourly.csv"
OUTPUT_DIRECTORY = "results/forecast"
TEST_DAYS = 90
ORIGIN_STRIDE_HOURS = 168
# ============================================


if __name__ == "__main__":
    raise SystemExit(main([
        "forecast",
        "--input", INPUT_HOURLY_CSV,
        "--output", OUTPUT_DIRECTORY,
        "--test-days", str(TEST_DAYS),
        "--origin-stride-hours", str(ORIGIN_STRIDE_HOURS),
    ]))
