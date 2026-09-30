# AERO-TRACK 4D — Judge Defence Q&A

**System**: AERO-TRACK 4D (SIH 26078)  
**Version**: 1.0.0  
**Status**: Research Prototype  

> Every answer in this document cites a specific repository file or measured result. No answer is unsupported speculation.  
> Where the answer is unfavourable, it is reported honestly.

---

## Q1. Is any input a real operational forecast (NEPS-G / NCUM)?

**A.** **No.** The system does not ingest any live or historical NCMRWF operational NWP data. The atmospheric inputs are **ERA5 reanalysis** from the ECMWF Copernicus Climate Data Store for three Bay-of-Bengal cyclones: Amphan (2020), Fani (2019), and Yaas (2021). The coarse NWP input is a synthetic proxy generated via Gaussian blurring (σ=1.2) and spectral attenuation (0.75–0.85). The 10-member ensemble is a physically motivated Bred-Vector / parametric chaos perturbation proxy, not actual NEPS-G.

**Evidence**: `results/audit_metrics.json § data_loader.coarse_filter`, `src/api.py § make_provenance_schema`

---

## Q2. Why does the tracker have worse footprint IoU than a threshold baseline?

**A.** The GAT tracker achieves **68.09 km mean track error** (an 85.5% improvement over the 469.65 km threshold baseline), but gets lower footprint segmentation IoU (**0.085 vs 0.123**). This occurs because the GAT was explicitly trained with a continuous Haversine geodesic loss function to regress vortex centroid coordinates, not for binary pixel footprint segmentation. The simple threshold CC baseline greedily groups connected wind pixels above 50 km/h, which captures the broad spatial swath better despite failing dramatically on true center tracking.

**Evidence**: `results/training_runs/tracker_loso_*.json § baseline_comparison`, `README.md`

---

## Q3. Why is peak recovery 80.4% and not near 100%?

**A.** Because **Leave-One-Storm-Out (LOSO) cross-validation** is an honest, rigorous generalization test on completely unseen storm dynamics. When evaluated on the held-out Super Cyclone Amphan (139.7 km/h ERA5 peak), CorrDiff recovers **112.4 km/h (80.4%)** while standard U-Net recovers 106.8 km/h (76.5%) and bicubic achieves only 73.2 km/h (52.4%). Reaching 100% in reanalysis downscaling would require fitting to the specific storm or suffering from overfitting. Furthermore, global 0.25° ERA5 itself has an intensity ceiling compared to in-situ 10-min eyewall observations (222 km/h IBTrACS), which can only be closed by regional IMDAA/radar training.

**Evidence**: `results/downscaling_benchmark.json`, `docs/BENCHMARK_CARD.md`

---

## Q4. Is the physics loss actually helping?

**A.** **It is a measured trade-off, not a pure win.** In the LOSO ablation matrix, adding physics conservation (divergence + MFC) and extreme tail loss improved peak wind recovery from **65.9% (92.1 km/h) to 80.4% (112.4 km/h)** and reduced p95 tail error from 14.14 km/h to 2.90 km/h. However, moisture flux convergence (MFC) alignment slightly dropped from **0.764 / 0.730 to 0.692**, because aggressively pushing the network into high-amplitude extreme tails introduces subtle convective gradient tension. We report this trade-off plainly rather than claiming physics solved every metric simultaneously.

**Evidence**: `results/downscaling_benchmark.json § models`, `results/ablation_matrix.json`

---

## Q5. What would you do with two more weeks?

**A.** Three concrete engineering and meteorological milestones:
1. **Real Operational NWP Ingestion**: Connect the data pipeline to live ECMWF TIGGE / NOAA GEFS / NCMRWF open data feeds for real 10-member ensemble GRIB2 files.
2. **Larger Storm Corpus**: Expand the training corpus from 3 North Indian Ocean storms to 25+ global tropical cyclones (spanning Bay of Bengal, Arabian Sea, and Western Pacific).
3. **Regional IMDAA Target**: Train native 12 km → 4 km downscaling against NCMRWF IMDAA regional reanalysis and coastal Doppler Weather Radar (DWR) mosaics.

---


---

## Q4. What is ERA5?

**A.** ERA5 is the fifth-generation ECMWF global reanalysis, produced by combining historical observations with numerical weather model output via data assimilation. It is not a real-time operational forecast — it is a retrospective reconstruction of atmospheric state, released approximately 5 days behind real time. ERA5 is our ground-truth reference and our training target. It is available under the Copernicus Climate Change Service license for research and education use.

**Evidence**: `docs/DATA_LICENSES.md`  
**Evidence**: `results/downscaling_benchmark.json § provenance.data_source_type = ERA5_REANALYSIS`

---

## Q5. How is EFI computed?

**A.** The Extreme Forecast Index (EFI) is computed using **numerical integration** of the formula:

```
EFI = (2/π) × ∫₀¹ [F(M) − M] / [M(1−M)]^(1/2) dM
```

where:
- `F` is the empirical CDF of the 10-member synthetic forecast ensemble at each grid point
- `M` is the ERA5 climatological CDF, constructed from Bay-of-Bengal pre-monsoon historical ERA5 data (16×16 grid)
- Integration is performed via `scipy.integrate.quad` numerical quadrature

The result is bounded to `[−1, +1]` by construction. +1 means the entire forecast distribution is above the historical maximum; −1 means the entire distribution is below the historical minimum.

**Evidence**: `src/efi.py`  
**Evidence**: `tests/test_phase4_proper_efi.py`  
**Evidence**: `results/official_benchmark.json § B_efi_vs_threshold`

> [!NOTE]
> Previously the system used an unbounded z-score proxy labelled as EFI. This was replaced with proper numerical integration in Phase 4 of the upgrade plan.

---

## Q6. What is the spherical GNN learning?

**A.** The **SpatioTemporalSphericalGAT** (Graph Attention Network) learns to predict cyclone **centre position** at each 6-hourly timestep from ERA5 surface fields mapped onto a geodesic icosphere mesh.

- **Input**: ERA5 surface wind, pressure, precipitation, and temperature, interpolated to 269 mesh nodes over 8°–26°N, 78°–96°E
- **Architecture**: Multi-head Graph Attention → spatial pooling → GRU temporal encoder → centre coordinate regression
- **Mesh**: Regional patch of icosphere subdivision-6 (269 nodes, 742 edges, node spacing 111–132 km)
- **Training objective**: Minimize Haversine-distance track error vs. IBTrACS best-track positions

**Evidence**: `src/spherical_gnn.py`  
**Evidence**: `results/training_runs/tracker_loso_20260929_143627.json`  
**Evidence**: `results/audit_metrics.json § spherical_gnn`

---

## Q7. How was the model trained?

**A.** Two models were trained:

### SphericalGAT Tracker
- **Algorithm**: AdamW (lr=0.002, weight_decay=1e-4), 40 epochs, batch gradient descent
- **Train storms**: Fani 2019 + Yaas 2021 (LOSO split, amphan_2020 held out)
- **Val temporal buffer**: 24 hours to prevent boundary leakage
- **Training time**: ~26 seconds (17,060-parameter model)
- **Manifest**: `results/training_runs/tracker_loso_20260929_143627.json`

### CorrDiff Downscaler
- **Algorithm**: Adam (lr=0.001), 20 epochs, batch size 16
- **Loss**: `ExtremeTailConservationLoss` = MSE + 0.3×L1 + 0.25×TailLoss + 0.15×DivergenceLoss + 0.2×MFCLoss
- **Train storms**: Fani 2019 + Yaas 2021 (168 samples from Amphan withheld)
- **Architecture**: 360,872 parameters (MeanPredictor + DiffusionCorrector)
- **Manifest**: `results/training_runs/downscale_loso_20260929_145218.json`

All training runs used `seed=42` for reproducibility. Checkpoints are saved with the manifest and can be re-evaluated exactly.

---

## Q8. How did you prevent storm leakage?

**A.** Storm-level Leave-One-Storm-Out (LOSO) split:

1. **Storm-level partition**: Amphan 2020 (the test storm) was never seen by either model during training. Fani and Yaas were used exclusively for training/validation.
2. **Temporal buffer**: A 24-hour buffer was applied at storm boundaries in the tracker split to prevent temporal proximity contamination.
3. **Normalization stats**: Normalization statistics (mean/std) are computed on training data only, before any test-fold data is accessed.
4. **Contractual leakage tests**: `tests/test_phase12_leakage_anticheat.py` automatically verifies that "amphan_2020" does not appear in any training manifest's `train_storms` list, and that train+test sample counts are consistent with the documented split.

**Evidence**: `tests/test_phase12_leakage_anticheat.py § TestStormSplitIntegrity`  
**Evidence**: `results/training_runs/tracker_loso_20260929_143627.json § splits.val_temporal_buffer_hours = 24`

---

## Q9. What exactly does "5 km" mean?

**A.** The "5 km" label in the dashboard refers to a **display interpolation target**, not native model resolution.

| Layer | Resolution |
|---|---|
| Native model grid (training + inference) | **16×16** (regional patch, ~111 km node spacing) |
| ERA5 training target | **0.25° (~28 km)** regional grid |
| Dashboard display grid | **38×38** (bilinear upsampling of 16×16 output) |
| "5 km" | **Display interpolation label only** — not model inference at 5 km |

The API explicitly discloses both `native_grid` (16×16) and `display_grid` (38×38) in every response's `provenance` object.

**Evidence**: `src/api.py § make_provenance_schema()` — returns `native_grid: "16x16 regional"` and `display_grid: "38x38 bilinear interpolation"`  
**Evidence**: `results/audit_metrics.json § spherical_gnn.node_spacing_km`

---

## Q10. What does CorrDiff add?

**A.** CorrDiff (Corrector Diffusion) adds **stochastic high-frequency detail** and **extreme-amplitude recovery** on top of a deterministic mean prediction:

- **Stage 1 (MeanPredictor)**: A U-Net produces a spatially smooth conditional mean — this is identical in structure to the U-Net baseline
- **Stage 2 (DiffusionCorrector)**: A score-based denoising diffusion model learns the residual between Stage 1 output and the true ERA5 field, conditioned on a physics conformity loss

The key contribution vs. U-Net is:
- **Peak wind recovery**: 80.4% vs. 76.5% (U-Net) — better extreme-amplitude preservation
- **p95 tail error**: 2.9 km/h vs. 11.45 km/h (U-Net) — dramatically better at the extremes
- **Probabilistic output**: 5 stochastic samples per inference; CRPS improves by 0.20 km/h vs. U-Net

CorrDiff does **not** beat bicubic on MAE (7.97 vs. 5.41 km/h) — this is consistent with the known U-Net regression-to-mean effect also present in the CorrDiff mean predictor.

**Evidence**: `results/official_benchmark.json § C_downscaling_loso`  
**Evidence**: `docs/BENCHMARK_CARD.md § 3.1`

---

## Q11. What baseline did you beat?

**A.**

| Task | Baselines beaten | Where CorrDiff Proposed wins |
|---|---|---|
| Tracking | Threshold CC (85.5% error reduction), Const. Velocity (86.4%) | Track centre error |
| Downscaling (extreme tail) | Bicubic (+28pp peak recovery), U-Net (+3.9pp), CorrDiff-no-phys (+14.5pp) | Peak recovery, p95 tail error |

**Where it does NOT beat the baseline**:
- MAE wind: Bicubic (5.41) is better than CorrDiff Proposed (7.97)
- FSS precipitation: Bicubic (0.824) is better than CorrDiff Proposed (0.634)
- Footprint IoU: Threshold CC (0.123) is better than GAT (0.085)

These unfavourable comparisons are included in `docs/BENCHMARK_CARD.md` and are not hidden.

**Evidence**: `results/official_benchmark.json`

---

## Q12. How do you verify extreme preservation?

**A.** Three metrics specifically target extreme preservation:

1. **Peak Recovery Percent**: `100 × (predicted_peak_wind / true_peak_wind)`. For Amphan 2020, true ERA5 peak = 139.7 km/h; CorrDiff Proposed predicted peak = 112.4 km/h → **80.4% recovery**.
2. **p90/p95 tail error**: Absolute error at the 90th and 95th percentiles of the wind distribution. CorrDiff Proposed: p90=5.41 km/h, p95=2.90 km/h (substantially better than all baselines at the 95th percentile).
3. **Extreme Tail Loss** (`λ_tail=0.25`): A dedicated training loss term that upweights samples where the ERA5 target exceeds the 95th percentile of the training distribution.

**Evidence**: `results/downscaling_benchmark.json § models.corrdiff_proposed_physics`  
**Evidence**: `src/downscaling.py § ExtremeTailConservationLoss`

---

## Q13. How are probabilities calibrated?

**A.** Probabilistic outputs are provided by:

1. **CorrDiff ensemble**: 5 stochastic samples per inference, aggregated to P10/P50/P90 quantiles. **CRPS = 7.44 km/h** for the proposed model vs. 7.64 for U-Net (improvement of 0.20 km/h).
2. **EFI**: Bounded `[−1, +1]` by construction, so no additional calibration is needed for the EFI range.
3. **Medium-range ensemble**: 10-member synthetic parametric ensemble with quantile outputs (P10/P50/P90) and uncertainty attribution (chaos formula).

**Calibration caveat**: We have not performed a reliability diagram or Brier score calibration against a held-out observation set. Calibration is measured only via CRPS on Amphan 2020 (168 samples). This is a significant limitation.

**Evidence**: `results/official_benchmark.json § F_deterministic_vs_probabilistic`  
**Evidence**: `src/ensemble_medium_range.py`

---

## Q14. How are alerts generated?

**A.** Alert polygons are derived **directly from the model's predicted wind field**, not from arbitrary radius circles or manual definition:

```
fine_wind_grid (CorrDiff output, 16×16)
  ↓ bilinear interpolation to display grid
  ↓ threshold exceedance mask (e.g., >80 km/h)
  ↓ scipy.ndimage connected-component labelling
  ↓ largest connected region selected
  ↓ convex hull polygon (lat/lon coordinates)
  ↓ severity classification (Yellow/Orange/Red based on peak wind)
  ↓ lead-time tag
  ↓ GeoJSON output
  ↓ OASIS CAP v1.2 XML embedding
```

The polygon boundary is entirely model-field-derived. The alert probability (e.g., 0.88) comes from the fraction of ensemble members exceeding the threshold at the alert polygon centroid.

**Evidence**: `src/alert_contour.py`  
**Evidence**: `src/cap_alert.py`  
**Evidence**: `tests/test_phase5_7_8_forecast_alert.py`

---

## Q15. What happens when the model is wrong?

**A.** The system handles model failure in the following ways:

1. **Disclosed uncertainty**: Every API response carries `verification_status: prototype`. P10/P50/P90 quantile outputs explicitly show the ensemble spread.
2. **Provenance transparency**: Every response discloses that the input is ERA5 (not real-time NWP) and that the ensemble is synthetic, so a downstream user knows the source of potential bias.
3. **Honest metrics**: Peak recovery of 80.4% means the model **underestimates peak wind by 19.6%** on average (predicted 112.4 km/h vs. true 139.7 km/h). This underestimation bias is disclosed in `docs/MODEL_CARD.md`.
4. **No population claims**: The system does not make claims about affected populations or loss of life, eliminating a class of severe downstream harm from model error.
5. **No autonomous action**: The system produces alerts as data artefacts; no automated messaging or broadcast is implemented.

**Operational integration note**: For NCMRWF operational integration, the system would require validation against a multi-year hindcast dataset, formal reliability calibration, and human-in-the-loop review before any alert product is issued.

---

## Q16. How would NCMRWF ingest the system operationally?

**A.** The system is architected for future NCMRWF integration via a clean input adapter:

1. **Replace ERA5 input with NCMRWF GRIB2**: The data loader accepts a field dictionary; a GRIB2 adapter reading NEPS-G output would replace the ERA5 NetCDF reader without changing any model code.
2. **Replace synthetic ensemble with NEPS-G**: The 10-member synthetic ensemble can be replaced by actual NEPS-G members; the uncertainty propagation pipeline (`src/ensemble_medium_range.py`) is designed with `real_forecast_data_used` as a runtime toggle.
3. **Retain provenance contract**: The `make_provenance_schema()` function in `src/api.py` would be updated to set `data_source_type: NCMRWF_NEPS_G` and `forecast_status: OPERATIONAL_FORECAST`, making the provenance change machine-readable.
4. **Required for production**: The model would need retraining or fine-tuning on multi-year NCMRWF GRIB2 data at higher resolution, a formal reliability calibration study, and an operational test framework before live deployment.

**Evidence**: `src/api.py § make_provenance_schema`  
**Evidence**: `src/ensemble_medium_range.py § real_forecast_data_used`  
**Evidence**: `AERO_TRACK_4D_ONE_DAY_MASTER_ANTIGRAVITY.md § GOVERNING RULE`

---

*Document generated from repository evidence. All metrics are verifiable from `results/official_benchmark.json`, `results/audit_metrics.json`, and the training manifests in `results/training_runs/`.*
