"""Shared data structures; business rules live in their owning modules."""

from .models import ForecastArtifacts, GeneratedHouseholdData

__all__ = ["ForecastArtifacts", "GeneratedHouseholdData"]
