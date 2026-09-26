"""
Test D — Multi-Storm Out-of-Sample Generalization
Runs CorrDiff inference on all three storms:
- Cyclone Amphan 2020 (training event)
- Cyclone Fani 2019 (completely unseen)
- Cyclone Yaas 2021 (completely unseen)
Produces the generalization table that no other SIH team will have.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.downscale.inference import CorrDiffInferenceEngine


def test_multistorm_generalization():
    print("\n" + "="*60)
    print("TEST D — Multi-Storm Out-of-Sample Generalization")
    print("="*60)

    inf = CorrDiffInferenceEngine()

    storms = [
        {"event_id": "amphan_2020", "step": 5,  "label": "Amphan 2020 (Super Cyclone, peak held-out)"},
        {"event_id": "fani_2019",   "step": 7,  "label": "Fani 2019 (Cat-5 equivalent, UNSEEN)"},
        {"event_id": "yaas_2021",   "step": 5,  "label": "Yaas 2021 (Very Severe, UNSEEN)"},
    ]

    storm_results = {}

    for s in storms:
        print(f"\n  Running: {s['label']} ...")
        result = inf.run_downscale(step_idx=s["step"], n_ensemble_members=5, event_id=s["event_id"])

        amp   = result["amplitude_evaluation"]
        cal   = result["calibration_metrics"]
        phys  = result["physics_diagnostics"]
        peaks = amp["peak_wind"]

        era5_peak     = peaks["native_era5_target"]
        coarse_peak   = peaks["coarse_nwp"]
        corrdiff_peak = peaks["corrdiff_ensemble_mean"]
        corrdiff_p90  = peaks["corrdiff_p90_high_impact"]
        rec_corrdiff  = amp["measured_recovery_percent"]["corrdiff_mean"]
        smoothing_loss = amp["spectral_smoothing_loss_unet"]
        crps          = cal["crps_wind_kmh"]
        fss           = cal["fss_precipitation_score"]
        phys_score    = phys["diagnostic_conformity_score"]

        storm_results[s["event_id"]] = {
            "label": s["label"],
            "era5_peak_kmh": era5_peak,
            "coarse_peak_kmh": coarse_peak,
            "corrdiff_peak_kmh": corrdiff_peak,
            "corrdiff_p90_kmh": corrdiff_p90,
            "recovery_pct": rec_corrdiff,
            "smoothing_loss_pct": smoothing_loss,
            "crps_kmh": crps,
            "fss": fss,
            "physics_score": phys_score,
        }

        print(f"    ERA5 target:    {era5_peak:.1f} km/h")
        print(f"    Coarse NWP:     {coarse_peak:.1f} km/h")
        print(f"    CorrDiff mean:  {corrdiff_peak:.1f} km/h  ({rec_corrdiff:.1f}% recovery)")
        print(f"    CRPS:           {crps:.3f} km/h  |  FSS: {fss:.3f}  |  Physics: {phys_score:.1f}/100")

    # --- Print the Generalization Table ---
    print(f"\n  {'='*80}")
    print(f"  MULTI-STORM GENERALIZATION TABLE (for your SIH demo slide)")
    print(f"  {'='*80}")
    print(f"  {'Storm':<30} {'ERA5 Peak':>10} {'Recovery%':>10} {'CRPS':>10} {'FSS':>8} {'Phys':>8}")
    print(f"  {'-'*80}")
    for eid, r in storm_results.items():
        seen = "(training)" if eid == "amphan_2020" else "(unseen)  "
        print(f"  {r['label'][:29]:<30} {r['era5_peak_kmh']:>9.1f} {r['recovery_pct']:>9.1f}% {r['crps_kmh']:>9.3f} {r['fss']:>8.3f} {r['physics_score']:>7.1f}")

    # D1: All storms return valid ERA5 peak (not zero)
    for eid, r in storm_results.items():
        assert r["era5_peak_kmh"] > 0.0, f"D1 FAIL: {eid} ERA5 peak is zero"

    # D2: CorrDiff output peak >= coarse for all storms
    for eid, r in storm_results.items():
        assert r["corrdiff_peak_kmh"] >= r["coarse_peak_kmh"], (
            f"D2 FAIL: {eid} corrdiff={r['corrdiff_peak_kmh']:.1f} < coarse={r['coarse_peak_kmh']:.1f}"
        )

    # D3: CRPS is finite for all storms
    for eid, r in storm_results.items():
        assert 0.0 < r["crps_kmh"] < 500.0, f"D3 FAIL: {eid} CRPS={r['crps_kmh']:.3f} not in (0, 500)"

    # D4: FSS is valid (0-1) for all storms
    for eid, r in storm_results.items():
        assert 0.0 <= r["fss"] <= 1.0, f"D4 FAIL: {eid} FSS={r['fss']:.3f} not in [0, 1]"

    # D5: Physics score > 0 for all storms
    for eid, r in storm_results.items():
        assert r["physics_score"] > 0.0, f"D5 FAIL: {eid} physics_score={r['physics_score']:.1f} not positive"

    unseen_working = sum(1 for eid in ["fani_2019", "yaas_2021"]
                         if storm_results[eid]["corrdiff_peak_kmh"] >= storm_results[eid]["coarse_peak_kmh"])
    print(f"\n  Unseen storm generalization: {unseen_working}/2 storms recovered amplitude correctly")
    print(f"\n  [TEST D PASSED]")


if __name__ == "__main__":
    test_multistorm_generalization()
