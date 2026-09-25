"""
Automated Smoke Test Suite for AERO-TRACK 4D (SIH 26078).
Verifies that all core API endpoints respond with HTTP 200 and valid payloads.
Can run standalone against a running server or via FastAPI TestClient.
"""

import sys
import json
import urllib.request

BASE_URL = "http://127.0.0.1:8000"

ENDPOINTS = [
    ("GET", "/", None),
    ("GET", "/api/status", ["status", "organization", "data_sources"]),
    ("GET", "/api/track", ["event_meta", "total_steps", "tracked_steps"]),
    ("GET", "/api/track-error", ["mean_track_error_km", "table"]),
    ("GET", "/api/downscale?step_index=5", ["fields", "power_spectrum", "physics_diagnostics"]),
    ("GET", "/api/spherical-mesh", ["type", "features"]),
    ("GET", "/api/gnn-mesh-state?step_index=5", ["step_index", "centroid", "gnn_stage1"]),
    ("GET", "/api/medium-range-ensemble", ["total_members", "lead_times", "cone_geojson"]),
    ("GET", "/api/coastal-districts", ["type", "features"]),
    ("GET", "/api/wind-vectors?step_index=5", ["step_index", "vectors"]),
    ("POST", "/api/alert", ["alert_tier", "predicted_local_wind_kmh", "action_directive"]),
    ("GET", "/api/bulletin?step_index=5", None),
    ("GET", "/api/live/global-anomalies", ["status", "active_anomalies", "total_basins_monitored"]),
    ("GET", "/api/live/point-forecast?lat=25.76&lon=-80.19", ["status", "current_conditions", "medium_range_ensemble_10day"]),
    ("GET", "/api/live/search?q=Tokyo", ["results"]),
    ("GET", "/api/credibility/imd-comparison", ["status", "event_id", "official_citations", "summary_metrics", "comparison_steps"]),
    ("GET", "/api/historical/verification", ["benchmark_event", "key_metrics", "two_gap_analysis"]),
    ("GET", "/api/hazards", None),
    ("GET", "/api/hazards/fani_2019/timesteps", ["hazard_type", "tracked_steps"]),
    ("GET", "/api/hazards/fani_2019/downscale?step_index=7", ["fields", "calibration_metrics"]),
    ("GET", "/api/hazards/yaas_2021/timesteps", ["hazard_type", "tracked_steps"]),
    ("GET", "/api/hazards/yaas_2021/downscale?step_index=5", ["fields", "calibration_metrics"]),
    ("GET", "/api/hazards/heat_dome_2020/timesteps", ["hazard_type", "tracked_steps"]),
    ("GET", "/api/hazards/heat_dome_2020/downscale?step_index=2", ["fields", "amplitude_evaluation"]),
    ("GET", "/api/hazards/cold_wave_2021/timesteps", ["hazard_type", "tracked_steps"]),
    ("GET", "/api/hazards/cold_wave_2021/downscale?step_index=2", ["fields", "amplitude_evaluation"]),
    ("GET", "/api/alert/cap?lat=21.62&lon=87.51", None),
    ("GET", "/api/scientific/metpy-audit", ["coriolis_parameter_s-1", "rossby_deformation_radius_km", "kolmogorov_inertial_subrange"]),
    ("GET", "/api/agri-advisory?lat=21.62&lon=87.51&hazard_type=cyclone&metric_val=102.1", ["threat_metric", "actionable_protocols", "economic_shield_estimate"]),
    ("GET", "/api/export/netcdf", None),
    ("GET", "/api/export/asc-grid", None),
    ("GET", "/api/export/geojson", ["type", "features", "metadata"]),
    ("GET", "/api/export/agri-csv", None),
]


def run_tests():
    print("=" * 60)
    print("AERO-TRACK 4D SMOKE TEST SUITE")
    print("=" * 60)

    # Pre-flight check: ensure server is ready
    import time
    for _ in range(10):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/status", timeout=2) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.5)

    passed = 0
    failed = 0

    for method, path, required_keys in ENDPOINTS:
        url = f"{BASE_URL}{path}"
        req_data = None
        headers = {}

        if method == "POST":
            payload = {
                "lat": 21.626,
                "lon": 87.508,
                "location_name": "Digha Coast (West Bengal)",
                "step_index": 5
            }
            req_data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                raw = resp.read()

                if status == 200:
                    if required_keys:
                        body = raw.decode("utf-8", errors="ignore")
                        data = json.loads(body)
                        missing = [k for k in required_keys if k not in data]
                        if missing:
                            print(f"[FAIL] {method} {path} - Missing keys: {missing}")
                            failed += 1
                            continue

                    print(f"[PASS] {method} {path} (HTTP {status})")
                    passed += 1
                else:
                    print(f"[FAIL] {method} {path} - Unexpected status: {status}")
                    failed += 1
        except Exception as e:
            print(f"[FAIL] {method} {path} - Exception: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
