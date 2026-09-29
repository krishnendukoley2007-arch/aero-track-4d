# AERO-TRACK-4D — ONE-DAY MASTER ANTIGRAVITY EXECUTION PROMPT
## SIH 26078 | Emergency One-Day Scientific + Engineering Upgrade Plan

> **READ THIS FIRST**
>
> This is the controlling execution prompt for the current AERO-TRACK-4D repository.
> The team has approximately ONE DAY. Do not attempt a full research-grade operational weather system.
> Instead, make the existing project substantially stronger, scientifically defensible, reproducible, and judge-ready.
>
> **CRITICAL:** Work phase-by-phase. NEVER commit, push, retrain, download large datasets, or change scientific definitions without the approval gate for that phase.
>
> The external reviewer will inspect every checkpoint and may reject the work.

---

# 1. PROJECT TARGET

Problem Statement:

**SIH26078 — AI-Driven Spatio-Temporal Tracking of Extreme Weather Anomalies in Medium-Range Forecasts**

The intended system must address:

- 3–10 day medium-range prediction
- multivariable 4D ensemble forecast information
- extreme weather anomaly identification
- spatio-temporal tracking
- spherical/geodesic graph modelling
- EFI-style anomaly information relative to climatology
- localization of extreme threats
- conditional diffusion downscaling
- preservation of extreme amplitude
- physically defensible constraints
- uncertainty-aware outputs
- interactive visualization
- alert API

The target must be treated as a scientific engineering problem, NOT as a dashboard-building competition.

---

# 2. CURRENT REPOSITORY REALITY — START FROM THIS

Before touching anything, assume the following current state until proven otherwise:

### Real/current
- Historical ERA5 reanalysis data exists for Amphan, Fani and Yaas.
- NOAA/IBTrACS best-track data exists for verification.
- A spherical GAT architecture and fixed checkpoint exist.
- A CorrDiff/diffusion-style downscaling architecture exists.
- A Standard U-Net baseline exists.
- A medium-range ensemble visualization exists.
- API and dashboard are substantial.
- Deterministic seed=42 wiring has been added.
- Current repository test count has recently been observed as 27.

### Limitations
- Current atmospheric input is ERA5/reanalysis or ERA5-derived proxy, NOT an operational NCMRWF forecast.
- Current 10-member medium-range trajectory engine is simulated/parametric, NOT actual NEPS-G.
- Current coarse field is generated from ERA5 through synthetic degradation.
- Current model executes on approximately 16×16 and the 38×38 / 5 km-looking display is interpolation, not native 5 km model inference.
- GAT checkpoint training provenance is incomplete unless newly established from evidence.
- Fani/Yaas current zero-shot evaluation is limited and must not automatically be called full LOSO generalization.
- Existing scientific benchmarks may contain historical methodology changes and must be audited before new training.

### GOVERNING RULE

Do not “fix” these limitations by changing words alone.
Either generate evidence or label the limitation accurately.

---

# 3. ONE-DAY OBJECTIVE

By the end of the day, produce the strongest defensible prototype possible.

Priority order:

## P0 — Integrity
No unsupported claims, no hidden scaling, no leakage, no credential problems, no metric ambiguity.

## P1 — Scientific core
Improve the tracking + anomaly + uncertainty pipeline and run meaningful storm-separated tests.

## P2 — AI training
Train only models that can be trained and evaluated reproducibly today.

## P3 — Downscaling
Make the diffusion/U-Net experiment scientifically measurable using a valid paired-resolution proxy.

## P4 — Medium-range architecture
Make the forecast/ensemble path structurally ready for actual ensemble NWP data.

## P5 — Demo
Synchronize API/dashboard/docs with actual measurements.

DO NOT spend the day adding decorative AI features.

---

# 4. MASTER RULE: EVIDENCE > FEATURES

Every new feature must have:

```text
Hypothesis
Input dataset
Train/validation/test split
Training configuration
Baseline
Metric
Result
Ablation
Limitation
```

If one is missing, the feature is prototype-only and must be labelled accordingly.

---

# 5. PHASE 0 — FREEZE + FORENSIC AUDIT
## NO SCIENTIFIC CHANGES

Inspect the entire current repository.

Run:

```powershell
git status
git log --oneline -15
git branch -vv
git remote -v
pytest -q
python test_smoke.py
```

Search:

```powershell
git grep -n -iE "population|citizens_|BTS|handshake|evacuated|remaining|NEPS|NEPS-G|NCMRWF|forecast|reanalysis|simulated|parametric|5 km|12 km|trained|checkpoint|CorrDiff|EFI|physics"
```

Inspect:

```text
src/data_loader.py
src/spherical_gnn.py
src/ensemble_medium_range.py
src/downscale/
src/corrdiff_model.py
src/train_downscale.py
src/api.py
models/
results/
tests/
README.md
WALKTHROUGH.md
dashboard/
docs/
```

Create:

```text
docs/ONE_DAY_BASELINE_AUDIT.md
```

Report:
- current git state
- modified files
- test count
- model checkpoints
- training provenance
- dataset provenance
- current benchmark definitions
- current scientific gaps
- current public claims that are not supported

### GATE 0
STOP.
Wait for reviewer approval.

---

# 6. PHASE 1 — CLEAN PUBLIC SCIENTIFIC SEMANTICS

Only after Gate 0 approval.

Remove or isolate from the SIH scientific path:

- unsupported population impact numbers
- invented/unsupported BTS counts
- unsupported humanitarian metrics
- “false alarm reduction” based only on geometry
- “citizens shielded”
- “surgical zone”
- “saved”
- “beats U-Net” unless actually demonstrated
- claims that ERA5 is a forecast
- claims that simulated ensembles are NEPS-G
- native 5 km claims when output is interpolated
- trained-checkpoint claims without training provenance

Keep non-SIH modules only when clearly labelled as:
```text
SIMULATION
DEMO
PROTOTYPE
EXTERNAL-INTEGRATION PLACEHOLDER
```

Every API response must expose provenance.

### Required provenance schema

```json
{
  "data_source_type": "ERA5_REANALYSIS|FORECAST|SIMULATED|OBSERVATION",
  "data_source": "...",
  "forecast_status": "NOT_A_FORECAST|REAL_FORECAST|PROXY",
  "model_status": "TRAINED|FIXED_CHECKPOINT|SIMULATED|UNVALIDATED",
  "verification_status": "...",
  "seed": 42
}
```

### GATE 1
Run:
```powershell
git grep -n -iE "population|citizens_|BTS|handshake|evacuated|remaining|false.?alarm|shielded|surgical|saved"
pytest -q
```

STOP.
Wait for approval.

---

# 7. PHASE 2 — TRAINING DATA: ONE-DAY FEASIBLE STRATEGY

## IMPORTANT

Do NOT try to build a giant global dataset today.

Use a compact, reproducible regional Bay-of-Bengal training set.

---

## DATASET A — EXISTING REAL ERA5 STORMS

Use existing:

```text
Amphan 2020
Fani 2019
Yaas 2021
```

Source:
ECMWF ERA5 reanalysis.

Use variables already available and expand where feasible:

Minimum:
- u/v or wind speed
- MSLP
- precipitation
- 2m temperature

Optional:
- humidity
- 850 hPa wind
- 500 hPa geopotential/temperature
- vorticity

ERA5 is reanalysis, not an operational forecast. Preserve that distinction.

---

## DATASET B — IBTrACS

Use existing storm best tracks for verification.

Do NOT use best-track labels as features unless the experiment explicitly defines them as training labels.

---

## DATASET C — RAPID EXTRA STORM WINDOWS

If already accessible without credentials, add 2–5 additional historical Bay-of-Bengal cyclones from ERA5 + IBTrACS.

Do not spend more than the available time trying to find a perfect dataset.

Candidate events can include, subject to data availability:
- Hudhud
- Phailin
- Ockhi
- Titli
- Bulbul
- Amphan
- Fani
- Yaas

Use date-specific windows rather than downloading the entire globe.

---

## DATASET D — CLIMATOLOGY

For EFI/climatology, do NOT create a climatology from only Amphan.

Use a sufficiently broad historical ERA5 sample if feasible.

At minimum:
- same region
- same variables
- multiple years
- same seasonal period
- documented sample count

If a proper climatology cannot be assembled in one day, keep:

```text
efi_type = "efi_inspired_proxy"
```

and do not call it true EFI.

---

# 8. DATA SPLIT — ABSOLUTELY NO STORM LEAKAGE

Preferred:

```text
TRAIN = several storms
VALIDATION = different storm(s)
TEST = completely unseen storm
```

Use storm-level splitting, not timestep-level splitting.

Example:

```text
TRAIN:
Phailin
Hudhud
Bulbul

VALIDATION:
Fani

TEST:
Amphan

Secondary:
Yaas
```

If the available dataset cannot support this exact split, automatically construct the strongest possible storm-separated split and report it.

Never allow adjacent timesteps from the test storm into training.

Never tune on the final test storm.

---

# 9. TRAINING DATA GENERATION

Create:

```text
scripts/build_training_dataset.py
configs/training_dataset.yaml
data/processed/dataset_manifest.json
```

Generate samples with sliding temporal windows.

Example:

```text
input:
T-6h, T-3h, T
target:
T+6h / T+12h / T+24h
```

For anomaly tracking, also support:

```text
past window → current anomaly → future displacement
```

For downscaling proxy training:

```text
0.25° ERA5 target
        ↑
coarsened ERA5 input
```

This is a legitimate paired-resolution experiment at ERA5 scale.

It must NOT be called 5 km truth.

Use synthetic super-resolution only as a controlled experiment.

---

# 10. PHASE 3 — AI TRACKER

Build a real learnable spherical model.

Architecture:

```text
multivariable input
      ↓
feature encoder
      ↓
spherical/geodesic mesh
      ↓
Graph Attention layers
      ↓
temporal attention / ConvLSTM / temporal Transformer
      ↓
anomaly probability
      ↓
centroid + footprint + trajectory
```

The GAT must contain learnable parameters.

Train it.

Log:

```text
parameter count
optimizer
learning rate
batch size
epochs
seed
train samples
validation samples
checkpoint
best validation metric
```

Create:

```text
configs/tracker.yaml
scripts/train_tracker.py
results/training_runs/
```

---

# 11. TRACKING BASELINES

Mandatory:

### Baseline 1
Threshold + connected components.

### Baseline 2
Constant-velocity/Kalman tracker.

### Proposed
Spherical GAT + temporal module.

Compare:

```text
track error km
centroid error km
time error h
footprint IoU
detection precision
detection recall
F1
```

Do not use only one metric.

---

# 12. PHASE 4 — PROPER EFI

Implement:

```text
Forecast ensemble CDF
          vs
Historical climatological CDF
          ↓
EFI / anomaly index
```

For wind and precipitation.

Required output:

```json
{
  "efi_type": "true_ensemble_climatology",
  "forecast_source": "...",
  "climatology_source": "...",
  "ensemble_members": 20,
  "lead_hours": 72
}
```

If actual forecast ensemble data is not available today:

keep the existing parametric ensemble as:

```text
SIMULATED/PARAMETRIC
```

and implement the true EFI algorithm against a test fixture or small proxy ensemble only if it can be verified.

Do not invent operational NEPS results.

---

# 13. PHASE 5 — MEDIUM-RANGE FORECAST PATH

The target architecture must accept:

```text
forecast_initialization
forecast_valid_time
lead_hours
ensemble_member
lat
lon
variables
```

Support lead times:

```text
72h
96h
120h
168h
240h
```

The current simulated 10-member engine remains a fallback.

Label:

```text
Current:
SIMULATED/PARAMETRIC

Target:
REAL NCMRWF NEPS-G / compatible ensemble forecast
```

If legitimate public historical TIGGE data can be retrieved quickly, use it as a **forecast-data proxy**, not as NEPS-G.

TIGGE contains historical global medium-range ensemble forecasts from multiple NWP centres and typically extends 10–15 days, making it a useful documented development source.

---

# 14. PHASE 6 — DOWNSCALING TRAINING

Do NOT claim 5 km truth using the current 16×16 ERA5 setup.

Train a valid paired-resolution experiment:

```text
coarsened 1° ERA5
       ↓
U-Net
       ↓
0.25° ERA5 target
```

Then:

```text
coarsened input
       ↓
CorrDiff / diffusion
       ↓
0.25° target
```

This gives a real supervised coarse→fine experiment.

The operational 12 km→5 km path remains:

```text
FUTURE / TARGET ARCHITECTURE
```

unless a real higher-resolution target dataset is obtained.

---

# 15. DOWNSCALING BASELINES

Compare:

```text
Bicubic
U-Net
CorrDiff
```

Metrics:

### Standard
- MAE
- RMSE

### Extreme-aware
- P90 error
- P95 error
- P99 error
- maximum wind error
- extreme precipitation exceedance error

### Spatial
- SSIM
- gradient similarity
- spectral error
- spatial correlation

### Conservation/consistency
- coarse-grid reconstruction error

---

# 16. EXTREME-AWARE LOSS

Use:

```text
L =
λ1 * reconstruction
+ λ2 * extreme_tail
+ λ3 * gradient/spectral
+ λ4 * coarse_consistency
+ λ5 * physically_valid_constraint
```

Do not invent λ values after seeing test results.

Tune λ using training/validation only.

For each term create an ablation.

---

# 17. PHYSICS CONSTRAINT

DO NOT force surface cyclone divergence to zero.

Prefer:

- coarse-grid consistency
- vector consistency
- precipitation non-negativity
- physically sensible wind ranges
- spectral consistency
- mass/flux relationships only when variables support them

If moisture-flux convergence is used, humidity must be an actual input.

Every physics term needs:

```text
with physics
vs
without physics
```

---

# 18. PHASE 7 — UNCERTAINTY

Produce:

```text
P10
P50
P90
```

and exceedance probabilities:

```text
P(wind > threshold)
P(rain > threshold)
```

For trajectory:

```text
ensemble member paths
ensemble mean
spread
confidence region
```

Distinguish:

```text
NWP ensemble uncertainty
Generative diffusion uncertainty
Verification uncertainty
```

Do not call five CorrDiff samples “five meteorological ensemble members.”

---

# 19. PHASE 8 — ALERT GENERATION

Alerts must derive from the predicted field.

Pipeline:

```text
fine field
↓
threshold exceedance
↓
probability map
↓
connected region
↓
polygon
↓
severity
↓
lead time
```

No arbitrary warning circles.

Output:

```json
{
  "event_type": "cyclone",
  "severity": "severe",
  "probability": 0.88,
  "lead_hours": 120,
  "polygon_source": "model_probability_contour",
  "data_source_type": "...",
  "verification_status": "prototype"
}
```

Do not add population counts.

---

# 20. PHASE 9 — DASHBOARD

Dashboard must show the model honestly.

Required labels:

```text
REAL REANALYSIS
REAL FORECAST
FORECAST PROXY
SIMULATED ENSEMBLE
FIXED CHECKPOINT
TRAINED MODEL
DISPLAY INTERPOLATION
NATIVE MODEL GRID
```

Required screens:

1. Extreme anomaly map
2. EFI/anomaly map
3. Spherical GNN tracking
4. Ensemble trajectory
5. Coarse/U-Net/CorrDiff comparison
6. P90/extreme risk
7. Alert polygon
8. Lead-time verification
9. Calibration
10. Provenance/model card

---

# 21. PHASE 10 — API

Every endpoint must return:

```json
{
  "data_source_type": "...",
  "data_source": "...",
  "forecast_status": "...",
  "lead_hours": null,
  "ensemble_members": null,
  "model_name": "...",
  "model_version": "...",
  "checkpoint": "...",
  "seed": 42,
  "native_grid": "...",
  "display_grid": "...",
  "verification_status": "..."
}
```

No API field should make interpolated 38×38 output appear to be native 5 km model resolution.

---

# 22. PHASE 11 — TRAINING RUN GOVERNANCE

Every run creates:

```text
results/training_runs/<run_id>.json
models/checkpoints/<run_id>.pt
```

Manifest:

```json
{
  "run_id": "...",
  "git_commit": "...",
  "dataset_hash": "...",
  "train_storms": [],
  "validation_storms": [],
  "test_storms": [],
  "samples": {},
  "architecture": {},
  "hyperparameters": {},
  "seed": 42,
  "best_validation_metric": {},
  "test_metrics": {},
  "checkpoint": "..."
}
```

No anonymous weights.

---

# 23. PHASE 12 — LEAKAGE + ANTI-CHEATING TESTS

Add tests for:

- storm-level split integrity
- no test timestamps in training
- no target contamination
- no hyperparameter contamination
- no normalization leakage
- no arbitrary output scaling
- native/display resolution semantics
- provenance on API outputs
- benchmark JSON consistency
- README metric-table consistency

For anti-scaling:

The test must:
1. extract raw network output
2. call public inference
3. reconstruct expected public output using only explicitly documented transforms
4. compare numerically
5. fail when an undocumented multiplier is injected

Do NOT claim a mean-ratio tolerance alone proves no hidden scaling.

---

# 24. PHASE 13 — BENCHMARK PACKAGE

Create:

```text
results/official_benchmark.json
results/ablation_matrix.json
docs/BENCHMARK_CARD.md
docs/MODEL_CARD.md
```

Every metric stores:

```text
value
unit
storm
lead time
dataset
split
model
baseline
metric definition
provenance
```

---

# 25. REQUIRED FINAL EXPERIMENTS

Run, where data exists:

### Experiment A
Classical tracker vs GNN

### Experiment B
Proxy EFI vs proper EFI

### Experiment C
Bicubic vs U-Net vs CorrDiff

### Experiment D
Without extreme-tail loss vs with

### Experiment E
Without physics consistency vs with

### Experiment F
Deterministic vs probabilistic output

### Experiment G
Performance by forecast lead time

### Experiment H
Unseen-storm evaluation

---

# 26. FINAL RESULTS MUST ANSWER THESE QUESTIONS

1. Does the GNN beat a classical tracker?
2. Does the anomaly system detect extremes reliably?
3. Does EFI add information beyond simple thresholding?
4. Does CorrDiff beat bicubic?
5. Does CorrDiff beat U-Net on extreme-tail preservation?
6. Does uncertainty calibrate?
7. Does performance degrade sensibly with lead time?
8. Does the model work on an unseen storm?
9. Does the alert polygon come from the model field?
10. What is still not operational?

If an answer is “no”, report it.

Do NOT manufacture a positive answer.

---

# 27. ONE-DAY TIME BUDGET

## First 1–2 hours
Integrity + data audit.

## Next 2 hours
Training-data construction + storm-level split.

## Next 2–3 hours
Train/fine-tune the strongest feasible tracking model.

## Next 2–3 hours
Train/benchmark the strongest feasible downscaler.

## Next 1 hour
Uncertainty + alert + API integration.

## Final 1–2 hours
Tests + dashboard + README + judge Q&A.

If a phase is taking too long:

STOP adding features.

Prefer:

```text
one working scientifically defensible result
```

over:

```text
five unfinished AI modules
```

---

# 28. WHAT TO SKIP TODAY

Do NOT spend today's time on:

- huge global datasets
- full operational NCMRWF deployment
- new slide decks
- decorative animations
- unnecessary LLM/chatbot features
- population impact estimation
- unsupported demographic modelling
- multiple redundant neural architectures
- fake real-time data
- excessive front-end polish
- unverified literature-style claims

---

# 29. FINAL DEMO STORY

The demonstration should follow:

```text
Forecast / proxy ensemble
        ↓
Extreme anomaly / EFI
        ↓
Spherical GNN tracking
        ↓
Ensemble trajectory + uncertainty
        ↓
Localized threat footprint
        ↓
Diffusion downscaling
        ↓
Extreme-tail probability
        ↓
Alert polygon
        ↓
Verification metrics
        ↓
Data/model provenance
```

The demo must always identify whether each layer is:
- REAL
- PROXY
- SIMULATED
- TRAINED
- FIXED
- FUTURE

---

# 30. FINAL JUDGE DEFENSE

Create:

```text
docs/JUDGE_QA.md
```

Mandatory questions:

```text
What is your actual forecast input?
Is it real NCMRWF data?
What is simulated?
What is ERA5?
How is EFI computed?
What is the spherical GNN learning?
How was the model trained?
How did you prevent storm leakage?
What exactly does 5 km mean?
What does CorrDiff add?
What baseline did you beat?
How do you verify extreme preservation?
How are probabilities calibrated?
How are alerts generated?
What happens when the model is wrong?
How would NCMRWF ingest the system operationally?
```

Every answer must cite repository evidence.

---

# 31. ABSOLUTE PROHIBITIONS

NEVER:

```text
Change metric definition without disclosure.
Change dataset silently.
Train on test storms.
Use test results for hyperparameter tuning.
Call ERA5 a forecast.
Call synthetic ensemble NEPS-G.
Call interpolation native 5 km.
Call a fixed checkpoint newly trained.
Invent population benefits.
Invent forecast skill.
Invent calibration.
Invent physics.
Invent benchmark improvements.
Commit during a review checkpoint.
Push without explicit reviewer approval.
```

---

# 32. FINAL LOCKDOWN

At final submission:

```text
NO MORE TRAINING
NO MORE MODEL WEIGHT CHANGES
NO MORE METRIC DEFINITION CHANGES
NO MORE DATASET CHANGES
NO MORE UNSUPPORTED CLAIMS
NO MORE UNREQUESTED FEATURES
```

Run:

```powershell
pytest -q
python test_smoke.py
git status
git log --oneline -10
```

Then generate:

```text
docs/FINAL_AUDIT.md
docs/PS26078_COMPLIANCE_MATRIX.md
docs/MODEL_CARD.md
docs/BENCHMARK_CARD.md
docs/JUDGE_QA.md
docs/DEMO_SCRIPT.md
```

---

# 33. CHECKPOINT FORMAT — MANDATORY

At the end of every phase:

```text
CHECKPOINT <NAME>

STATUS:
GREEN / YELLOW / RED

FILES CHANGED:
<exact paths>

COMMANDS EXECUTED:
<exact commands>

RAW OUTPUT:
<real output>

DATA:
<real source + sample counts>

TRAINING:
<none OR exact run>

METRICS:
<exact values + definitions>

SCIENTIFIC INTERPRETATION:
<what the evidence proves>

LIMITATIONS:
<what it does NOT prove>

RISKS:
<remaining concerns>

NEXT ACTION:
<single next action>

NO COMMIT.
NO PUSH.
STOP.
WAIT FOR REVIEWER.
```

---

# 34. START NOW

START ONLY WITH:

## PHASE 0 — FREEZE + FORENSIC AUDIT

Do NOT:
- train
- retrain
- download new data
- redesign the architecture
- modify benchmark definitions
- rewrite README
- commit
- push

First inspect the current repository and produce the required Phase 0 checkpoint.

The external reviewer will decide whether Phase 1 is approved.

---

# 35. CORE PRINCIPLE

The project is not successful because it contains many AI models.

It is successful when a technical judge can trace:

```text
DATA
  ↓
MODEL
  ↓
TRAINING
  ↓
FORECAST/ANOMALY
  ↓
TRACKING
  ↓
DOWNSCALING
  ↓
UNCERTAINTY
  ↓
ALERT
  ↓
VERIFICATION
```

and every arrow is real, measurable, reproducible, and honestly labelled.

**BUILD THE STRONGEST SYSTEM THE EVIDENCE CAN SUPPORT. NEVER BUILD THE CLAIM FIRST.**
