"""Run in PyCharm, or: python generate.py --config config/default.json."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from hackowatt.pipeline import generate

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config/default.json')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    generate(ROOT,args.config,args.output)
