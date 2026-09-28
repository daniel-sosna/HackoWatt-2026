"""Unified HackoWatt dashboard. Run via ``python main.py dashboard``."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hackowatt.services import DashboardService  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--input", default="results/default")
    parser.add_argument("--forecast-input", default="results/forecast")
    return parser.parse_known_args()[0]


def historical_view(service: DashboardService) -> None:
    household = service.historical()
    summary = service.historical_summary()
    st.subheader("Historical household profile")
    first, second, third, fourth = st.columns(4)
    first.metric("Physical hours", f"{summary['hours']:,}")
    second.metric("Total demand", f"{summary['total_kwh']:,.0f} kWh")
    third.metric("Average hour", f"{summary['mean_kwh']:.2f} kWh")
    fourth.metric("Minute-level peak", f"{summary['peak_kw']:.2f} kW")

    hourly = household.hourly.copy()
    timestamp = pd.to_datetime(hourly["timestamp_utc"], utc=True).dt.tz_convert("Europe/Warsaw")
    hourly.index = timestamp
    available = [column for column in ["total_kwh", "space_heating_kwh", "water_heater_kwh"] if column in hourly]
    st.line_chart(hourly[available], use_container_width=True)
    st.caption("Hourly energy in local Polish time. `timestamp_utc` remains the canonical source index.")
    st.subheader("Highest-load hours")
    st.dataframe(summary["peaks"], use_container_width=True, hide_index=True)


def forecasting_view(service: DashboardService) -> None:
    st.subheader("Forecast quality")
    try:
        artifacts = service.forecast()
    except FileNotFoundError as error:
        st.info(f"{error}")
        return
    predictions, metrics = artifacts.predictions, artifacts.metrics
    model = st.selectbox("Model", sorted(predictions.model_id.unique()))
    origins = sorted(predictions.origin_utc.unique())
    origin = st.selectbox("Rolling forecast origin", origins, index=len(origins) - 1)
    horizon = st.select_slider("Horizon", options=[24, 72, 168], value=24,
                              format_func=lambda value: {24: "24 hours", 72: "3 days", 168: "7 days"}[value])
    selected = predictions[(predictions.model_id == model) & (predictions.origin_utc == origin)]
    selected = selected[selected.horizon_h <= horizon].sort_values("horizon_h")
    chart = selected.set_index(pd.to_datetime(selected.timestamp_utc, utc=True))[["actual_kwh", "load_hat"]]
    chart.columns = ["Actual", "Forecast"]
    st.line_chart(chart, use_container_width=True)
    bucket = {24: "hours_1_24", 72: "hours_25_72", 168: "hours_1_168"}[horizon]
    st.dataframe(metrics[metrics.bucket == bucket], use_container_width=True, hide_index=True)
    st.caption("This is rolling-origin backtesting. Recorded weather is treated as the issued forecast for validation.")


def renewable_view(service: DashboardService) -> None:
    st.subheader("PV planning")
    controls, results = st.columns([1, 2])
    with controls:
        capacity = st.slider("PV capacity (kWp)", 0.0, 12.0, 6.0, 0.5)
        specific_yield = st.slider("Specific yield (kWh/kWp/year)", 700, 1_300, 1_000, 25)
        mode = st.selectbox("Economic assumptions", ["hackathon", "poland"],
                            format_func=lambda key: key.replace("_", " ").title())
    assessment = service.renewable(capacity, specific_yield, mode)
    with results:
        first, second, third = st.columns(3)
        first.metric("PV generation", f"{assessment['pv_kwh']:,.0f} kWh")
        second.metric("Self-consumption", f"{assessment['self_consumption_pct']:.1f}%")
        third.metric("Demand coverage", f"{assessment['demand_coverage_pct']:.1f}%")
        first, second, third = st.columns(3)
        first.metric("CAPEX", f"{assessment['capex']:,.0f} {assessment['currency']}")
        second.metric("Annual savings", f"{assessment['annual_savings']:,.0f} {assessment['currency']}")
        payback = assessment["simple_payback_years"]
        third.metric("Simple payback", f"{payback:.1f} years" if payback else "Not reached")
    st.caption("PV uses the supplied weather only as a daylight shape and normalises it to the selected annual specific yield.")
    suggestions = service.flexible_loads()
    if not suggestions.empty:
        st.subheader("Conservative load-shifting candidates")
        st.dataframe(suggestions, use_container_width=True, hide_index=True)


def main() -> None:
    args = arguments()
    root = args.project_root.resolve()
    service = DashboardService(root / args.input, root / args.forecast_input)
    st.set_page_config(page_title="HackoWatt Family", page_icon="⚡", layout="wide")
    st.title("HackoWatt Family")
    st.caption("Synthetic household demand, forecast validation, and renewable-energy planning.")
    page = st.sidebar.radio("Navigate", ["Historical profile", "Forecast quality", "PV planning"])
    if page == "Historical profile":
        historical_view(service)
    elif page == "Forecast quality":
        forecasting_view(service)
    else:
        renewable_view(service)


if __name__ == "__main__":
    main()
