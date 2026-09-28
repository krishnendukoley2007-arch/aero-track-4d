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
