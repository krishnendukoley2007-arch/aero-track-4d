# Data & Model Asset Licenses

This document formally records the terms of use, licensing, and attribution for all datasets, reanalyses, observational archives, and software components utilized or referenced in the **AERO-TRACK 4D** repository.

---

## 1. Software Code License

- **License**: [MIT License](../LICENSE)
- **Copyright**: (c) 2026 AERO-TRACK 4D Contributors
- **Scope**: All source code under `src/`, `scripts/`, `tests/`, and dashboard user interface components under `docs/` and `dashboard/` (excluding third-party bundled vendor libraries).

---

## 2. Atmospheric & Meteorological Data Assets

### A. ECMWF ERA5 Reanalysis
- **Provider**: European Centre for Medium-Range Weather Forecasts (ECMWF) via Copernicus Climate Change Service (C3S).
- **License**: **Copernicus Licence** (Creative Commons Attribution 4.0 International — CC BY 4.0 / Copernicus Terms).
- **Terms of Use**:
  - Worldwide, royalty-free, non-exclusive license to use, reproduce, adapt, and distribute Copernicus data and products for both commercial and non-commercial purposes.
- **Mandatory Attribution**:
  - *"Contains modified Copernicus Climate Change Service information [2020]. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains."*
  - DOI: [10.24381/cds.143582cf](https://doi.org/10.24381/cds.143582cf)
- **Repository Usage**: Reanalysis grids for Cyclones Amphan (2020), Fani (2019), and Yaas (2021) stored in `data/raw/` and `data/climatology/`.

### B. NOAA IBTrACS (International Best Track Archive for Climate Stewardship)
- **Provider**: National Oceanic and Atmospheric Administration (NOAA) / National Centers for Environmental Information (NCEI) / World Meteorological Organization (WMO).
- **License**: **Public Domain (U.S. Government Work)**.
- **Terms of Use**:
  - Free and unrestricted global access.
- **Attribution & Reference**:
  - Knapp, K. R., et al. (2018). *The International Best Track Archive for Climate Stewardship (IBTrACS)*. Bulletin of the American Meteorological Society (BAMS).
  - Agency of record for North Indian Ocean basin: **India Meteorological Department (IMD), New Delhi**.
- **Repository Usage**: Historical cyclone best-track trajectories, central pressure, and sustained wind ground-truth observations in `data/raw/`.

### C. NCMRWF IMDAA (Indian Monsoon Data Assimilation and Analysis)
- **Provider**: National Centre for Medium Range Weather Forecasting (NCMRWF), Ministry of Earth Sciences (MoES), Government of India, in collaboration with the UK Met Office and IMD.
- **License / Terms**:
  - Scientific and academic research access governed by NCMRWF / MoES data policy.
- **Mandatory Acknowledgment**:
  - *"Authors gratefully acknowledge National Centre for Medium Range Weather Forecasting (NCMRWF), Ministry of Earth Sciences, Government of India, for providing IMDAA regional reanalysis. IMDAA was produced under the collaborative project between UK Met Office, NCMRWF, and IMD."*
- **Repository Usage**: Target dataset for high-resolution 12 km regional downscaling (Phase 2 and Phase 4).

### D. IndiaWeatherBench
- **Provider**: Stanford University / Nguyen et al.
- **License**: **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.
- **Citation**:
  - Nguyen, T. D., Singh, R., Naharas, S., Bandarkar, S., & Grover, A. (2023). *IndiaWeatherBench: Benchmarking Medium-Range Weather Forecasting in India*.
- **Repository Usage**: Historical baseline reference and multi-decade evaluation protocols.

---

## 3. Bundled Third-Party Frontend Libraries

| Library | Version | License | Upstream Source |
|---|---|---|---|
| **Three.js** | r128 | MIT | [threejs.org](https://threejs.org/) |
| **OrbitControls.js** | r128 | MIT | Three.js Authors |
| **Lucide Icons** | Latest | ISC / MIT | [lucide.dev](https://lucide.dev/) |
| **Leaflet.js** | 1.9.4 | BSD-2-Clause | [leafletjs.com](https://leafletjs.com/) (loaded via CDN) |
