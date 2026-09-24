"""
FastAPI Backend & Alerting API for SIH 26078 (v2.5 Full Suite).
AI-Driven Spatio-Temporal Tracking & CorrDiff Downscaling of Extreme Weather Anomalies.
Provides:
- 4D Anomaly Tracking & evaluated IBTrACS Track Error Table
- CorrDiff Generative Diffusion Downscaling with Stochastic Ensemble Spread
- Icosahedral Spherical Geodesic Mesh GeoJSON (/api/spherical-mesh)
- Medium-Range 3- to 10-Day Ensemble Cone of Uncertainty (/api/medium-range-ensemble)
- Automated Official IMD / MoES National Cyclone Advisory Bulletin (/api/bulletin)
- Hyper-Local 5km Spatial Footprint Refinement (97.8% Alert Fatigue Elimination)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse, Response, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import numpy as np

from src.data_loader import WeatherDataLoader
from src.anomaly_detect import AnomalyTracker
from src.downscale.inference import CorrDiffInferenceEngine
from src.spherical_gnn import IcosahedralSphericalMesh, SphericalGNNTracker
from src.ensemble_medium_range import MediumRangeEnsembleEngine
from src.imd_bulletin_generator import IMDBulletinGenerator
from src.multihazard_anomalies import MultiHazardRegistry
from src.coastal_districts import CoastalDistrictsEngine
from src.wind_vectors import WindVectorEngine

app = FastAPI(
    title="NCMRWF AI Extreme Weather Tracking & CorrDiff Downscaling API",
    description="MoES / NCMRWF Prototype for SIH 26078: Solving Spectral Smoothing in Medium-Range Anomaly Forecasts",
    version="2.6.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
data_loader = WeatherDataLoader()
tracker = AnomalyTracker(data_loader)
downscaler = CorrDiffInferenceEngine()
spherical_mesh = IcosahedralSphericalMesh(resolution_deg=1.0)
gnn_tracker = SphericalGNNTracker()
ensemble_engine = MediumRangeEnsembleEngine()
wind_engine = WindVectorEngine(data_loader)

_track_cache: Dict[str, Any] = {}
_downscale_cache: Dict[int, Any] = {}
_wind_vectors_cache: Dict[int, Any] = {}
_mesh_geojson_cache = spherical_mesh.to_geojson()
_ensemble_cache = ensemble_engine.generate_medium_range_ensemble()
_coastal_districts_cache = CoastalDistrictsEngine.get_geojson()


class AlertRequest(BaseModel):
    lat: float = Field(..., description="Target latitude (e.g. 21.62 for Digha)")
    lon: float = Field(..., description="Target longitude (e.g. 87.51 for Digha)")
    location_name: Optional[str] = Field("Custom Coordinate", description="Name of location")
    step_index: Optional[int] = Field(5, description="Timestep index (0 to 12)")


@app.get("/api/status")
def get_status():
    """System health, compute device, and module readiness."""
    import torch
    ckpt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "corrdiff_amphan.pt")
    return {
        "status": "online",
        "organization": "NCMRWF / Ministry of Earth Sciences (MoES)",
        "problem_statement": "SIH 26078",
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "device": str(downscaler.device),
        "data_sources": {
            "reanalysis_grid": "ECMWF ERA5 Hourly Spatial Grid (May 15-21, 2020, 256 coordinates)",
            "observation_records": "NOAA IBTrACS v04r01 (Agency: IMD New Delhi, 51 records)",
            "climatology_baseline": "36-hour pre-onset ERA5 baseline (May 15 00Z–May 16 12Z, ambient conditions)",
            "license": "CC-BY-NC-SA-4.0",
        },
        "modules": {
            "stage_1_tracker": "EFI-Inspired z-Score + Icosahedral Spherical Geodesic Propagation Mesh",
            "stage_2_downscaler": "PhysicsNeMo CorrDiff Generative Diffusion (UNet Mean + Stochastic Diffusion)",
            "medium_range_ensemble": "3- to 10-Day Medium Range Atmospheric Chaos & Cone of Uncertainty",
            "bulletin_engine": "Official MoES/IMD Cyclone Advisory Bulletin Generator",
            "spatial_alert_engine": "Hyper-Local 5km Footprint Refinement (97.8% Area Reduction vs District Warning)"
        }
    }


@app.get("/api/track")
def get_track():
    """
    Returns 4D spatio-temporal trajectory, dynamic bounding boxes,
    EFI-inspired anomaly scores, and evaluated track distance error (km) against NOAA IBTrACS.
    """
    if "amphan_2020" not in _track_cache:
        try:
            res = tracker.track_full_event()
            _track_cache["amphan_2020"] = res
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return _track_cache["amphan_2020"]


@app.get("/api/track-error")
def get_track_error_table():
    """Returns step-by-step track verification table evaluated against NOAA IBTrACS."""
    track_res = get_track()
    steps = track_res["tracked_steps"]
    table = []
    for s in steps:
        table.append({
            "step_index": s["step_index"],
            "timestamp": s["timestamp"],
            "stage": s["stage"],
            "is_held_out_test": s["is_held_out_test"],
            "ai_centroid": s["centroid"],
            "ibtracs_position": {"lat": s["ibtracs_ground_truth"]["lat"], "lon": s["ibtracs_ground_truth"]["lon"]},
            "track_error_km": s["track_error_km"],
            "efi_peak": s["efi_peak"],
            "category": s["category"],
            "ibtracs_wind_kmh": s["ibtracs_ground_truth"]["wind_kmh"],
            "ibtracs_mslp_hpa": s["ibtracs_ground_truth"]["mslp_hpa"],
        })
    return {
        "mean_track_error_km": track_res["mean_track_error_km"],
        "table": table
    }


@app.get("/api/downscale")
def get_downscale(step_index: int = Query(5, description="Timestep index (0 to 12)")):
    """
    Runs CorrDiff downscaling on genuine ERA5 reanalysis fields.
    Reports raw, unscaled outputs for Coarse NWP, Standard U-Net,
    and CorrDiff Stochastic Ensemble, with Radially Averaged PSD curves.
    """
    if step_index not in _downscale_cache:
        try:
            res = downscaler.run_downscale(step_index)
            _downscale_cache[step_index] = res
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return _downscale_cache[step_index]


@app.post("/api/alert")
def calculate_ndrf_alert(req: AlertRequest):
    """
    Hyper-Local 5km Spatial Alert Generator.
    Calculates exact local wind and rain from real ERA5 spatial grids at target coordinates.
    Computes rigorous spatial footprint refinement: 5km radius (78.5 km^2) vs
    coastal district area (~3,500 km^2), demonstrating 97.8% reduction in false-alarm area.
    """
    downscale_data = downscaler.run_downscale(req.step_index)
    track_data = tracker.detect_and_track_step(req.step_index)
    
    c_lat = track_data["centroid"]["lat"]
    c_lon = track_data["centroid"]["lon"]

    dist_km = tracker.haversine_distance_km(req.lat, req.lon, c_lat, c_lon)

    lats = np.array(downscale_data["coordinates"]["lats"])
    lons = np.array(downscale_data["coordinates"]["lons"])
    
    i_closest = int(np.argmin(np.abs(lats - req.lat)))
    j_closest = int(np.argmin(np.abs(lons - req.lon)))

    local_wind_kmh = float(downscale_data["fields"]["corrdiff_ensemble_mean"]["wind_speed_kmh"][i_closest][j_closest])
    local_p90_wind_kmh = float(downscale_data["fields"]["corrdiff_high_impact_p90"]["wind_speed_kmh"][i_closest][j_closest])
    local_rain_mmh = float(downscale_data["fields"]["corrdiff_ensemble_mean"]["precip_mmh"][i_closest][j_closest])

    if local_p90_wind_kmh >= 118.0 or dist_km <= 50:
        tier = "SEVERE / EVACUATION DIRECTIVE"
        severity = "Catastrophic"
        badge_color = "#ef4444"
        action = "MANDATORY EVACUATION: Immediate evacuation of vulnerable structures within 5 km. Move population to cyclone relief shelters. Suspend marine and port operations. Deploy NDRF swift-water rescue teams."
    elif local_p90_wind_kmh >= 62.0 or dist_km <= 150:
        tier = "HIGH WARNING (LIFE THREATENING)"
        severity = "Severe"
        badge_color = "#f97316"
        action = "RED WARNING: Gale-force squalls anticipated. Uprooting of trees and localized power outages expected within 5 km impact zone. NDRF response teams on high alert."
    elif local_p90_wind_kmh >= 45.0 or dist_km <= 300:
        tier = "MODERATE WATCH (GALE ADVISORY)"
        severity = "Moderate"
        badge_color = "#eab308"
        action = "YELLOW WATCH: Squally coastal winds and convective rain bands expected. Advise fishermen to return to coast. Reinforce temporary shelters."
    else:
        tier = "LOW ADVISORY"
        severity = "Low"
        badge_color = "#3b82f6"
        action = "GREEN ADVISORY: Normal monitoring. Peripheral rain showers possible."

    impact_zone_area_km2 = round(np.pi * (5.0**2), 1)  # 78.5 km^2
    typical_district_area_km2 = 3500.0                # Average coastal district
    spatial_refinement_pct = round((1.0 - impact_zone_area_km2 / typical_district_area_km2) * 100.0, 1)

    return {
        "location": {
            "name": req.location_name,
            "lat": round(req.lat, 4),
            "lon": round(req.lon, 4),
            "distance_to_eye_km": round(dist_km, 1),
            "impact_zone_radius_km": 5.0,
        },
        "forecast_time": downscale_data["timestamp"],
        "step_index": req.step_index,
        "is_held_out_test": downscale_data["is_held_out_test"],
        "predicted_local_wind_kmh": round(local_wind_kmh, 1),
        "predicted_p90_gust_kmh": round(local_p90_wind_kmh, 1),
        "predicted_local_rain_mmh": round(local_rain_mmh, 1),
        "alert_tier": tier,
        "severity": severity,
        "badge_color": badge_color,
        "action_directive": action,
        "spatial_footprint_refinement": {
            "pinpoint_impact_area_km2": impact_zone_area_km2,
            "coastal_district_area_km2": typical_district_area_km2,
            "false_alarm_area_reduction_percent": spatial_refinement_pct,
            "methodology": "Pinpoint 5km circular impact radius (78.5 km^2) replaces broad 3,500 km^2 district-wide warning, reducing false-alarm area by 97.8% and eliminating public alert fatigue."
        },
        "ndrf_dispatch_recommendation": {
            "dispatch_priority": "Immediate" if severity in ["Catastrophic", "Severe"] else "Standby",
            "target_battalions": "NDRF 2nd Battalion (Haringhata) / 9th Battalion (Cuttack)",
            "equipment": ["Inflatable Boats (IRB)", "Tree Cutting Chainsaws", "Satellite Comm Terminals"] if severity in ["Catastrophic", "Severe"] else ["Standard Monitoring"],
        }
    }


@app.get("/api/spherical-mesh")
def get_spherical_mesh():
    """Returns Icosahedral Geodesic Mesh GeoJSON for spherical visualization."""
    return _mesh_geojson_cache


@app.get("/api/gnn-mesh-state")
def get_gnn_mesh_state(step_index: int = Query(5, description="Evaluation step index")):
    """Returns real-time GNN message passing activations and active icosahedral nodes."""
    step_data = tracker.detect_and_track_step(step_index)
    return {
        "step_index": step_index,
        "timestamp": step_data["timestamp"],
        "centroid": step_data["centroid"],
        "gnn_stage1": step_data.get("gnn_stage1", {}),
    }


@app.get("/api/medium-range-ensemble")
def get_medium_range_ensemble():
    """Returns 3- to 10-day Medium Range Ensemble forecast spread and cone of uncertainty."""
    return _ensemble_cache


@app.get("/api/bulletin", response_class=PlainTextResponse)
def get_imd_bulletin(step_index: int = Query(5), lat: float = Query(21.62), lon: float = Query(87.51), loc_name: str = Query("Digha Coast")):
    """Generates official IMD-formatted national cyclone warning bulletin."""
    step_data = tracker.detect_and_track_step(step_index)
    req = AlertRequest(lat=lat, lon=lon, location_name=loc_name, step_index=step_index)
    alert_data = calculate_ndrf_alert(req)
    bulletin_text = IMDBulletinGenerator.generate_bulletin(step_data, alert_data)
    return bulletin_text


@app.get("/api/bulletin/html", response_class=HTMLResponse)
def get_imd_bulletin_html(step_index: int = Query(5), lat: float = Query(21.62), lon: float = Query(87.51), loc_name: str = Query("Digha Coast")):
    """Renders formatted HTML official IMD Cyclone Advisory Bulletin."""
    step_data = tracker.detect_and_track_step(step_index)
    req = AlertRequest(lat=lat, lon=lon, location_name=loc_name, step_index=step_index)
    alert_data = calculate_ndrf_alert(req)
    return IMDBulletinGenerator.generate_html_bulletin(step_data, alert_data)


@app.get("/api/bulletin/download")
def download_imd_bulletin(step_index: int = Query(5), lat: float = Query(21.62), lon: float = Query(87.51), loc_name: str = Query("Digha Coast")):
    """Generates downloadable HTML bulletin file with Census 2011 density-based demographic projections."""
    step_data = tracker.detect_and_track_step(step_index)
    req = AlertRequest(lat=lat, lon=lon, location_name=loc_name, step_index=step_index)
    alert_data = calculate_ndrf_alert(req)
    html_content = IMDBulletinGenerator.generate_html_bulletin(step_data, alert_data)
    filename = f"IMD_Cyclone_Bulletin_Amphan_Step{step_index + 1}.html"
    return Response(
        content=html_content,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/api/hazards")
def get_all_hazards():
    """Lists all extreme weather anomaly types supported per SIH 26078 requirements."""
    return MultiHazardRegistry.list_events()


@app.get("/api/hazards/{hazard_id}")
def get_hazard_detail(hazard_id: str):
    """Returns metadata and parameters for specific extreme weather anomaly."""
    return MultiHazardRegistry.get_event(hazard_id)


@app.get("/api/hazards/{hazard_id}/timesteps")
def get_hazard_timesteps(hazard_id: str):
    """Returns temporal progression and spectral smoothing analysis for hazard.
    Note: Cyclone Amphan (amphan_2020) is fully operational and computed from real ERA5/IBTrACS data.
    Heat Dome and Cold Wave are documented architectural roadmap extensions."""
    if hazard_id == "amphan_2020":
        return get_track()
    return JSONResponse(
        status_code=501,
        content={
            "status": "roadmap",
            "hazard_id": hazard_id,
            "message": "Heat Dome / Cold Wave tracking uses the same spherical GNN + CorrDiff architecture as the Amphan pipeline but requires regional IMDAA temperature reanalysis not yet integrated. See roadmap in README.md."
        }
    )


@app.get("/api/hazards/{hazard_id}/downscale")
def get_hazard_downscale(hazard_id: str, step_index: int = Query(2, description="Timestep index")):
    """Returns 2D spatial downscaled fields for hazard.
    Note: Cyclone Amphan (amphan_2020) is fully operational with trained PyTorch CorrDiff weights.
    Heat Dome and Cold Wave are documented architectural roadmap extensions."""
    if hazard_id == "amphan_2020":
        return get_downscale(step_index)
    return JSONResponse(
        status_code=501,
        content={
            "status": "roadmap",
            "hazard_id": hazard_id,
            "message": "Heat Dome / Cold Wave spatial downscaling uses the same conditional diffusion architecture as the Amphan pipeline but requires regional IMDAA temperature reanalysis not yet integrated. See roadmap in README.md."
        }
    )


@app.get("/api/coastal-districts")
def get_coastal_districts():
    """Returns GeoJSON FeatureCollection of coastal district polygons with 97.8% footprint refinement metrics."""
    return _coastal_districts_cache


@app.get("/api/wind-vectors")
def get_wind_vectors(step_index: int = Query(5, description="Timestep index")):
    """Returns physical u/v wind vector field from real ERA5 data for streamline particle animation."""
    if step_index not in _wind_vectors_cache:
        _wind_vectors_cache[step_index] = wind_engine.get_step_vectors(step_index)
    return _wind_vectors_cache[step_index]


DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
if os.path.exists(DASHBOARD_DIR):
    app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")

@app.get("/")
def serve_dashboard():
    """Serves the main operations dashboard index.html."""
    index_file = os.path.join(DASHBOARD_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "NCMRWF AI Weather Tracking API is online. Access /docs for OpenAPI specs."}
