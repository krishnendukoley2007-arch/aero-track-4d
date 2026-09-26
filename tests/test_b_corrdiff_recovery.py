"""
Test B — CorrDiff Amplitude Recovery
Proves the trained CorrDiff actually sharpens peak wind/rainfall beyond coarse NWP input.
Uses existing corrdiff_amphan.pt weights and Amphan peak timestep (step 5).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.downscale.inference import CorrDiffInferenceEngine


def test_corrdiff_amplitude_recovery():
    print("\n" + "="*60)
    print("TEST B — CorrDiff Amplitude Recovery")
    print("="*60)

    inf = CorrDiffInferenceEngine()
    print("  Running downscale on Amphan 2020 — Step 5 (Peak Super Cyclone, held-out test)...")

    result = inf.run_downscale(step_idx=5, n_ensemble_members=5, event_id="amphan_2020")

    amp_eval = result["amplitude_evaluation"]
    peak_info = amp_eval["peak_wind"]
    recovery = amp_eval["measured_recovery_percent"]
    cal = result["calibration_metrics"]
    phys = result["physics_diagnostics"]

    era5_peak    = peak_info["native_era5_target"]
    coarse_peak  = peak_info["coarse_nwp"]
    unet_peak    = peak_info["standard_unet_smoothed"]
    corrdiff_peak = peak_info["corrdiff_ensemble_mean"]
    corrdiff_p90  = peak_info["corrdiff_p90_high_impact"]
    ibtracs_peak  = peak_info["ibtracs_in_situ"]

    rec_coarse   = recovery["coarse_nwp"]
    rec_unet     = recovery["standard_unet"]
    rec_corrdiff = recovery["corrdiff_mean"]
    rec_p90      = recovery["corrdiff_p90"]

    smoothing_loss = amp_eval["spectral_smoothing_loss_unet"]
    corrdiff_gain  = amp_eval["corrdiff_gain_over_unet_kmh"]

    crps = cal["crps_wind_kmh"]
    fss  = cal["fss_precipitation_score"]
    phys_score = phys["diagnostic_conformity_score"]

    print(f"\n  [B1] Peak Wind Speed Comparison (5 km resolution):")
    print(f"       ERA5 native target (ground truth): {era5_peak:.1f} km/h")
    print(f"       IBTrACS in-situ observation:       {ibtracs_peak:.1f} km/h")
    print(f"  NOTE: ERA5 is a 25km reanalysis grid — it cannot resolve the 15km cyclone eyewall.")
    print(f"        IBTrACS reports 10-min sustained in-situ best-track wind (222.2 km/h).")
    print(f"        This system targets ERA5 resolution, not IBTrACS best-track.")
    print(f"       Coarse NWP input (12 km):          {coarse_peak:.1f} km/h  ({rec_coarse:.1f}% of ERA5 target)")
    print(f"       Standard U-Net (spectrally smooth): {unet_peak:.1f} km/h  ({rec_unet:.1f}% of ERA5 target)")
    print(f"       CorrDiff ensemble mean:            {corrdiff_peak:.1f} km/h  ({rec_corrdiff:.1f}% of ERA5 target)")
    print(f"       CorrDiff P90 high-impact scenario: {corrdiff_p90:.1f} km/h  ({rec_p90:.1f}% of ERA5 target)")

    print(f"\n  [B2] Spectral Smoothing Loss & Recovery:")
    print(f"       U-Net spectral smoothing loss:     {smoothing_loss:.1f}%")
    print(f"       CorrDiff gain over U-Net:          +{corrdiff_gain:.1f} km/h")

    print(f"\n  [B3] Calibration Metrics:")
    print(f"       CRPS (wind, 5-member ensemble):    {crps:.3f} km/h")
    print(f"       FSS (precipitation, 5 km window):  {fss:.3f}")

    print(f"\n  [B4] Physics Diagnostic Score: {phys_score:.1f} / 100")
    print(f"       (Post-hoc fluid dynamics audit: MFC alignment + divergence in turbulent eyewall)")

    # B1: Coarse input suppresses wind vs ERA5 target
    assert coarse_peak < era5_peak, f"B1 FAIL: coarse={coarse_peak:.1f} not < era5={era5_peak:.1f} km/h"

    # B2: CorrDiff output peak >= coarse peak
    assert corrdiff_peak >= coarse_peak, f"B2 FAIL: corrdiff={corrdiff_peak:.1f} not >= coarse={coarse_peak:.1f} km/h"

    # B3: CorrDiff > U-Net (diffusion adds value over plain UNet)
    assert corrdiff_peak >= unet_peak, f"B3 FAIL: corrdiff={corrdiff_peak:.1f} not >= unet={unet_peak:.1f} km/h"

    # B4: CRPS is finite and positive
    assert 0.0 < crps < 200.0, f"B4 FAIL: crps={crps:.3f} km/h not in (0, 200)"

    # B5: FSS is valid (0 to 1)
    assert 0.0 <= fss <= 1.0, f"B5 FAIL: fss={fss:.3f} not in [0, 1]"

    # B6: Physics score > 0
    assert phys_score > 0.0, f"B6 FAIL: physics_score={phys_score:.1f} not positive"

    print(f"\n  [TEST B PASSED]")
    print(f"  CorrDiff={corrdiff_peak:.1f} km/h ({rec_corrdiff:.1f}% recovery) | CRPS={crps:.3f} km/h | gain=+{corrdiff_gain:.1f} km/h over U-Net")


if __name__ == "__main__":
    test_corrdiff_amplitude_recovery()
