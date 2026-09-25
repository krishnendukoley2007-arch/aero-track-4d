"""
Real Unit Tests for Engineering Hardening (SIH 26078 Build Brief v3 Section 6)
Validates:
1. Physics-Informed Conservation Loss (divergence penalty, moisture flux convergence penalty, gradient flow)
2. Defensible REST API Contracts across all operational and multi-hazard endpoints
"""

import math
import pytest
import torch
import numpy as np
from fastapi.testclient import TestClient
from src.api import app
from src.downscale.corrdiff_model import PhysicsInformedConservationLoss

client = TestClient(app)


# =========================================================================
# 1. Physics-Informed Conservation Loss Unit Tests
# =========================================================================

class TestPhysicsInformedConservationLoss:
    """Verifies that fluid dynamics and thermodynamic loss terms strictly penalize unphysical states."""

    def setup_method(self):
        self.loss_fn = PhysicsInformedConservationLoss(
            lambda_mse=1.0,
            lambda_l1=0.3,
            lambda_div=0.15,
            lambda_mfc=0.20,
            dx=5000.0
        )

    def test_divergence_loss_zero_on_uniform_wind_field(self):
        """A spatially uniform wind field has zero spatial derivatives and zero divergence."""
        # channels: 0: wind, 1: mslp, 2: precip, 3: temp
        pred = torch.ones(1, 4, 32, 32) * 50.0  # uniform 50 km/h wind
        target = torch.ones(1, 4, 32, 32) * 50.0

        loss_dict = self.loss_fn(pred, target)
        div_loss = loss_dict["loss_divergence"].item()
        assert div_loss == pytest.approx(0.0, abs=1e-8), f"Expected 0.0 divergence for uniform field, got {div_loss}"

    def test_divergence_loss_penalizes_divergent_wind_field(self):
        """A wind field with strong spatial velocity divergence must produce a strictly positive divergence loss."""
        pred = torch.zeros(1, 4, 32, 32)
        # Create non-zero gradient along x and y
        for i in range(32):
            for j in range(32):
                pred[0, 0, i, j] = float(j * 5.0)  # dw/dx > 0
        target = pred.clone()

        loss_dict = self.loss_fn(pred, target)
        div_loss = loss_dict["loss_divergence"].item()
        assert div_loss > 0.0, f"Expected positive divergence loss, got {div_loss}"

    def test_mfc_loss_zero_when_convergence_supports_precipitation(self):
        """When wind strongly converges (negative divergence = positive convergence), MFC penalty is 0."""
        pred = torch.zeros(1, 4, 32, 32)
        # Inward velocity gradient (convergence: dw/dx < 0, dw/dy < 0 => -div > 0)
        for i in range(32):
            for j in range(32):
                pred[0, 0, i, j] = float((32 - j) * 10.0 + (32 - i) * 10.0)  # convergent
        pred[0, 2, :, :] = 0.8  # intense precipitation core
        target = pred.clone()

        loss_dict = self.loss_fn(pred, target)
        mfc_loss = loss_dict["loss_moisture_convergence"].item()
        assert mfc_loss == pytest.approx(0.0, abs=1e-8), f"MFC penalty should be 0 during strong convergence, got {mfc_loss}"

    def test_mfc_loss_penalizes_intense_rain_in_divergent_drying_zone(self):
        """Penalizes intense rain cells that occur where air is divergent (drying, no moisture convergence)."""
        pred = torch.zeros(1, 4, 32, 32)
        # Outward velocity gradient (divergence: dw/dx > 0 => wind_conv < 0)
        for i in range(32):
            for j in range(32):
                pred[0, 0, i, j] = float(j * 20.0 + i * 20.0)
        # High precipitation where air is diverging
        pred[0, 2, 5:25, 5:25] = 0.95  # unphysical severe rain without moisture inflow
        target = pred.clone()

        loss_dict = self.loss_fn(pred, target)
        mfc_loss = loss_dict["loss_moisture_convergence"].item()
        assert mfc_loss > 0.0, f"Unphysical uncoupled precipitation must trigger positive MFC penalty, got {mfc_loss}"

    def test_gradient_flow_through_divergence_and_mfc_terms(self):
        """Verifies that gradients propagate back to neural network weights from divergence and MFC loss terms."""
        pred = torch.randn(1, 4, 32, 32, requires_grad=True)
        target = torch.randn(1, 4, 32, 32)

        loss_dict = self.loss_fn(pred, target)
        total_loss = loss_dict["total_loss"]
        total_loss.backward()

        assert pred.grad is not None, "Gradients must propagate to input tensor"
        assert not torch.all(pred.grad == 0), "Gradients must be non-zero"
        # Specifically verify gradients in wind (channel 0) and precip (channel 2)
        assert torch.sum(torch.abs(pred.grad[:, 0, :, :])) > 0.0, "Wind channel must receive divergence gradients"
        assert torch.sum(torch.abs(pred.grad[:, 2, :, :])) > 0.0, "Precip channel must receive MFC gradients"


# =========================================================================
# 2. Defensible REST API Contract Unit Tests
# =========================================================================

class TestDefensibleAPIContracts:
    """Tests rigorous schema contracts, values, and error behaviors for all operational and multi-hazard endpoints."""

    def test_status_endpoint_contract(self):
        res = client.get("/api/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert "Ministry of Earth Sciences" in data["organization"]
        assert "stage_1_tracker" in data["modules"]
        assert "stage_2_downscaler" in data["modules"]

    def test_track_endpoint_contract(self):
        res = client.get("/api/track")
        assert res.status_code == 200
        data = res.json()
        assert "tracked_steps" in data
        track = data["tracked_steps"]
        assert len(track) == 13, "Must return full 13-timestep lifecycle"
        for step in track:
            assert "step_index" in step
            assert "timestamp" in step
            assert "centroid" in step
            assert "lat" in step["centroid"] and "lon" in step["centroid"]
            assert "efi_peak" in step
            assert "bounding_box" in step
            assert "ibtracs_ground_truth" in step

    def test_track_error_acceptance_threshold(self):
        res = client.get("/api/track-error")
        assert res.status_code == 200
        data = res.json()
        assert "mean_track_error_km" in data
        assert "table" in data
        held_out = [r for r in data["table"] if r.get("is_held_out_test")]
        assert len(held_out) == 2, "Must evaluate 2 held-out timesteps (Step 5 and Step 10)"
        held_out_mean = sum(r["track_error_km"] for r in held_out) / len(held_out)
        assert held_out_mean <= 46.2, (
            f"Acceptance failed: held-out track error {held_out_mean:.2f} km "
            f"exceeds 46.2 km baseline"
        )
        assert [r["step_index"] for r in held_out] == [5, 10]

    def test_downscale_step5_contract(self):
        res = client.get("/api/downscale?step_index=5")
        assert res.status_code == 200
        data = res.json()
        assert data["resolution_km"] == 5.0
        assert data["grid_shape"] == [38, 38]
        assert "fields" in data
        assert "coarse_nwp" in data["fields"]
        assert "corrdiff_ensemble_mean" in data["fields"]
        assert "corrdiff_high_impact_p90" in data["fields"]

    def test_spherical_mesh_area_variance_contract(self):
        res = client.get("/api/spherical-mesh")
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "FeatureCollection"
        meta = data.get("metadata", {})
        assert "cell_area_variance_percent" in meta
        assert meta["cell_area_variance_percent"] < 5.0, (
            f"Acceptance failed: mesh area variance {meta['cell_area_variance_percent']}% exceeds 5% threshold"
        )

    def test_gnn_explainability_overlay_contract(self):
        res = client.get("/api/gnn-mesh-state?step_index=5")
        assert res.status_code == 200
        data = res.json()
        assert "explainability_overlay" in data
        overlay = data["explainability_overlay"]
        assert "top_weighted_attention_scores" in overlay
        assert len(overlay["top_weighted_attention_scores"]) > 0
        assert "source_node" in overlay["top_weighted_attention_scores"][0]
        assert "attention_weight" in overlay["top_weighted_attention_scores"][0]
        assert "feature_attribution_weights" in overlay
        assert "dynamical_steering_summary" in overlay

    def test_alert_endpoint_paired_confidence_contract(self):
        payload = {
            "lat": 21.62,
            "lon": 87.51,
            "location_name": "Digha Coast",
            "step_index": 5,
            "hazard_id": "amphan_2020",
            "op_mode": "cyclone"
        }
        res = client.post("/api/alert", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "alert_tier" in data
        # Check paired tier includes ensemble spread string
        assert "Ensemble Spread" in data["alert_tier"]
        assert "confidence_aware_assessment" in data
        conf = data["confidence_aware_assessment"]
        assert "ensemble_spread_std_kmh" in conf
        assert "probabilistic_confidence_score" in conf
        assert "spatial_footprint_refinement" in data
        refine = data["spatial_footprint_refinement"]
        assert refine["false_alarm_area_reduction_percent"] >= 95.0

    def test_multilingual_bulletin_generation(self):
        """Verifies official IMD advisory bulletins in English, Hindi, Bengali, and Odia."""
        lang_markers = {
            "en": "GOVERNMENT OF INDIA",
            "hi": "भारत सरकार",
            "bn": "ভারত সরকার",
            "or": "ଭାରତ ସରକାର"
        }
        for lang, expected_str in lang_markers.items():
            res = client.get(f"/api/bulletin?step_index=5&lang={lang}")
            assert res.status_code == 200, f"Failed for lang {lang}"
            assert expected_str in res.text, f"Expected marker '{expected_str}' in {lang} bulletin"

    def test_credibility_layer_imd_comparison_contract(self):
        res = client.get("/api/credibility/imd-comparison")
        assert res.status_code == 200
        data = res.json()
        assert "comparison_steps" in data
        assert len(data["comparison_steps"]) == 13
        assert "official_citations" in data
        summary = data["summary_metrics"]
        assert "aerotrack_mean_track_error_km" in summary
        assert "imd_bulletin_mean_track_error_km" in summary
        held_out = summary["held_out_test_comparison"]
        assert held_out["aerotrack_held_out_mean_error_km"] <= held_out["imd_bulletin_held_out_mean_error_km"], (
            "AERO-TRACK 4D held-out error should be competitive or superior to official IMD track"
        )

    def test_multi_hazard_operational_contracts(self):
        """Cyclone Fani & Yaas are Operational (200), Heat Dome & Cold Wave provide 2D grids (200), 404 on invalid."""
        # Operational storms:
        res_fani = client.get("/api/hazards/fani_2019/downscale?step_index=7")
        assert res_fani.status_code == 200
        assert res_fani.json()["event_id"] == "fani_2019"

        res_yaas = client.get("/api/hazards/yaas_2021/downscale?step_index=5")
        assert res_yaas.status_code == 200
        assert res_yaas.json()["event_id"] == "yaas_2021"

        # Multi-hazard prototypes:
        res_heat = client.get("/api/hazards/heat_dome_2020/downscale?step_index=2")
        assert res_heat.status_code == 200
        assert res_heat.json()["hazard_id"] == "heat_dome_2020"
        assert "fields" in res_heat.json()

        res_cold = client.get("/api/hazards/cold_wave_2021/downscale?step_index=2")
        assert res_cold.status_code == 200
        assert res_cold.json()["hazard_id"] == "cold_wave_2021"
        assert "fields" in res_cold.json()

        # Non-existent hazard:
        res_invalid = client.get("/api/hazards/nonexistent_event/downscale?step_index=1")
        assert res_invalid.status_code == 404
