"""Train and compare 24-hour, 3-day and 7-day load forecasting architectures."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from hackowatt.forecasting import run_forecast_experiment

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'results/default/hourly.csv')
    parser.add_argument('--output',type=Path,default=ROOT/'results/forecast')
    parser.add_argument('--test-days',type=int,default=90)
    parser.add_argument('--origin-stride-hours',type=int,default=168)
    args=parser.parse_args()
    _,metrics,spec=run_forecast_experiment(args.input,args.output,args.test_days,args.origin_stride_hours)
    print(metrics[['model_id','bucket','mae_kwh','rmse_kwh','wape_pct','total_error_pct','peak_hour_mae_kwh','peak_timing_mae_h']].round(3).to_string(index=False))
    print(f"Saved {spec['origins']} rolling origins to {args.output}")
