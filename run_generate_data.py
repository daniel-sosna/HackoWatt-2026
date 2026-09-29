"""Run synthetic historical-data generation directly from PyCharm."""
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hackowatt.app import main  # noqa: E402


# ===== EDIT THESE VALUES BEFORE RUNNING =====
CONFIG_PATH = "config/default.json"
OUTPUT_DIRECTORY = "results/default"
# ============================================


if __name__ == "__main__":
    raise SystemExit(main(["generate", "--config", CONFIG_PATH, "--output", OUTPUT_DIRECTORY]))
