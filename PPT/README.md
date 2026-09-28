# AERO-TRACK 4D: SIH 2026 Presentation Master Pack

**Smart India Hackathon 2026 (Idea Submission)**  
- **Problem Statement ID:** `26078`
- **Problem Statement Title:** <u>AI-Driven Spatio-Temporal Tracking of Extreme Weather Anomalies in Medium-Range Forecasts</u>
- **Theme:** Smart Automation | **Category:** Software
- **Organization:** Ministry of Earth Sciences (MoES) / NCMRWF
- **Team ID:** `126325` | **Team Name:** Omnis Cura

---

## 📁 Folder Contents

| File / Subfolder | Description |
| :--- | :--- |
| **[`SIH26078_OmnisCura_AeroTrack4D.pptx`](SIH26078_OmnisCura_AeroTrack4D.pptx)** | **The Official 6-Slide Presentation Deck** (Formatted strictly to official SIH 2026 rules with Slide 7 deleted). |
| **[`SIH26078_OmnisCura_AeroTrack4D.pdf`](SIH26078_OmnisCura_AeroTrack4D.pdf)** | **Official Submission PDF** (Exact 6-page vector PDF generated via Microsoft PowerPoint COM engine). |
| **[`SIH2026-IDEA-Presentation-Format.pptx`](SIH2026-IDEA-Presentation-Format.pptx)** | Original SIH 2026 clean template source. |
| **[`build_presentation.py`](build_presentation.py)** | Self-contained Python COM automation script to build and export the deck and PDF. |
| **[`slide_previews/`](slide_previews/)** | Full $1920 \times 1080$ high-resolution PNG previews of each slide (Slides 1 through 6). |
| **[`assets/`](assets/)** | Curated, vetted, zero-defect working screenshots and web-rendered architecture diagrams. |

---

## 🖥️ Slide-by-Slide Executive Overview

### [Slide 1: Title Page](slide_previews/slide_1.png)
- Official SIH 2026 Title layout with Team ID `126325`, Team Name `Omnis Cura`, College placeholder, and Underlined Problem Statement Title.
- 4 Verification Badges: `✔ 22/22 Tests Passing`, `⚡ <50 ms GPU Latency`, `🎯 5.0 km Subgrid Target`, `📉 Alert-Corridor Area (78.5 km² vs 3,500 km²)`.

### [Slide 2: Proposed Solution & Innovation](slide_previews/slide_2.png)
- **Left Column:** Operational Challenge & Root Causes (Atmospheric Chaos in 3–10d NWP, Spectral Smoothing Trap, Severe Public Alert Fatigue) and Two-Stage Hybrid AI Solution Architecture.
- **Right Column:** Operational Proof featuring NASA 3D Earth Photorealism over Bay of Bengal, eyewall wind recovery, and 3 key innovation badges ($0.439\%$ Mesh Variance, Kolmogorov $k^{-5/3}$ cascade, alert-corridor area vs assumed district area (geometry, not model skill)).

### [Slide 3: Technical Approach & Pipeline Architecture](slide_previews/slide_3.png)
- **Top Section:** Publication-grade, web-rendered End-to-End Hybrid AI Architecture Diagram ([`assets/clean_architecture_pipeline.png`](assets/clean_architecture_pipeline.png)) showing Stage 00 (4D Ingestion) $\rightarrow$ Stage 01 (Spherical GNN) $\rightarrow$ Stage 02 (CorrDiff Physics Diffusion) $\rightarrow$ Stage 03 (Operational Impact).
- **Bottom Left:** Technology Stack (PyTorch 2.3, JAX, DGL, NVIDIA PhysicsNeMo, MetPy, Cartopy, Xarray, Dask, FastAPI) & Official Datasets (NCMRWF NEPS-G, IMDAA, ERA5, IBTrACS).
- **Bottom Right:** Working Downscaling Lab swipe comparison ($12\text{ km} \rightarrow 5.0\text{ km}$) with the verified error decomposition panel.

### [Slide 4: Feasibility, Viability & Risk Mitigation Analysis](slide_previews/slide_4.png)
- **1. Technical Feasibility:** 22/22 unit & integration tests passing, $<50\text{ ms}$ real-time latency.
- **2. Resource Feasibility:** Precomputed 2000–2017 climatology baseline, accessible compute budget ($\sim 10\text{h}$ on single A100 GPU, $\$25\text{--}\$30$).
- **3. 4D Vertical Sounding & Thermodynamics:** High-resolution Skew-T Log-P Atmospheric Profiler modal ($1000\text{--}200\text{ hPa}$) with Bulk Wind Shear ($8.1\text{ m/s}$), Warm Core ($+6.8^\circ\text{C}$), and Surface CAPE ($2,840\text{ J/kg}$).
- **4. Defensive Risk Mitigation:** Dask parallel I/O, spherical Hungarian vortex tracking, and continuity divergence penalty ($\nabla \cdot \mathbf{V} = 0$).

### [Slide 5: Empirical Benchmarks & Quantified Societal Impact](slide_previews/slide_5.png)
- **Top:** Multi-Storm Generalization Table across Cyclone Amphan (2020), Cyclone Fani (2019) [Unseen], and Cyclone Yaas (2021) [Unseen].
- **Bottom Left:** Actual working screenshot of the hyper-local $5\text{ km}$ alert and automated Ministry of Earth Sciences / IMD National Cyclone Warning Bulletin.
- **Bottom Right:** 4 Quantified Societal Benefits (alert-corridor area vs assumed district area (geometry, not model skill), $+14.2\text{ km}$ accuracy over IMD, 3–10 day structural lead time, democratized supercomputing).

### [Slide 6: Research References, Citations & Data Acknowledgment](slide_previews/slide_6.png)
- **Peer-Reviewed Foundations:** CorrDiff (ICML 2024 / NVIDIA), GraphCast (Science 2023 / DeepMind), EFI (ECMWF 2003), IndiaWeatherBench (Stanford 2023), Score SDE (ICLR 2021).
- **Operational Reports:** IMD RSMC New Delhi (2020), IMD National Cyclone Bulletins (2020), NOAA NCEI IBTrACS v04r01, ECMWF ERA5, WMO Multi-Hazard Guidelines (WMO-No. 1150).
- **Government Acknowledgment:** Formal citation and compliance acknowledgment for NCMRWF, Ministry of Earth Sciences (MoES), Government of India, UK Met Office, and IMD.

---

## 🚀 How to Rebuild Deck & Previews

To regenerate the presentation deck and all slide preview images at any time:

```powershell
python PPT/build_presentation.py
```
