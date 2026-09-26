"""
Export all AERO-TRACK 4D API responses from live server at http://127.0.0.1:8000
into docs/data/ for zero-latency static GitHub Pages deployment.
"""

import os
import sys
import json
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
DATA_DIR = os.path.join(DOCS_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

ENDPOINTS = [
    ("/api/status", "status.json"),
    ("/api/track", "track.json"),
    ("/api/track-error", "track_error.json"),
    ("/api/spherical-mesh", "spherical_mesh.json"),
    ("/api/medium-range-ensemble", "medium_range_ensemble.json"),
    ("/api/coastal-districts", "coastal_districts.json"),
    ("/api/scientific/metpy-audit", "metpy_audit.json"),
    ("/api/historical/verification", "historical_verification.json"),
    ("/api/credibility/imd-comparison", "imd_comparison.json"),
    ("/api/live/global-anomalies", "global_anomalies.json"),
    ("/api/live/active-storms", "active_storms.json"),
    ("/api/live/pressure-field", "pressure_field.json"),
    ("/api/live/global-wind-vectors", "global_wind_vectors.json"),
    ("/api/hazards/fani_2019/timesteps", "hazards_fani_timesteps.json"),
    ("/api/hazards/fani_2019/downscale?step_index=7", "hazards_fani_downscale.json"),
    ("/api/hazards/yaas_2021/timesteps", "hazards_yaas_timesteps.json"),
    ("/api/hazards/yaas_2021/downscale?step_index=5", "hazards_yaas_downscale.json"),
    ("/api/hazards/heat_dome_2020/timesteps", "hazards_heat_dome_timesteps.json"),
    ("/api/hazards/heat_dome_2020/downscale?step_index=2", "hazards_heat_dome_downscale.json"),
    ("/api/hazards/cold_wave_2021/timesteps", "hazards_cold_wave_timesteps.json"),
    ("/api/hazards/cold_wave_2021/downscale?step_index=2", "hazards_cold_wave_downscale.json"),
]

# Add timesteps 0 to 12 for Amphan
for step in range(13):
    ENDPOINTS.append((f"/api/downscale?step_index={step}", f"downscale_step_{step}.json"))
    ENDPOINTS.append((f"/api/wind-vectors?step_index={step}", f"wind_vectors_step_{step}.json"))
    ENDPOINTS.append((f"/api/gnn-mesh-state?step_index={step}", f"gnn_mesh_step_{step}.json"))
    ENDPOINTS.append((
        f"/api/bulletin?step_index={step}&lat=21.626&lon=87.508&loc_name=Digha%20Coast%20(West%20Bengal)",
        f"bulletin_step_{step}.json"
    ))

print(f"Exporting {len(ENDPOINTS)} endpoints to {DATA_DIR}...")
total_bytes = 0

for url_path, filename in ENDPOINTS:
    full_url = BASE_URL + url_path
    target_path = os.path.join(DATA_DIR, filename)
    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "AERO-TRACK-Exporter/1.0"})
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            with open(target_path, "wb") as f:
                f.write(content)
            total_bytes += len(content)
            print(f"  [OK] {filename} ({len(content):,} bytes)")
    except Exception as e:
        print(f"  [FAIL] {url_path} -> {filename}: {e}")

print(f"\nSuccessfully exported {len(ENDPOINTS)} files ({total_bytes / (1024*1024):.2f} MB).")
