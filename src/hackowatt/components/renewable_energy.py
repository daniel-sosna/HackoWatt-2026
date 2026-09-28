"""Compatibility import for the retired offline renewable exporter.

Use ``python main.py dashboard`` for the maintained unified application.
"""

from ..legacy.renewable_energy import apply_model_profile, build_issued_forecast_payload

__all__ = ["apply_model_profile", "build_issued_forecast_payload"]
