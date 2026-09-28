"""Compatibility wrapper. Prefer: python main.py forecast."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from hackowatt.app import main

if __name__ == '__main__':
    raise SystemExit(main(['forecast', *sys.argv[1:]]))
