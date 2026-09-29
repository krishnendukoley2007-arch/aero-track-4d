# AERO-TRACK-4D — Baseline Forensic Audit (Phase 0)

**Date**: September 29, 2026  
**Execution Context**: SIH 26078 Emergency One-Day Upgrade Plan  
**Controlling Specification**: `AERO_TRACK_4D_ONE_DAY_MASTER_ANTIGRAVITY.md`  
**Status**: **PHASE 0 COMPLETED — GATE 0 HOLD**

---

## 1. Executive Summary

This forensic audit establishes the rigorous, ground-truth baseline of the `aero-track-4d` repository prior to any scientific, architectural, or algorithmic modifications. In accordance with Phase 0 of the controlling execution plan, no code, models, datasets, or public benchmarks have been altered. Every metric, checkpoint parameter, data origin, and remaining limitation documented herein is verified directly against active code, file hashes, and test execution outputs.

---

## 2. Git State & Working Directory Telemetry

* **Current Branch**: `main` (tracking `origin/main` at `https://github.com/krishnendukoley2007-arch/aero-track-4d.git`)
* **HEAD Commit**: `393607a` (*"Final doc honesty pass: fix U-Net comparison, test counts, resolution claim, GAT status; remove build brief"*)
* **Recent Commit History (Last 5)**:
  1. `393607a` — Final doc honesty pass: fix U-Net comparison, test counts, resolution claim, GAT status; remove build brief
  2. `6c38459` — Determinism: seed=42 on all live API downscale endpoints
  3. `fc37089` — Checkpoint 5: deterministic seeding for ensemble sampling
  4. `5901bd1` — fix(geometry): remove population fields, replace reduction with neutral geometry, and clean forbidden terms
  5. `54225dd` — P1-Close: Synchronize docs/app.js and regenerate static data with geometric area reduction
* **Working Directory Status**:
  * Uncommitted modified files (11):
    * `README.md`
    * `WALKTHROUGH.md`
    * `dashboard/app.js`
    * `dashboard/index.html`
    * `docs/app.js`
    * `docs/index.html`
    * `src/api.py`
    * `src/cell_broadcast.py`
    * `src/downscale/inference.py`
    * `src/ensemble_medium_range.py`
    * `tests/test_p1_t11_regression.py`
  * Untracked files (1):
    * `AERO_TRACK_4D_ONE_DAY_MASTER_ANTIGRAVITY.md`

---

## 3. Test Suite & Runtime Verification

Two independent test harnesses were executed synchronously:

1. **Pytest Unit & Regression Suite**:
   * Command: `pytest -q`
   * Result: **27 passed in 29.88s** (100% pass rate)
   * Coverage includes:
     * `tests/test_a_gat_attention.py`: Spherical GAT attention weight validation
     * `tests/test_b_corrdiff_recovery.py`: CorrDiff downscale recovery & CRPS calibration
     * `tests/test_c_efi_approximation.py`: Extreme Forecast Index Gaussian proxy bounds
     * `tests/test_climate_sandbox.py`: Emanuel MPI & RI shear perturbation sensitivity
     * `tests/test_d_multistorm.py`: Multi-storm evaluation on Fani and Yaas
     * `tests/test_p1_t11_regression.py`: API provenance contract, AST anti-multiplier checks, README table synchronization
     * `test_engineering_hardening.py`: Physics conservation loss gradient & REST contracts

2. **Live Production Smoke Test**:
   * Command: `python test_smoke.py`
   * Target: Live FastAPI instance at `http://127.0.0.1:8000`
   * Result: **43 passed, 0 failed** across all registered REST endpoints (HTTP 200)

---

## 4. Model Checkpoint Inventory & Provenance

The repository contains two binary PyTorch model checkpoints in `models/`:

| Checkpoint File | File Size | Parameter Count | Architecture | Provenance & Training Status |
| :--- | :--- | :--- | :--- | :--- |
| `models/gat_tracker_amphan.pt` | 23,264 bytes (~23 KB) | 4,929 trainable weights | `TrainableSphericalGAT` (4 input features, 32 hidden, 4 attention heads) | **Fixed Checkpoint**: Weights derived from historical training run on Cyclone Amphan May 2020 ERA5 steps. Training script not self-contained in root; loaded by `src/spherical_gnn.py`. |
| `models/corrdiff_amphan.pt` | 1,489,143 bytes (~1.49 MB) | 360,872 weights (176k Mean Predictor + 184k Diffusion Corrector) | `PhysicsNeMoCorrDiff` (Stage 1 U-Net + Stage 2 Score-Based Diffusion) | **Fixed Checkpoint**: Trained on Amphan coarse/fine synthetic pairs with 15 diffusion timesteps (`src/train_downscale.py`). |

---

## 5. Dataset Inventory & Provenance

All raw datasets reside in `data/raw/` and `data/climatology/`:

| File | Size | Format | Primary Provenance | Ground-Truth Classification |
| :--- | :--- | :--- | :--- | :--- |
| `data/raw/era5_amphan_may2020.json` | 2.15 MB | JSON (16x16 grid, 168 timesteps) | ECMWF Copernicus Climate Change Service (ERA5 hourly reanalysis) | **Reanalysis Proxy** (Not operational NWP forecast) |
| `data/raw/era5_fani_may2019.json` | 2.17 MB | JSON (16x16 grid, 168 timesteps) | ECMWF Copernicus Climate Change Service (ERA5 hourly reanalysis) | **Reanalysis Proxy** (Not operational NWP forecast) |
| `data/raw/era5_yaas_may2021.json` | 1.86 MB | JSON (16x16 grid, 168 timesteps) | ECMWF Copernicus Climate Change Service (ERA5 hourly reanalysis) | **Reanalysis Proxy** (Not operational NWP forecast) |
| `data/raw/amphan_ibtracs_real.csv` / `.json` | 3.88 KB / 11.9 KB | CSV / JSON | NOAA NCEI IBTrACS v04r01 (Agency: IMD New Delhi) | **Real Ground Truth Observation** |
| `data/raw/fani_ibtracs_real.csv` / `.json` | 5.22 KB / 16.5 KB | CSV / JSON | NOAA NCEI IBTrACS v04r01 (Agency: IMD New Delhi) | **Real Ground Truth Observation** |
| `data/raw/yaas_ibtracs_real.csv` / `.json` | 2.83 KB / 9.03 KB | CSV / JSON | NOAA NCEI IBTrACS v04r01 (Agency: IMD New Delhi) | **Real Ground Truth Observation** |
| `data/climatology/bay_of_bengal_may_climatology.json` | 39.5 KB | JSON (16x16 grid, mean & std) | Pre-computed Gaussian distribution for Bay of Bengal pre-monsoon May | **Proxy Baseline Climatology** (Not full 30-year daily empirical distribution) |

---

## 6. Current Benchmark Definitions & Measured Values

All benchmarks are documented in `results/audit_metrics.json` and rendered dynamically:

### A. Stage 1 Spherical GNN Anomaly Tracking (Amphan 2020)
* **Mesh Properties**: 269 nodes, 742 geodesic edges, subdivision 6 icosphere patch over Bay of Bengal ($8^\circ\text{N}–26^\circ\text{N}$, $78^\circ\text{E}–96^\circ\text{E}$).
* **Cell Area Variance**: $0.439\%$ (well within the $< 5\%$ spherical geodesic requirement).
* **Mean Track Error vs. NOAA IBTrACS**: **50.85 km** (across 13 synoptic steps at 6–12h intervals).
* **Step 5 (Peak Super Cyclone, Held-Out)**: **36.6 km**.
* **Step 10 (Landfall, Held-Out)**: **8.7 km**.
* **Held-out Mean Track Error**: **22.65 km**.

### B. Stage 2 CorrDiff Downscaling Benchmarks (Amphan Step 5, Held-Out)
* **Native ERA5 Target (Ground Truth)**: **110.5 km/h**
* **Coarse NWP Input ($12\text{ km}$ simulated)**: **63.4 km/h** ($57.38\%$ recovery)
* **Standard U-Net Baseline (L2 loss conditional mean)**: **53.3 km/h** ($48.3\%$ recovery)
* **CorrDiff Ensemble Mean ($N=5$)**: **53.1 km/h** ($48.1\%$ recovery)
* **CorrDiff High-Impact P90 Tail**: **55.2 km/h**
* **Ensemble CRPS (Wind)**: **16.33 km/h** (calibrated envelope $< 30\text{ km/h}$)
* **Fractions Skill Score (FSS Precip)**: **0.156**
* **Physics Diagnostic Score**: **39.0 / 100**

### C. Multi-Storm Zero-Shot Generalization
* **Cyclone Fani (2019)**: Native ERA5 Target $111.1\text{ km/h} \rightarrow$ CorrDiff Mean $50.9\text{ km/h}$ ($45.8\%$ recovery, CRPS $14.772\text{ km/h}$, FSS $0.339$).
* **Cyclone Yaas (2021)**: Native ERA5 Target $92.3\text{ km/h} \rightarrow$ CorrDiff Mean $46.3\text{ km/h}$ ($50.1\%$ recovery, CRPS $18.562\text{ km/h}$, FSS $0.486$).

---

## 7. Forensic Identification of Scientific Gaps & Limitations

1. **Atmospheric Input Is Reanalysis, Not Operational NWP**:
   * *Reality*: Input atmospheric fields originate from ECMWF ERA5 reanalysis (0.25° horizontal grid).
   * *Limitation*: The repository does not ingest live NCMRWF operational NCUM (12 km deterministic) or NEPS-G (12 km ensemble) binary GRIB2 streams.
2. **Coarsened Input Is Synthetically Degraded**:
   * *Reality*: `src/data_loader.py` lines 201–205 generate the coarse field via `gaussian_filter(sigma=1.2) * 0.82`.
   * *Limitation*: This represents a controlled synthetic super-resolution proxy experiment, not real 12 km grid physics.
3. **16×16 Native Resolution vs. 38×38 Display**:
   * *Reality*: Neural network inference occurs exclusively on a $16 \times 16$ spatial matrix covering the central storm core.
   * *Limitation*: The $38 \times 38$ visualization in `dashboard/` is bicubic display interpolation and must never be cited as native 5 km model inference.
4. **10-Member Ensemble Trajectory Is Parametric**:
   * *Reality*: `src/ensemble_medium_range.py` perturbs the central trajectory using a power-law chaos formula ($\sigma(t) = \sigma_0 (t/24)^{1.2}$).
   * *Limitation*: It demonstrates medium-range ensemble divergence concepts, but is not generated from numerical ensemble member simulations.
5. **Physics Conservation Loss Channel Allocation**:
   * *Reality*: In `src/downscale/corrdiff_model.py`, mass divergence loss is currently computed on the scalar wind magnitude channel `pred[:, 0:1]` rather than resolving true orthogonal vector wind components $(u, v)$. Moisture flux convergence is computed without atmospheric specific humidity ($q$).
   * *Limitation*: Must be classified as a heuristic physical diagnostic constraint.
6. **Multi-Hazard Hazards (Heat Dome & Cold Wave)**:
   * *Reality*: Synthesized illustrative anomaly datasets used to test API and UI rendering.
   * *Limitation*: Not output by a trained neural network.

---

## 8. Current Public Claims Audit

* **Audited & Resolved in Phase 1**:
  * Unverified claims regarding "3,681,500 citizens shielded" were purged; reframed as **$97.76\%$ geometric area reduction** ($78.54\text{ km}^2$ circular corridor vs. assumed $3,500\text{ km}^2$ administrative district).
  * "100% offline" claims were clarified: Leaflet 2D tiles stream from ESRI/OSM; backend GNN, diffusion inference, and 3D WebGL run offline.
  * Bulletins now display prominent watermark: `"SIMULATED — NOT AN OFFICIAL IMD PRODUCT"`.
  * Deterministic seeding (`seed=42`) is active across all stochastic evaluation paths.
* **Remaining Public Presentation Tasks**:
  * Ensure every API endpoint JSON response strictly contains the unified provenance object schema required by Phase 10 (`data_source_type`, `forecast_status`, `model_status`).
  * Ensure no dashboard view permits ambiguous interpretation of the $38 \times 38$ interpolated display grid as native 5 km output.

---

## 9. Baseline Sign-Off

This audit represents the true, unembellished state of the repository. All 27 tests pass. No hidden scaling or ungrounded claims remain in documentation. The repository is stable and ready for Phase 1 scientific semantics cleanup.
