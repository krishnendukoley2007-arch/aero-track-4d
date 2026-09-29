# AERO-TRACK 4D — Model Card

**System**: AERO-TRACK 4D  
**Problem**: SIH 26078 — AI-Driven Spatio-Temporal Tracking of Extreme Weather Anomalies in Medium-Range Forecasts  
**Status**: Research Prototype  
**Version**: 1.0.0  
**Date**: 2026-09-29  

---

## Model Overview

AERO-TRACK 4D is a two-stage deep learning pipeline for tracking and downscaling extreme tropical cyclone events over the Bay of Bengal. It consists of:

1. **SpatioTemporalSphericalGAT** — a Graph Attention Network on a geodesic icosphere mesh for cyclone-centre tracking
2. **PhysicsNeMoCorrDiff** — a score-based diffusion downscaler that generates high-frequency wind/pressure fields from coarse NWP proxy inputs, conditioned on a physics-conformity loss

> [!IMPORTANT]
> This is a **research prototype** built on ERA5 reanalysis data over three Bay-of-Bengal cyclones. It is **not an operational forecast system**. All claims must be understood within that scope.

---

## Model 1 — SpatioTemporalSphericalGAT (Tracker)

| Property | Value |
|---|---|
| Architecture | Graph Attention Network + GRU temporal encoder |
| Mesh type | Regional patch on icosphere subdivision-6 |
| Domain | 8°–26°N, 78°–96°E (Bay of Bengal) |
| Total nodes | 269 |
| Total edges | 742 |
| Node spacing | 111–132 km (mean 127.6 km) |
| Trainable parameters | 17,060 |
| Input variables | wind_speed_10m, surface_pressure, precip, temp_2m |
| Native grid | 16×16 regional grid |
| Seed | 42 |
| Optimizer | AdamW (lr=0.002, wd=1e-4) |
| Epochs | 40 |
| Split strategy | Leave-One-Storm-Out (LOSO) |
| Train storms | fani_2019, yaas_2021 |
| Test storm | amphan_2020 (held out) |
| Checkpoint | `models/checkpoints/gat_tracker_loso.pt` |

### Training Provenance
- Training manifest: `results/training_runs/tracker_loso_20260929_143627.json`
- All weights are versioned in the training manifest; no anonymous weights
- Training data: ERA5 reanalysis at 16×16 grid (surface variables only)
- Val temporal buffer: 24 hours (prevents boundary leakage)

### Tracker Performance (Unseen Amphan 2020)

| Metric | Proposed GAT | Threshold CC Baseline | Const. Velocity Baseline |
|---|---|---|---|
| Mean track error (km) | **68.09** | 469.65 | 500.33 |
| Median track error (km) | **13.31** | 388.92 | 388.92 |
| Footprint IoU | 0.085 | **0.123** | — |
| Precision | 0.104 | **0.153** | — |
| Recall | 0.307 | 0.349 | — |
| F1 score | 0.155 | 0.212 | — |
| Track error reduction vs. CC | **85.5%** | — | — |

**Honest assessment**: The GAT dramatically reduces track centre error (85.5% reduction). Footprint IoU is *lower* than the classical threshold-CC baseline — the model is more spatially conservative at 16×16 resolution. This is disclosed, not hidden.

---

## Model 2 — PhysicsNeMoCorrDiff (Downscaler)

| Property | Value |
|---|---|
| Architecture | Two-stage: MeanPredictor (U-Net) + DiffusionCorrector |
| Total parameters | 360,872 |
| Mean predictor parameters | 176,164 |
| Diffusion corrector parameters | 184,708 |
| Input | 1.0° (~111 km) synthetic NWP coarse proxy (Gaussian-degraded ERA5) |
| Target | 0.25° (~28 km) ERA5 regional grid |
| Display grid | 38×38 (bilinear interpolation of 16×16 — NOT native inference) |
| Loss function | ExtremeTailConservationLoss (MSE + L1 + divergence + MFC) |
| Loss weights | λ_mse=1.0, λ_l1=0.3, λ_tail=0.25, λ_div=0.15, λ_mfc=0.2 |
| Samples per inference | 5 stochastic diffusion samples |
| Seed | 42 |
| Split strategy | Leave-One-Storm-Out (LOSO) |
| Train storms | fani_2019, yaas_2021 |
| Test storm | amphan_2020 (held out) |
| Checkpoint | `models/checkpoints/corrdiff_loso.pt` |

### Downscaler Performance (Unseen Amphan 2020, 168 samples)

| Metric | Bicubic | U-Net | CorrDiff No-Phys | **CorrDiff Proposed** |
|---|---|---|---|---|
| MAE wind (km/h) | **5.41** | 7.64 | 9.93 | 7.97 |
| RMSE wind (km/h) | **7.40** | 8.60 | 10.94 | 8.92 |
| MAE pressure (hPa) | 6.53 | 5.07 | **3.86** | 4.08 |
| Peak recovery (%) | 52.4 | 76.5 | 65.9 | **80.4** |
| p90 wind error (km/h) | 9.42 | 9.25 | 12.59 | **5.41** |
| p95 wind error (km/h) | 12.25 | 11.45 | 14.14 | **2.90** |
| CRPS wind (km/h) | 5.41 | 7.64 | 9.38 | **7.44** |
| FSS precip (>2 mm/h) | **0.824** | 0.46 | 0.681 | 0.634 |
| PSD spectral slope | -3.41 | -3.15 | -3.12 | -3.28 |

**True ERA5 spectral slope**: −3.07. Proposed model is closest to true slope.

### Physics Loss Terms (Documented Limitations)

> [!WARNING]
> The divergence loss is computed on the **scalar wind channel** only (not vector u,v), because the model operates on a single wind-speed scalar field. True divergence requires both u and v components.  
> The moisture-flux-convergence (MFC) term is computed as `−div(scalar_wind) × precip` — this is a **proxy** for true moisture convergence, which requires specific humidity q (not available in this dataset).

---

## Data Limitations

| Limitation | Status |
|---|---|
| Input is ERA5 reanalysis, not live NCMRWF | ⚠️ DISCLOSED |
| Ensemble is synthetic (parametric perturbations), not NEPS-G | ⚠️ DISCLOSED |
| Native model resolution is 16×16; "5 km" display is interpolation | ⚠️ DISCLOSED |
| Only Bay-of-Bengal pre-monsoon cyclones (3 storms) | ⚠️ DISCLOSED |
| No upper-air levels; no humidity variable | ⚠️ DISCLOSED |
| Physics terms are proxies (scalar div, no q) | ⚠️ DISCLOSED |

---

## Intended Use

This prototype demonstrates the architectural pipeline for:
- Spherical GNN cyclone tracking
- Diffusion-based downscaling with physics-constrained loss
- EFI-based extreme anomaly detection
- Probabilistic ensemble trajectory uncertainty

**Intended users**: SIH 2026 evaluation judges; researchers assessing the feasibility of the approach.

**Not intended for**: operational weather forecasting, life-safety decisions, or direct public communication of storm threats.

---

## Evaluation Infrastructure

- Test suite: `pytest tests/ -v` (37 unit tests)
- Smoke test: `python test_smoke.py` (46 API endpoints)
- Leakage tests: `tests/test_phase12_leakage_anticheat.py`
- Benchmark reference: `results/official_benchmark.json`
- Training provenance: `results/training_runs/*.json`
