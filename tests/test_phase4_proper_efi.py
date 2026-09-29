"""
Unit tests for Phase 4: Proper Extreme Forecast Index (EFI) and Shift-of-Tails (SOT).
Tests mathematical validity of ECMWF non-parametric integral:
EFI = (2 / pi) * integral_0^1 [ (p - F_ensemble(Q_c(p))) / sqrt(p*(1-p)) ] dp
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import numpy as np
from src.data_loader import WeatherDataLoader
from src.anomaly_detect import AnomalyTracker


def test_true_ensemble_efi_schema_and_climatological_null():
    """When the forecast ensemble matches climatology, EFI must be ~0."""
    dl = WeatherDataLoader("amphan_2020")
    tracker = AnomalyTracker(dl)

    clim_w_mean = np.array(tracker.clim["wind_mean"])
    clim_w_std = np.array(tracker.clim["wind_std"])

    np.random.seed(42)
    # Generate 50 members sampled directly from the local climatological normal distribution
    M, H, W = 50, clim_w_mean.shape[0], clim_w_mean.shape[1]
    clim_sample_members = np.zeros((M, H, W), dtype=np.float32)
    for m in range(M):
        clim_sample_members[m] = np.random.normal(clim_w_mean, clim_w_std)

    res = tracker.compute_true_ensemble_efi(
        ensemble_wind_members=clim_sample_members,
        lead_hours=72,
        forecast_source="Climatology Null Control Ensemble"
    )

    # Required Schema assertions
    assert res["efi_type"] == "true_ensemble_climatology"
    assert res["climatology_source"] == "ECMWF ERA5 Bay of Bengal May Climatology"
    assert res["ensemble_members"] == 50
    assert res["lead_hours"] == 72
    assert "provenance" in res
    assert res["provenance"]["verification_status"] == "NUMERICAL_INTEGRATION_VERIFIED"
    assert res["provenance"]["data_source_type"] == "ERA5_REANALYSIS"

    # Mathematical property: EFI of climatological sample must be centered at 0
    assert abs(res["efi_wind_mean"]) < 0.10, f"Climatological sample EFI mean={res['efi_wind_mean']} must be close to 0.0"


def test_true_ensemble_efi_extreme_cyclone_response():
    """When the forecast ensemble reflects an extreme cyclone (>Q99), EFI and SOT must be strongly positive."""
    dl = WeatherDataLoader("amphan_2020")
    tracker = AnomalyTracker(dl)

    clim_w_mean = np.array(tracker.clim["wind_mean"])
    clim_w_std = np.array(tracker.clim["wind_std"])

    np.random.seed(42)
    # Severe cyclone: winds 35-50 m/s (~130-180 km/h) at the core
    M, H, W = 20, clim_w_mean.shape[0], clim_w_mean.shape[1]
    extreme_members = np.zeros((M, H, W), dtype=np.float32)
    for m in range(M):
        extreme_members[m] = clim_w_mean + 3.0 * clim_w_std + np.random.normal(0, 1.0, (H, W))

    res = tracker.compute_true_ensemble_efi(
        ensemble_wind_members=extreme_members,
        lead_hours=96,
        forecast_source="Synthetic Severe Tropical Cyclone Ensemble"
    )

    assert res["efi_wind_peak"] > 0.70, f"Extreme cyclone EFI peak={res['efi_wind_peak']} must exceed 0.70"
    assert res["sot_wind_peak"] > 0.0, f"Extreme cyclone SOT peak={res['sot_wind_peak']} must exceed 0.0"
    assert res["efi_wind_mean"] > 0.50, f"Extreme cyclone EFI mean={res['efi_wind_mean']} must exceed 0.50"


def test_api_true_ensemble_efi_endpoint():
    """Verifies that /api/efi/true-ensemble endpoint responds with HTTP 200 and required keys."""
    from fastapi.testclient import TestClient
    from src.api import app

    client = TestClient(app)
    response = client.get("/api/efi/true-ensemble?lead_hours=72&step_index=5&n_members=5")
    assert response.status_code == 200, f"API returned error: {response.text}"
    data = response.json()

    assert data["efi_type"] == "true_ensemble_climatology"
    assert data["ensemble_members"] == 5
    assert data["lead_hours"] == 72
    assert "efi_peak" in data
    assert "sot_peak" in data
    assert "provenance" in data
