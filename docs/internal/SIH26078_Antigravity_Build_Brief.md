# Build Brief for Antigravity — SIH26078: AI-Driven Spatio-Temporal Tracking of Extreme Weather Anomalies

## Context (read this first, do not skip)

We are building a **scoped-down, working prototype** of a two-stage weather anomaly tracking + downscaling
pipeline, for the SIH 2026 hackathon (organization: NCMRWF / Ministry of Earth Sciences). The full official
spec asks for a global-scale, production-grade system (icosahedral-mesh GNN + physics-informed diffusion
downscaling processing worldwide NWP ensembles). That is not buildable in hackathon time. Instead we are
building **one real, working vertical slice**: tracking Cyclone Amphan (May 2020, Bay of Bengal) using real
public data, with an anomaly-tracking module and a downscaling module that are genuinely functional, not
mocked.

Do not attempt the literal global/production version. Build the scoped version below, get it working
end-to-end, and only then add polish if time remains.

---

## 1. Environment setup

```bash
# Python env
conda create -n weather-tracker python=3.10 -y
conda activate weather-tracker

# Core scientific stack
pip install xarray dask netCDF4 zarr h5py scipy numpy pandas matplotlib cartopy

# ML stack
pip install torch --index-url https://download.pytorch.org/whl/cu121   # adjust CUDA version to the GPU available
pip install huggingface_hub

# API + dashboard
pip install fastapi uvicorn plotly dash

# ERA5 fallback access (only needed if step 2's primary source is insufficient)
pip install cdsapi
```

**Important — ECMWF's Climate Data Store has migrated.** The old legacy CDS API is shut down. If you need
`cdsapi`, you must:
1. Register a **new** account at https://cds.climate.copernicus.eu
2. Get a new personal access token from your profile page
3. Create `~/.cdsapirc` with:
   ```
   url: https://cds.climate.copernicus.eu/api
   key: YOUR_PERSONAL_ACCESS_TOKEN
   ```
4. Use `cdsapi` version 0.7 or later — anything older, or any tutorial referencing the old
   `cdsapp#!/dataset/...` URLs, will not work.

---

## 2. Data acquisition — PRIMARY SOURCE

Use **IndiaWeatherBench**, a machine-learning-ready dataset built specifically from the IMDAA reanalysis
(the same dataset family the official PS references as "NCUM"/regional reanalysis). This avoids all raw
GRIB/NetCDF wrangling and avoids needing a fresh NCMRWF data-portal registration.

- Hosted at: `https://huggingface.co/datasets/tungnd/IndiaWeatherBench`
- **Spatial domain**: 6°N–36.72°N latitude, 66.6°E–97.25°E longitude → a 256×256 grid at native 0.12°
  (~12 km) resolution. This fully covers the Bay of Bengal / Cyclone Amphan region (roughly 10–25°N,
  80–95°E), so no separate regional crop is needed.
- **Temporal coverage**: 20 years, 2000–2019, subsampled to 6-hour intervals (00/06/12/18 UTC).
  Pre-split into train (2000–2017, ~26,500 samples), validation (2018, ~1,500 samples), and
  test (2019, ~1,500 samples).
- **Variables (43 channels)**:
  - Single-level: 2m temperature (TMP), 10m U/V wind (UGRD/VGRD), total precipitation (APCP),
    mean sea level pressure (PRMSL), total cloud cover (TCDCRO)
  - Pressure-level (at 50, 250, 500, 600, 700, 850, 925 hPa): temperature (TMP_prl), geopotential
    height (HGT), U/V wind (UGRD_prl/VGRD_prl), relative humidity (RH)
  - Static fields: terrain height (MTERH), land cover (LAND)
- **Formats available**: Zarr (`indiaweatherbench_raw.zarr.zip`, ~101 GB) and HDF5
  (`indiaweatherbench_h5.zip`, ~106 GB), plus a precomputed climatology
  (`climatology_2000_2017.zarr.zip`, ~9 GB) — **use this precomputed climatology directly, do not
  recompute it from scratch**, it saves a large amount of processing time and is exactly the baseline
  needed for the anomaly z-score step below.
- **License: CC-BY-NC-SA-4.0** (non-commercial, share-alike). Fine for a hackathon prototype — flag this
  license explicitly in the submission/demo materials, and credit the dataset authors
  (Tung Nguyen, Harkanwar Singh, Nilay Naharas, Lucas Bandarkar, Aditya Grover) plus the underlying
  IMDAA/NCMRWF acknowledgement below.

```python
from huggingface_hub import hf_hub_download

# Download only the climatology + a working year subset first, not the full 216 GB
hf_hub_download(repo_id="tungnd/IndiaWeatherBench", filename="climatology_2000_2017.zarr.zip",
                 repo_type="dataset", local_dir="./data")
# For the event data, pull whichever year file covers May 2020 from indiaweatherbench_h5.zip / raw.zarr.zip
```

**Required acknowledgement text** (include in your submission, per NCMRWF's data terms):
> "Authors gratefully acknowledge NCMRWF, Ministry of Earth Sciences, Government of India, for IMDAA
> reanalysis. IMDAA reanalysis was produced under the collaboration between UK Met Office, NCMRWF and IMD."

### Fallback source (only if 2020 event data isn't cleanly covered)
Pull ERA5 directly via the new CDS API (see setup above) for a Bay of Bengal bounding box
(10–25°N, 80–95°E), May 16–21 2020, hourly, variables: `10m_u_component_of_wind`,
`10m_v_component_of_wind`, `mean_sea_level_pressure`, `total_precipitation`.

---

## 3. Repository structure

```
weather-anomaly-tracker/
├── data/
│   ├── raw/                    # downloaded IndiaWeatherBench / ERA5 files
│   └── climatology/             # precomputed climatology from IndiaWeatherBench
├── src/
│   ├── data_loader.py          # loads Zarr/HDF5, handles IndiaWeatherBench + ERA5 fallback
│   ├── anomaly_detect.py       # z-score anomaly field + blob detection + centroid tracking
│   ├── downscale/               # adapted PhysicsNeMo CorrDiff module (see step 5)
│   ├── api.py                  # FastAPI app: /track, /downscale
│   └── train_downscale.py
├── external/
│   └── physicsnemo/            # cloned NVIDIA/physicsnemo repo (see step 5)
├── dashboard/                   # Plotly Dash or Leaflet/React map frontend
├── models/                      # saved weights
└── requirements.txt
```

---

## 4. Anomaly detection & tracking module

1. Load the precomputed climatology (mean + std per grid cell, per day-of-year) from
   `climatology_2000_2017.zarr.zip`.
2. For the event window (May 16–21, 2020), compute a per-cell, per-timestep z-score anomaly:
   `z = (value - climatological_mean) / climatological_std`, for wind speed, MSLP, and precipitation.
   This is a legitimate, simplified stand-in for the official PS's "Extreme Forecast Index (EFI)" —
   describe it in your pitch as "an EFI-inspired anomaly index against a 2000–2017 climatological
   baseline," which is both accurate and defensible.
3. Threshold the anomaly field (e.g. `|z| > 2`) to get a binary mask.
4. Use `scipy.ndimage.label` to find connected blobs in each timestep.
5. Track blob centroids across consecutive timesteps using nearest-centroid matching (no need for a
   Kalman filter or anything more elaborate for a demo).
6. Output a list of `(timestamp, lat, lon, bounding_box, severity)` — this is your "4D bounding box
   trajectory."

**Stretch goal only, do not block on this**: NVIDIA/physicsnemo ships a maintained **GraphCast** example
under `examples/weather/graphcast` in the same repository used for downscaling in step 5. If time
remains, this is the reference implementation to adapt for a genuine mesh-based GNN tracker, rather than
writing icosahedral mesh code from scratch. Treat it as a bonus slide in the pitch, not a dependency for
the working demo.

---

## 5. Downscaling module — use NVIDIA PhysicsNeMo's CorrDiff, do not build a diffusion model from scratch

The official PS's "physics-constrained generative diffusion downscaling" is a real, open-source,
documented architecture: **CorrDiff**. It uses a two-step approach — a UNet predicts the mean field,
then a diffusion model stochastically corrects it — which isolates generative learning to the
small-scale/stochastic part of the problem (analogous to Reynolds decomposition in fluid dynamics) and
is specifically designed to preserve extremes rather than smooth them out, which is the exact problem
the PS describes.

```bash
git clone https://github.com/NVIDIA/physicsnemo.git external/physicsnemo
cd external/physicsnemo
pip install -e .
# For the physics-informed / PINN pieces specifically:
pip install "nvidia-physicsnemo[sym]"
```

- Use the **CorrDiff-Mini** example at `examples/weather/corrdiff` as your starting point. It is
  explicitly built for adaptation/learning: a smaller architecture plus a reduced dataset cuts training
  time from thousands of GPU-hours down to **around 10 hours on a single A100** — a realistic number for
  a rented cloud GPU during the hackathon window.
- Swap CorrDiff-Mini's default HRRR-based data loader for your IndiaWeatherBench regional crop: condition
  on the coarser (subsampled/blurred) 0.12° field, target the native-resolution field, following the same
  "predict mean via UNet, correct via diffusion" pattern.
- You get the extreme-value preservation property largely "for free" from this architecture — you do not
  need to hand-write a custom physics-informed loss function penalizing missing moisture convergence
  vectors etc. That part of the official spec is satisfied by CorrDiff's design itself; describe it
  accurately as such in your pitch rather than claiming a full PDE-constrained loss you didn't implement.

**Compute planning**: reserve cloud GPU time (Colab Pro+, Lambda, RunPod, or similar) early — this is the
single longest-pole item in the whole build. Don't discover the GPU budget problem on the last day.

---

## 6. API & dashboard

- FastAPI app (`src/api.py`) with two endpoints:
  - `GET /track?start=...&end=...` → returns tracked anomaly bounding boxes/centroids for the date range
  - `GET /downscale?anomaly_id=...` → returns the CorrDiff-sharpened field for a specific tracked anomaly
- Dashboard (Plotly Dash or a Leaflet/React map): plot the coarse anomaly track as a moving marker over
  the Bay of Bengal; clicking a point reveals the downscaled field as a heatmap; color-code severity
  (low/moderate/severe) using the z-score thresholds from step 4.

---

## 7. Demo script (write this before finishing the build — it shapes what actually needs to work)

"Here is Cyclone Amphan approaching the Bay of Bengal on May 18, 2020. Our system flags the anomaly using
deviation from a 2000–2017 climatological baseline, tracks its trajectory across the forecast window, and
sharpens the impact zone using a generative correction-diffusion model — recovering the true peak wind
intensity and rainfall extremes that a standard averaging-based model would smooth away."
Show a clear before/after comparison: coarse 0.12° input vs. CorrDiff-sharpened output, side by side.

---

## 8. Order of operations for Antigravity — execute in this sequence

1. Set up the conda environment and install all dependencies listed in section 1.
2. Write `src/data_loader.py`: download the IndiaWeatherBench climatology file and the May 2020 event
   data from Hugging Face (`tungnd/IndiaWeatherBench`) via `huggingface_hub`; fall back to the new CDS API
   only if the event window isn't cleanly covered.
3. Write `src/anomaly_detect.py`: z-score anomaly computation against the precomputed climatology, blob
   detection via `scipy.ndimage.label`, centroid tracking across timesteps.
4. Clone `github.com/NVIDIA/physicsnemo` into `external/physicsnemo`, install it, and adapt the
   `examples/weather/corrdiff` (CorrDiff-Mini) data loader and training script to ingest the
   IndiaWeatherBench regional crop instead of its default HRRR data.
5. Train the adapted CorrDiff-Mini model on rented cloud GPU time; save weights to `models/`.
6. Write `src/api.py` (FastAPI, `/track` and `/downscale` endpoints) wiring together steps 3 and 5.
7. Build the dashboard: map view with tracked anomaly markers, click-through to the downscaled heatmap,
   severity color-coding.
8. Only if all of the above works end-to-end and time remains: adapt the `examples/weather/graphcast`
   example from the same PhysicsNeMo repo as a genuine GNN-based version of the tracking step from #3.

---

## 9. Citations to include in the final submission

- IndiaWeatherBench dataset (CC-BY-NC-SA-4.0): Nguyen, Singh, Naharas, Bandarkar, Grover —
  "IndiaWeatherBench: A Dataset and Benchmark for Data-Driven Regional Weather Forecasting over India,"
  code at `github.com/tung-nd/IndiaWeatherBench`.
- NCMRWF/IMDAA acknowledgement text as given in section 2.
- If ERA5 fallback data is used: "Contains modified Copernicus Climate Change Service information," with
  the standard ERA5 hourly-data citation (Hersbach et al. 2018, DOI 10.24381/cds.adbb2d47).
- NVIDIA PhysicsNeMo / CorrDiff as the downscaling architecture basis, `github.com/NVIDIA/physicsnemo`.
