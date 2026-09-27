import pytest
from src.climate_sandbox import compute_emanuel_mpi, compute_ships_ri_probability, evaluate_perturbation

def test_emanuel_mpi_thermodynamic_sanity():
    # Tropical SST 31 C, tropopause -73 C
    mpi = compute_emanuel_mpi(sst_c=31.0, tropo_temp_c=-73.0)
    assert mpi["v_max_kmh"] > 220.0, f"Expected realistic category 5 MPI, got {mpi['v_max_kmh']}"
    assert mpi["v_max_kmh"] < 360.0, f"Unphysical high MPI: {mpi['v_max_kmh']}"
    assert 870.0 <= mpi["p_min_hpa"] <= 940.0, f"Unphysical pressure: {mpi['p_min_hpa']}"
    assert 0.40 <= mpi["carnot_efficiency"] <= 0.60

def test_ships_ri_shear_sensitivity():
    # Low shear should yield higher RI probability than high shear
    ri_low_shear = compute_ships_ri_probability(
        sst_c=31.0, vws_kt=8.0, ohc_kj_cm2=90.0, rh700_pct=80.0, current_v_kt=100.0, mpi_v_kt=150.0
    )
    ri_high_shear = compute_ships_ri_probability(
        sst_c=31.0, vws_kt=25.0, ohc_kj_cm2=90.0, rh700_pct=80.0, current_v_kt=100.0, mpi_v_kt=150.0
    )
    assert ri_low_shear["prob_ri_percent"] > ri_high_shear["prob_ri_percent"], "Low shear must have higher RI probability"
    assert ri_low_shear["prob_ri_percent"] > 50.0
    assert ri_high_shear["prob_ri_percent"] < 40.0

def test_climate_perturbation_warming_amplification():
    # Warm ocean +2 C warming scenario
    res = evaluate_perturbation(hazard_id="amphan_2020", delta_sst=2.0, delta_vws=-2.0)
    assert res["delta_mpi_vmax_kmh"] > 0, "Warming must increase MPI Vmax"
    assert res["delta_mpi_pmin_hpa"] < 0, "Warming must lower central pressure"
    assert res["surge"]["delta_surge_m"] > 0, "Storm surge must amplify with warming"
    assert res["humanitarian_impact"]["delta_population"] > 0, "Population at risk must increase"
