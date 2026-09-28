"""Compatibility wrapper. Prefer: python main.py generate."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from hackowatt.app import main

if __name__=='__main__':
    raise SystemExit(main(['generate',*sys.argv[1:]]))
