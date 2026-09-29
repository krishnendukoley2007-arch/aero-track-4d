"""
Unit tests for Phase 5 (Medium-Range Forecast Path), Phase 7 (Uncertainty Quantification),
and Phase 8 (Model-Derived Alert Polygon Generation).
Verifies:
- Medium-range point forecast interface across lead times 72h, 96h, 120h, 168h, 240h.
- P10/P50/P90 quantiles and exceedance probabilities.
- Model-derived contour alert polygons (no arbitrary circles, no population counts).
- OASIS CAP v1.2 XML polygon embedding.
- Standardized Phase 10 provenance schema.
"""

import os
import sys
import xml.etree.ElementTree as ET
import numpy as np
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.ensemble_medium_range import MediumRangeEnsembleEngine
from src.alert_contour import compute_model_alert_polygon
from src.cap_alert import CAPAlertGenerator
from src.api import app
from fastapi.testclient import TestClient


def test_phase5_medium_range_forecast_lead_times():
    """Verifies that the medium-range ensemble engine accepts valid lead times and coordinates."""
    engine = MediumRangeEnsembleEngine()
    test_lead_times = [72, 96, 120, 168, 240]

    for lead in test_lead_times:
        res = engine.get_point_medium_range_forecast(
            lat=21.62,
            lon=87.51,
            lead_hours=lead,
            forecast_initialization="2020-05-16T00:00:00Z"
        )
        assert res["lead_hours"] == lead
        assert res["ensemble_members_count"] == 10
        assert len(res["members"]) == 10

        # Phase 7: Quantile ordering P10 <= P50 <= P90
        q_wind = res["quantiles"]["wind_speed_kmh"]
        assert q_wind["p10"] <= q_wind["p50_median"] <= q_wind["p90"], f"Quantile ordering failed at {lead}h: {q_wind}"

        q_pres = res["quantiles"]["surface_pressure_hpa"]
        assert q_pres["p10"] <= q_pres["p50_median"] <= q_pres["p90"]

        # Exceedance probabilities bounded in [0, 1]
        probs = res["exceedance_probabilities"]
        for k, v in probs.items():
            assert 0.0 <= v <= 1.0, f"Exceedance prob {k}={v} out of bounds"

        # Three-level uncertainty attribution
        unc = res["uncertainty_attribution"]
        assert "nwp_ensemble_uncertainty" in unc
        assert "generative_diffusion_uncertainty" in unc
        assert "verification_uncertainty" in unc

        # Provenance honesty
        prov = res["provenance"]
        assert prov["data_source_type"] == "SIMULATED"
        assert prov["forecast_status"] == "PROXY"
        assert "NCMRWF NEPS-G" in prov["target_architecture"]


def test_phase8_model_alert_polygon_generation():
    """Verifies that alert polygons derive strictly from model predicted fields without arbitrary circles or population."""
    # Synthetic 16x16 wind field with a localized peak > 62 km/h
    np.random.seed(42)
    lats = np.linspace(19.0, 23.0, 16)
    lons = np.linspace(85.0, 89.0, 16)

    wind_field = np.full((16, 16), 35.0, dtype=np.float32)
    # Inject high-intensity core in center
    wind_field[6:10, 6:10] = 95.0

    alert = compute_model_alert_polygon(
        fine_field=wind_field,
        lats=lats,
        lons=lons,
        threshold_val=62.0,
        event_type="cyclone",
        lead_hours=72,
        severity="severe"
    )

    assert alert["polygon_source"] == "model_probability_contour"
    assert alert["event_type"] == "cyclone"
    assert alert["lead_hours"] == 72
    assert alert["area_km2"] > 0.0

    # GeoJSON validity
    geojson = alert["geojson"]
    assert geojson["type"] == "Feature"
    assert geojson["geometry"]["type"] == "Polygon"
    ring = geojson["geometry"]["coordinates"][0]
    assert len(ring) >= 4, "Polygon ring must have at least 4 vertices (3 points + closed endpoint)"
    assert ring[0] == ring[-1], "Polygon ring must be closed"

    # Strict prohibition: no population fields
    alert_str = str(alert).lower()
    assert "population" not in alert_str
    assert "citizens" not in alert_str


def test_phase8_cap_xml_polygon_embedding():
    """Verifies that OASIS CAP v1.2 XML output uses model contour polygon coordinates."""
    alert_data = {
        "location": {"name": "Digha Coast", "lat": 21.62, "lon": 87.51},
        "severity": "Severe",
        "alert_tier": "SEVERE CYCLONE WARNING",
        "predicted_local_wind_kmh": 120.0,
        "predicted_p90_gust_kmh": 145.0,
        "predicted_local_rain_mmh": 35.0,
        "action_directive": "Immediate coastal evacuation to designated cyclone shelters.",
        "model_contour_coords": [
            [87.2, 21.4], [87.8, 21.4], [87.8, 22.0], [87.2, 22.0], [87.2, 21.4]
        ],
        "ndrf_dispatch_recommendation": {
            "dispatch_priority": "Immediate",
            "target_battalions": "NDRF 2nd Battalion"
        }
    }

    xml_str = CAPAlertGenerator.generate_cap_xml(alert_data, hazard_id="amphan_2020")
    root = ET.fromstring(xml_str)

    # Namespace handling
    ns = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
    area_el = root.find(".//cap:area", ns)
    assert area_el is not None

    polygon_el = area_el.find("cap:polygon", ns)
    assert polygon_el is not None, "CAP XML must contain <polygon> element deriving from model contour"
    assert "21.4000,87.2000" in polygon_el.text, "CAP XML polygon coordinate format must be 'lat,lon'"


def test_phase10_api_endpoints_provenance():
    """Verifies that API endpoints expose the standardized Phase 10 provenance schema."""
    client = TestClient(app)

    # 1. Medium range forecast endpoint
    resp1 = client.get("/api/medium-range/forecast?lat=21.62&lon=87.51&lead_hours=72")
    assert resp1.status_code == 200
    p1 = resp1.json()["provenance"]
    assert "data_source_type" in p1
    assert "forecast_status" in p1
    assert "model_status" in p1
    assert "seed" in p1

    # 2. Alert model polygon endpoint
    resp2 = client.get("/api/alert/model-polygon?step_index=5")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["polygon_source"] == "model_probability_contour"
    assert data2["geojson"]["geometry"]["type"] == "Polygon"

    # 3. Alert POST endpoint
    resp3 = client.post("/api/alert", json={
        "lat": 21.626,
        "lon": 87.508,
        "location_name": "Digha Coast",
        "step_index": 5
    })
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert "model_derived_alert_polygon" in data3
    assert data3["model_derived_alert_polygon"]["polygon_source"] == "model_probability_contour"
    p3 = data3["provenance"]
    assert p3["data_source_type"] == "ERA5_REANALYSIS"
    assert p3["verification_status"] == "POLYGON_CONTOUR_DERIVED"
