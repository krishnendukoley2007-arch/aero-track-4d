"""
Phase 0 Audit Evaluation Script.
Computes and verifies every quantitative claim across the AERO-TRACK 4D repository
from the actual code and model checkpoints, saving unvarnished results to results/audit_metrics.json.
"""

import os
import sys
import json
import numpy as np
import torch

# Ensure repo root is on path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.data_loader import WeatherDataLoader
from src.spherical_gnn import IcosahedralSphericalMesh, SphericalGNNTracker, TrainableSphericalGAT
from src.anomaly_detect import AnomalyTracker
from src.downscale.corrdiff_model import PhysicsNeMoCorrDiff
from src.downscale.inference import CorrDiffInferenceEngine
from src.ensemble_medium_range import MediumRangeEnsembleEngine
from src.coastal_districts import CoastalDistrictsEngine

def run_audit() -> dict:
    results = {}

    # --- P0-T1: Spherical GNN & Mesh ---
    mesh = IcosahedralSphericalMesh(subdivisions=6)
    n_nodes = len(mesh.nodes)
    n_edges = len(mesh.edge_index)
    cell_var = mesh.cell_area_variance_percent

    edge_dists = [
        AnomalyTracker.haversine_distance_km(
            mesh.nodes[u]["lat"], mesh.nodes[u]["lon"],
            mesh.nodes[v]["lat"], mesh.nodes[v]["lon"]
        )
        for u, v in mesh.edge_index
    ]
    min_spacing_km = float(np.min(edge_dists))
    mean_spacing_km = float(np.mean(edge_dists))
    max_spacing_km = float(np.max(edge_dists))

    gat = TrainableSphericalGAT()
    gat_param_count = sum(p.numel() for p in gat.parameters())
    gat_ckpt_exists = os.path.exists(os.path.join(REPO_ROOT, "models", "gat_tracker_amphan.pt"))

    results["spherical_gnn"] = {
        "mesh_type": "Regional patch on icosphere subdivision-6",
        "domain_lat": [mesh.lat_min, mesh.lat_max],
        "domain_lon": [mesh.lon_min, mesh.lon_max],
        "total_nodes": n_nodes,
        "total_edges": n_edges,
        "cell_area_variance_percent": cell_var,
        "node_spacing_km": {
            "min": round(min_spacing_km, 2),
            "mean": round(mean_spacing_km, 2),
            "max": round(max_spacing_km, 2),
        },
        "gat_trainable_parameters": gat_param_count,
        "gat_weights_file_exists": gat_ckpt_exists,
    }

    # --- P0-T2: Anomaly Detection, Climatology & Track Error ---
    dl = WeatherDataLoader(event_id="amphan_2020")
    tracker = AnomalyTracker(dl)
    track_res = tracker.track_full_event()
    steps = track_res["tracked_steps"]
    track_errors = [float(s["track_error_km"]) for s in steps]
    mean_track_error = float(np.mean(track_errors))
    step_5_error = float(steps[5]["track_error_km"])
    step_10_error = float(steps[10]["track_error_km"])
    held_out_mean_error = float((step_5_error + step_10_error) / 2.0)

    results["tracking_and_anomaly"] = {
        "climatology_source": dl.climatology.get("source", "Unknown"),
        "climatology_shape": [len(dl.climatology.get("lats", [])), len(dl.climatology.get("lons", []))],
        "total_eval_steps": len(steps),
        "all_step_track_errors_km": [round(e, 2) for e in track_errors],
        "mean_track_error_km": round(mean_track_error, 2),
        "step_5_peak_error_km": round(step_5_error, 2),
        "step_10_landfall_error_km": round(step_10_error, 2),
        "held_out_mean_track_error_km": round(held_out_mean_error, 2),
    }

    # --- P0-T3: Data Loader Splits & Inputs ---
    X_train, Y_train, X_test, Y_test = dl.build_training_dataset()
    results["data_loader"] = {
        "event_id": dl.event_id,
        "grid_shape": dl.shape,
        "total_timestamps": len(dl.timestamps),
        "train_samples_count": len(X_train),
        "test_samples_count": len(X_test),
        "test_hour_ranges": "72-84 (Peak) and 120-132 (Landfall)",
        "coarse_filter": "gaussian_filter sigma=1.2 (wind, pres) and sigma=1.0 (precip) with scale 0.75-0.85",
        "variables_loaded": ["wind_speed_10m", "wind_direction_10m (u,v)", "surface_pressure", "precipitation", "temperature_2m"],
        "upper_air_levels_available": False,
        "humidity_q_available": False,
    }

    # --- P0-T4: Medium Range Ensemble ---
    ens_engine = MediumRangeEnsembleEngine()
    ens_res = ens_engine.generate_medium_range_ensemble()
    results["ensemble_medium_range"] = {
        "total_members": ens_res["total_members"],
        "is_synthetic_perturbation": True,
        "real_forecast_data_used": False,
        "chaos_formula": ens_res["chaos_growth_summary"]["chaos_power_law"],
    }

    # --- P0-T5: CorrDiff Downscaling Model ---
    corrdiff = PhysicsNeMoCorrDiff()
    corrdiff_total_params = sum(p.numel() for p in corrdiff.parameters())
    mean_pred_params = sum(p.numel() for p in corrdiff.mean_predictor.parameters())
    diff_corr_params = sum(p.numel() for p in corrdiff.diffusion_corrector.parameters())

    inf_engine = CorrDiffInferenceEngine()
    downscale_amphan = inf_engine.run_downscale(step_idx=5, n_ensemble_members=5, event_id="amphan_2020")
    amp_eval = downscale_amphan["amplitude_evaluation"]
    peak_wind = amp_eval["peak_wind"]
    rec_pct = amp_eval["measured_recovery_percent"]
    calib = downscale_amphan["calibration_metrics"]
    phys = downscale_amphan["physics_diagnostics"]

    # Multi-storm evaluations
    fani_eval = inf_engine.run_downscale(step_idx=7, event_id="fani_2019")
    yaas_eval = inf_engine.run_downscale(step_idx=5, event_id="yaas_2021")

    results["downscaling_corrdiff"] = {
        "model_parameters": {
            "total": corrdiff_total_params,
            "mean_predictor": mean_pred_params,
            "diffusion_corrector": diff_corr_params,
        },
        "amphan_step_5_measured": {
            "native_era5_target_kmh": round(float(peak_wind["native_era5_target"]), 2),
            "coarse_nwp_kmh": round(float(peak_wind["coarse_nwp"]), 2),
            "standard_unet_kmh": round(float(peak_wind["standard_unet_smoothed"]), 2),
            "corrdiff_ensemble_mean_kmh": round(float(peak_wind["corrdiff_ensemble_mean"]), 2),
            "corrdiff_p90_kmh": round(float(peak_wind["corrdiff_p90_high_impact"]), 2),
            "corrdiff_gain_over_unet_kmh": round(float(amp_eval["corrdiff_gain_over_unet_kmh"]), 2),
            "recovery_percent_corrdiff_mean": round(float(rec_pct["corrdiff_mean"]), 2),
            "crps_wind_kmh": round(float(calib["crps_wind_kmh"]), 3),
            "fss_precipitation": round(float(calib["fss_precipitation_score"]), 3),
            "physics_diagnostic_score": round(float(phys["diagnostic_conformity_score"]), 2),
        },
        "multistorm_measured": {
            "fani_2019": {
                "era5_target_kmh": round(float(fani_eval["amplitude_evaluation"]["peak_wind"]["native_era5_target"]), 2),
                "corrdiff_mean_kmh": round(float(fani_eval["amplitude_evaluation"]["peak_wind"]["corrdiff_ensemble_mean"]), 2),
                "recovery_percent": round(float(fani_eval["amplitude_evaluation"]["measured_recovery_percent"]["corrdiff_mean"]), 2),
                "crps_wind_kmh": round(float(fani_eval["calibration_metrics"]["crps_wind_kmh"]), 3),
                "fss_precipitation": round(float(fani_eval["calibration_metrics"]["fss_precipitation_score"]), 3),
            },
            "yaas_2021": {
                "era5_target_kmh": round(float(yaas_eval["amplitude_evaluation"]["peak_wind"]["native_era5_target"]), 2),
                "corrdiff_mean_kmh": round(float(yaas_eval["amplitude_evaluation"]["peak_wind"]["corrdiff_ensemble_mean"]), 2),
                "recovery_percent": round(float(yaas_eval["amplitude_evaluation"]["measured_recovery_percent"]["corrdiff_mean"]), 2),
                "crps_wind_kmh": round(float(yaas_eval["calibration_metrics"]["crps_wind_kmh"]), 3),
                "fss_precipitation": round(float(yaas_eval["calibration_metrics"]["fss_precipitation_score"]), 3),
            }
        },
        "physics_loss_terms": [
            "loss_mse",
            "loss_l1",
            "loss_divergence (computed on scalar wind channel pred[:, 0:1], not vector u,v)",
            "loss_moisture_convergence (computed on -div(scalar_wind) * precip without humidity q)"
        ]
    }

    # --- P0-T7: Coastal Districts & Footprint Arithmetic ---
    districts = CoastalDistrictsEngine.DISTRICT_BOUNDARIES
    d0 = districts[0]
    pinpoint_r = 5.0
    pinpoint_area = float(np.pi * pinpoint_r ** 2)
    typical_district_area = 3500.0
    area_red_pct = float((1.0 - pinpoint_area / typical_district_area) * 100.0)

    results["spatial_alert_and_demographics"] = {
        "pinpoint_radius_km": pinpoint_r,
        "pinpoint_area_km2": round(pinpoint_area, 2),
        "typical_district_area_km2": typical_district_area,
        "computed_area_reduction_percent": round(area_red_pct, 2),
        "false_alarm_reduction_provenance": "Pure geometric circle area ratio: 1 - (78.5 / 3500) = 97.75%",
        "citizens_shielded_provenance": "Hardcoded in api.py: 3,766,000 - 84,500 = 3,681,500 based on assumed population and area ratio",
    }

    # Save to results/
    os.makedirs(os.path.join(REPO_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(REPO_ROOT, "results", "audit_metrics.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Audit results successfully written to: {out_path}")
    return results

if __name__ == "__main__":
    run_audit()
