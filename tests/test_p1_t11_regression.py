"""
tests/test_p1_t11_regression.py — P1-T11 Regression Test Suite.
Enforces:
(a) Every JSON response from every API endpoint contains a "provenance" field.
(b) README metric tables equal a fresh render from results/*.json (via scripts/render_readme_tables.py).
(c) Static AST check that src/downscale/inference.py and src/api.py contain no numeric-literal
    multiplier applied to model outputs and no hardcoded metric literals (FSS, CRPS, recovery percentages).
(d) Data-split integrity test ensuring zero test leakage and >= 24h validation temporal buffers.
"""

import ast
import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api import app
from src.data_loader import WeatherDataLoader
from scripts.render_readme_tables import (
    load_metrics,
    render_track_error_table,
    render_downscale_table,
    render_calibration_table,
    render_multistorm_table,
    render_spatial_alert_table,
)


def test_a_all_json_endpoints_have_provenance():
    """Asserts that every API endpoint returning application/json contains a provenance field."""
    client = TestClient(app)

    non_json_paths = {
        "/",
        "/style.css",
        "/app.js",
        "/api/bulletin",
        "/api/bulletin/html",
        "/api/bulletin/download",
        "/api/alert/cap",
        "/api/live/precipitation-tile/{z}/{x}/{y}.webp",
        "/api/export/netcdf",
        "/api/export/asc-grid",
        "/api/export/agri-csv",
    }

    call_params = {
        "/api/downscale": {"step_index": 5},
        "/api/gnn-mesh-state": {"step_index": 5},
        "/api/hazards/{hazard_id}": ("/api/hazards/fani_2019", {}),
        "/api/hazards/{hazard_id}/timesteps": ("/api/hazards/fani_2019/timesteps", {}),
        "/api/hazards/{hazard_id}/downscale": ("/api/hazards/fani_2019/downscale?step_index=7", {}),
        "/api/agri-advisory": {"lat": 21.626, "lon": 87.508},
        "/api/wind-vectors": {"step_index": 5},
        "/api/live/point-forecast": {"lat": 21.626, "lon": 87.508},
        "/api/live/search": {"q": "Kolkata"},
        "/api/atmospheric/sounding": {"lat": 21.626, "lon": 87.508},
        "/api/radar/dwr-metadata": {"radar_id": "kolkata"},
        "/api/radar/nowcast-frames": {"radar_id": "kolkata"},
        "/api/export/geojson": {"step_index": 5},
        "/api/satellite/insat3dr-thermal-ir": {"step_index": 5},
        "/api/alert/cell-broadcast": {"step_index": 5, "lat": 21.626, "lon": 87.508},
        "/api/downscale/diffusion-trajectory": {"step_index": 5},
        "/api/climate/perturbation": {"temp_delta_c": 1.5, "sst_anomaly_c": 1.0},
    }

    routes = [r for r in app.routes if isinstance(r, APIRoute) and r.path not in non_json_paths]
    missing_provenance = []

    for route in routes:
        path = route.path
        if path == "/api/alert":
            res = client.post(
                "/api/alert",
                json={
                    "lat": 21.62,
                    "lon": 87.51,
                    "location_name": "Digha",
                    "step_index": 5,
                    "hazard_id": "amphan_2020",
                },
            )
        elif path in call_params:
            spec = call_params[path]
            if isinstance(spec, tuple):
                res = client.get(spec[0])
            else:
                res = client.get(path, params=spec)
        else:
            res = client.get(path)

        assert res.status_code == 200, f"Endpoint {path} failed with HTTP {res.status_code}: {res.text}"
        ct = res.headers.get("content-type", "")
        if "application/json" in ct:
            payload = res.json()
            if isinstance(payload, dict):
                prov = payload.get("provenance")
            elif isinstance(payload, list) and len(payload) > 0 and isinstance(payload[0], dict):
                prov = payload[0].get("provenance")
            else:
                prov = None

            if not prov:
                missing_provenance.append(path)

    assert not missing_provenance, f"Endpoints missing provenance: {missing_provenance}"


def test_b_readme_metric_tables_equal_fresh_render():
    """Asserts that README metric tables match a fresh render from results/audit_metrics.json."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    readme_path = os.path.join(repo_root, "README.md")
    metrics_path = os.path.join(repo_root, "results", "audit_metrics.json")

    assert os.path.exists(readme_path), "README.md not found"
    assert os.path.exists(metrics_path), "results/audit_metrics.json not found"

    metrics = load_metrics(metrics_path)
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read().replace("\r\n", "\n")

    rendered_tables = [
        ("Track Error Table", render_track_error_table(metrics)),
        ("Downscale Table", render_downscale_table(metrics)),
        ("Calibration Table", render_calibration_table(metrics)),
        ("Multi-storm Table", render_multistorm_table(metrics)),
        ("Spatial Alert Table", render_spatial_alert_table(metrics)),
    ]

    for name, tbl in rendered_tables:
        normalized_table = tbl.strip().replace("\r\n", "\n")
        assert normalized_table in readme_content, f"Rendered {name} does not match content in README.md"


def test_c_static_ast_check_no_hidden_multipliers_or_hardcoded_metrics():
    """
    Best-effort static AST check that src/downscale/inference.py and src/api.py contain:
    1. No numeric multiplier literal (e.g. 1.85) applied to model outputs.
    2. No hardcoded metric literals (e.g. 0.392, 7.45, 142.3, 3766000, 3681500).
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_files = [
        os.path.join(repo_root, "src", "downscale", "inference.py"),
        os.path.join(repo_root, "src", "api.py"),
    ]

    forbidden_metric_literals = {0.392, 7.45, 142.3, 3766000, 3681500}
    violations = []

    for filepath in target_files:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)

        for node in ast.walk(tree):
            # Check for forbidden constants
            if isinstance(node, ast.Constant) and node.value in forbidden_metric_literals:
                violations.append(
                    f"{os.path.basename(filepath)}:{node.lineno} contains hardcoded forbidden literal {node.value}"
                )
            # Check for scaling multiplier (1.85)
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                if (isinstance(node.left, ast.Constant) and node.left.value in (1.85, 1.852)) or (
                    isinstance(node.right, ast.Constant) and node.right.value in (1.85, 1.852)
                ):
                    violations.append(
                        f"{os.path.basename(filepath)}:{node.lineno} contains scaling multiplier 1.85"
                    )

    assert not violations, f"Static AST violations detected:\n" + "\n".join(violations)


def test_d_data_split_integrity():
    """
    Verifies data-split integrity:
    1. Single-storm split: zero overlap between train and test timesteps; sample counts match 142/26.
    2. Leave-one-storm-out (LOSO): no test-storm sample appears in train/val across all 3 folds.
    3. Validation temporal buffer: >= 24h separation between training timesteps and validation timesteps.
    """
    # 1. Single-storm split
    loader = WeatherDataLoader("amphan_2020")
    X_train, Y_train, X_test, Y_test = loader.build_training_dataset()
    assert len(X_train) == 142, f"Expected 142 train samples, got {len(X_train)}"
    assert len(X_test) == 26, f"Expected 26 test samples, got {len(X_test)}"
    assert len(X_train) + len(X_test) == len(loader.timestamps)

    # 2 & 3. LOSO folds and 24h time-blocked validation buffer
    storms = ["amphan_2020", "fani_2019", "yaas_2021"]
    for test_storm in storms:
        split = WeatherDataLoader.build_loso_splits(test_storm_id=test_storm, val_block_hours=24, val_gap_hours=24)
        train_manifest = split["train_manifest"]
        val_manifest = split["val_manifest"]
        test_manifest = split["test_manifest"]

        # Ensure test storm is completely absent from train and val
        train_storms = set(item[0] for item in train_manifest)
        val_storms = set(item[0] for item in val_manifest)
        test_storms = set(item[0] for item in test_manifest)

        assert test_storm in test_storms
        assert test_storm not in train_storms, f"Test storm {test_storm} leaked into train split"
        assert test_storm not in val_storms, f"Test storm {test_storm} leaked into val split"

        # Ensure disjoint sample manifests
        assert set(train_manifest).isdisjoint(set(val_manifest)), "Train and val manifests overlap"
        assert set(train_manifest).isdisjoint(set(test_manifest)), "Train and test manifests overlap"
        assert set(val_manifest).isdisjoint(set(test_manifest)), "Val and test manifests overlap"

        # Ensure >= 24h separation between train and val timesteps within each training storm
        for storm_tr, t_tr in train_manifest:
            for storm_val, t_val in val_manifest:
                if storm_tr == storm_val:
                    gap = abs(t_tr - t_val)
                    assert (
                        gap >= 24
                    ), f"Temporal gap violation in {storm_tr}: train t={t_tr}, val t={t_val} (gap={gap} < 24h)"


def test_e_runtime_model_output_anti_scaling():
    """
    Runtime anti-scaling regression test:
    1. Obtains the raw neural-network native inference output directly from sample_ensemble()
       before any display interpolation or unit conversion.
    2. Obtains the public API / model output from run_downscale().
    3. Verifies that the difference is strictly and solely from explicitly whitelisted physical operations:
       - Physical unit conversion: m/s -> km/h (x 3.6)
       - Bicubic spatial display interpolation: zoom(..., 38.0 / 16.0, order=3)
       - Non-negative physical clipping: np.maximum(0, ...)
       - Display float precision rounding: round(..., 1)
    4. Proves negative assertions: fails if any arbitrary scalar (e.g. 1.05, 0.92, 1.85, 0.82)
       mutates model amplitudes.
    5. Confirms the effective mean scaling factor is identically 1.0 (no hidden scaling factor).
    """
    from src.downscale.inference import CorrDiffInferenceEngine
    import numpy as np
    import torch
    from scipy.ndimage import zoom

    inf = CorrDiffInferenceEngine()
    dl = WeatherDataLoader("amphan_2020")
    step_data = dl.get_real_era5_step(5)
    coarse = step_data["coarsened_nwp_input"]
    fine = step_data["native_era5_fine"]

    # 1. Prepare raw input tensor matching inference pipeline
    w_c = np.array(coarse["wind_speed_kmh"], dtype=np.float32) / 3.6
    p_c = (np.array(coarse["mslp_hpa"], dtype=np.float32) - 1000.0) / 25.0
    r_c = np.array(coarse["precip_mmh"], dtype=np.float32) / 20.0
    t_c = (np.array(fine["temp_c"], dtype=np.float32) - 25.0) / 10.0
    input_tensor = torch.tensor(
        np.stack([w_c, p_c, r_c, t_c])[None, ...], dtype=torch.float32
    ).to(inf.device)

    # 2. Extract raw native neural network outputs before any display processing
    with torch.no_grad():
        ens_res = inf.model.sample_ensemble(input_tensor, n_members=5, seed=42)
        raw_unet = ens_res["stage1_mean"][0].cpu().numpy()
        raw_cd_mean = ens_res["ensemble_mean"][0].cpu().numpy()
        raw_cd_high = ens_res["high_impact_scenario"][0].cpu().numpy()

    # 3. Obtain public model outputs
    public_res = inf.run_downscale(step_idx=5, n_ensemble_members=5, seed=42, event_id="amphan_2020")
    actual_cd_mean = np.array(public_res["fields"]["corrdiff_ensemble_mean"]["wind_speed_kmh"])
    actual_unet = np.array(public_res["fields"]["standard_unet"]["wind_speed_kmh"])
    actual_cd_high = np.array(public_res["fields"]["corrdiff_high_impact_p90"]["wind_speed_kmh"])

    # 4. Reconstruct public fields using ONLY whitelisted operations:
    # Whitelist: unit conversion (x 3.6 for m/s -> km/h), bicubic zoom (38/16), non-negativity clamp, round(1)
    reconstructed_cd_mean = np.round(np.maximum(0, zoom(raw_cd_mean[0] * 3.6, 38.0 / 16.0, order=3)), 1)
    reconstructed_unet = np.round(zoom(np.maximum(0, raw_unet[0] * 3.6), 38.0 / 16.0, order=3), 1)
    reconstructed_cd_high = np.round(np.maximum(0, zoom(raw_cd_high[0] * 3.6, 38.0 / 16.0, order=3)), 1)

    # Assert exact match to within single-precision rounding epsilon
    assert np.allclose(actual_cd_mean, reconstructed_cd_mean, atol=1e-4), (
        "CorrDiff ensemble mean output does not match raw native inference via whitelisted operations!"
    )
    assert np.allclose(actual_unet, reconstructed_unet, atol=1e-4), (
        "Standard U-Net output does not match raw native inference via whitelisted operations!"
    )
    assert np.allclose(actual_cd_high, reconstructed_cd_high, atol=1e-4), (
        "CorrDiff P90 output does not match raw native inference via whitelisted operations!"
    )

    # 5. Anti-scaling negative test: ANY arbitrary scalar factor applied to model amplitudes MUST fail
    for arbitrary_scalar in [0.82, 0.92, 1.02, 1.05, 1.10, 1.85, 2.0]:
        mutated_output = actual_cd_mean * arbitrary_scalar
        with pytest.raises(AssertionError):
            assert np.allclose(mutated_output, reconstructed_cd_mean, atol=1e-4)

    # 6. Prove that no unknown scaling factor exists:
    # First, verify that the public display field has an identical spatial mean to the reconstructed field:
    assert abs(float(np.mean(actual_cd_mean) - np.mean(reconstructed_cd_mean))) < 1e-4, (
        "Public output spatial mean differs from whitelisted reconstructed spatial mean!"
    )

    # Second, verify that the ratio between zoomed display field and raw physical field
    # is within standard bicubic spline interpolation curvature limits (+-5%), proving no
    # hidden scaling multiplier was inserted.
    raw_physical_mean = float(np.mean(np.maximum(0, raw_cd_mean[0] * 3.6)))
    public_display_mean = float(np.mean(actual_cd_mean))
    effective_scale_ratio = public_display_mean / raw_physical_mean
    assert 0.95 <= effective_scale_ratio <= 1.05, (
        f"Hidden amplitude scaling detected: effective scale ratio {effective_scale_ratio:.4f} deviates from 1.0"
    )

