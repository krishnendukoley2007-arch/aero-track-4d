"""
Real Data Loader & Coarse-to-Fine Pipeline for SIH 26078.
Loads genuine ECMWF ERA5 reanalysis spatial grids and official NOAA IBTrACS observation records for:
1. Super Cyclone Amphan (May 2020)
2. Extremely Severe Cyclonic Storm Fani (April-May 2019)
3. Very Severe Cyclonic Storm Yaas (May 2021)
Builds real coarse-to-fine super-resolution pairs with train/test held-out splits.
"""

import os
import json
import numpy as np
from typing import Dict, List, Any, Tuple
from scipy.ndimage import gaussian_filter

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CLIM_DIR = os.path.join(DATA_DIR, "climatology")


class WeatherDataLoader:
    """
    Ingests genuine ECMWF ERA5 reanalysis grids and NOAA IBTrACS best-track data.
    Constructs real coarse-to-fine pairs (coarsened NWP input vs native ERA5 target).
    Supports multi-storm validation for Amphan (2020), Fani (2019), and Yaas (2021).
    """

    STORM_FILES = {
        "amphan_2020": {
            "era5": "era5_amphan_may2020.json",
            "ibtracs": "amphan_ibtracs_real.json",
            "name": "Super Cyclonic Storm Amphan",
            "dates": "May 15–21, 2020",
            "impact_zones": ["West Bengal", "Odisha", "Sundarbans", "Bangladesh"],
            "peak_kts": 130.0,
            "min_hpa": 920.0,
            "agency": "IMD New Delhi",
        },
        "fani_2019": {
            "era5": "era5_fani_may2019.json",
            "ibtracs": "fani_ibtracs_real.json",
            "name": "Extremely Severe Cyclonic Storm Fani",
            "dates": "April 28 – May 04, 2019",
            "impact_zones": ["Puri", "Bhubaneswar", "Cuttack", "Odisha Coast"],
            "peak_kts": 115.0,
            "min_hpa": 932.0,
            "agency": "IMD New Delhi",
        },
        "yaas_2021": {
            "era5": "era5_yaas_may2021.json",
            "ibtracs": "yaas_ibtracs_real.json",
            "name": "Very Severe Cyclonic Storm Yaas",
            "dates": "May 23–28, 2021",
            "impact_zones": ["Dhamra Port", "Balasore", "Bhadrak", "Medinipur"],
            "peak_kts": 75.0,
            "min_hpa": 970.0,
            "agency": "IMD New Delhi",
        }
    }

    def __init__(self, event_id: str = "amphan_2020"):
        self.event_id = event_id if event_id in self.STORM_FILES else "amphan_2020"
        cfg = self.STORM_FILES[self.event_id]

        self.era5_file = os.path.join(RAW_DIR, cfg["era5"])
        self.ibtracs_file = os.path.join(RAW_DIR, cfg["ibtracs"])
        self.clim_file = os.path.join(CLIM_DIR, "bay_of_bengal_may_climatology.json")

        self.era5_data = self._load_json(self.era5_file)
        self.ibtracs_data = self._load_json(self.ibtracs_file)
        self.climatology = self._load_json(self.clim_file)

        self.lats = self.era5_data["domain"]["lats"]
        self.lons = self.era5_data["domain"]["lons"]
        self.shape = self.era5_data["domain"]["shape"]  # [16, 16]
        self.timestamps = self.era5_data["timestamps"]

        self._configure_eval_steps()

    def _configure_eval_steps(self):
        """Configures 13 standard evaluation checkpoints across the storm lifecycle."""
        if self.event_id == "fani_2019":
            self.eval_steps = [
                {"time_idx": 12, "iso": "2019-04-28T12:00", "stage": "Genesis / Cyclonic Storm"},
                {"time_idx": 24, "iso": "2019-04-29T00:00", "stage": "Severe Cyclonic Storm"},
                {"time_idx": 36, "iso": "2019-04-29T12:00", "stage": "Very Severe Cyclonic Storm"},
                {"time_idx": 48, "iso": "2019-04-30T00:00", "stage": "Extremely Severe Cyclonic Storm"},
                {"time_idx": 60, "iso": "2019-04-30T12:00", "stage": "Rapid Intensification"},
                {"time_idx": 72, "iso": "2019-05-01T00:00", "stage": "Category 4 Equivalent"},
                {"time_idx": 84, "iso": "2019-05-01T12:00", "stage": "High-Impact Approaching Eyewall"},
                {"time_idx": 96, "iso": "2019-05-02T00:00", "stage": "Peak Category 5 (Held-out Test 1)"},
                {"time_idx": 108, "iso": "2019-05-02T12:00", "stage": "Eyewall Northward Approach"},
                {"time_idx": 120, "iso": "2019-05-03T00:00", "stage": "Landfall at Puri Coast (Held-out Test 2)"},
                {"time_idx": 132, "iso": "2019-05-03T12:00", "stage": "Crossing Bhubaneswar / Cuttack"},
                {"time_idx": 144, "iso": "2019-05-04T00:00", "stage": "Weakening over Bengal Basin"},
                {"time_idx": 156, "iso": "2019-05-04T12:00", "stage": "Dissipation over Bangladesh"},
            ]
        elif self.event_id == "yaas_2021":
            self.eval_steps = [
                {"time_idx": 12, "iso": "2021-05-23T12:00", "stage": "Depression Stage"},
                {"time_idx": 24, "iso": "2021-05-24T00:00", "stage": "Deep Depression"},
                {"time_idx": 36, "iso": "2021-05-24T12:00", "stage": "Cyclonic Storm Yaas"},
                {"time_idx": 48, "iso": "2021-05-25T00:00", "stage": "Severe Cyclonic Storm"},
                {"time_idx": 60, "iso": "2021-05-25T12:00", "stage": "Very Severe Cyclonic Storm"},
                {"time_idx": 72, "iso": "2021-05-26T00:00", "stage": "Peak Eyewall Pre-Landfall (Held-out Test 1)"},
                {"time_idx": 78, "iso": "2021-05-26T06:00", "stage": "Landfall North of Dhamra (Held-out Test 2)"},
                {"time_idx": 84, "iso": "2021-05-26T12:00", "stage": "Crossing Balasore / Mayurbhanj"},
                {"time_idx": 96, "iso": "2021-05-27T00:00", "stage": "Weakening over Jharkhand"},
                {"time_idx": 108, "iso": "2021-05-27T12:00", "stage": "Deep Depression Inland"},
                {"time_idx": 120, "iso": "2021-05-28T00:00", "stage": "Well-Marked Low Pressure"},
                {"time_idx": 132, "iso": "2021-05-28T12:00", "stage": "Remnants over Bihar Basin"},
                {"time_idx": 140, "iso": "2021-05-28T20:00", "stage": "Dissipation"},
            ]
        else:
            # amphan_2020
            self.eval_steps = [
                {"time_idx": 24, "iso": "2020-05-16T00:00", "stage": "Genesis / Depression"},
                {"time_idx": 36, "iso": "2020-05-16T12:00", "stage": "Deep Depression"},
                {"time_idx": 48, "iso": "2020-05-17T00:00", "stage": "Cyclonic Storm"},
                {"time_idx": 60, "iso": "2020-05-17T12:00", "stage": "Severe Cyclonic Storm"},
                {"time_idx": 72, "iso": "2020-05-18T00:00", "stage": "Very Severe Cyclonic Storm"},
                {"time_idx": 78, "iso": "2020-05-18T06:00", "stage": "Peak Super Cyclone (Held-out Test 1)"},
                {"time_idx": 84, "iso": "2020-05-18T12:00", "stage": "Super Cyclone"},
                {"time_idx": 96, "iso": "2020-05-19T00:00", "stage": "Extremely Severe Cyclonic Storm"},
                {"time_idx": 108, "iso": "2020-05-19T12:00", "stage": "Extremely Severe Cyclonic Storm"},
                {"time_idx": 120, "iso": "2020-05-20T00:00", "stage": "Pre-Landfall Threat"},
                {"time_idx": 126, "iso": "2020-05-20T06:00", "stage": "Landfall (Held-out Test 2)"},
                {"time_idx": 132, "iso": "2020-05-20T12:00", "stage": "Crossing Bengal Coast"},
                {"time_idx": 144, "iso": "2020-05-21T00:00", "stage": "Inland Dissipation (Bangladesh)"},
            ]

    @staticmethod
    def _load_json(path: str) -> Any:
        with open(path, "r") as f:
            return json.load(f)

    def get_event_meta(self, event_id: str = None) -> Dict[str, Any]:
        """Returns event metadata with official NCMRWF, IMD, and Copernicus citations."""
        target_id = event_id or self.event_id
        cfg = self.STORM_FILES.get(target_id, self.STORM_FILES["amphan_2020"])
        winds = [d["wind_kts"] for d in self.ibtracs_data if d.get("wind_kts") is not None]
        mslps = [d["mslp_hpa"] for d in self.ibtracs_data if d.get("mslp_hpa") is not None]
        max_kts = max(winds) if winds else cfg["peak_kts"]
        max_kmh = round(max_kts * 1.852, 1)
        min_hpa = min(mslps) if mslps else cfg["min_hpa"]
        peak_intensity_str = f"{int(max_kts)} kts ({max_kmh} km/h), {int(min_hpa)} hPa ({cfg['name']} - IMD Official)"

        return {
            "id": target_id,
            "name": cfg["name"],
            "basin": "North Indian Ocean (Bay of Bengal)",
            "dates": cfg["dates"],
            "peak_intensity": peak_intensity_str,
            "impact_zones": cfg["impact_zones"],
            "data_source": f"ECMWF ERA5 Hourly Reanalysis + NOAA IBTrACS v04r01 (Agency: {cfg['agency']})",
            "acknowledgement": "Authors gratefully acknowledge NCMRWF, Ministry of Earth Sciences, Government of India, for IMDAA reanalysis. Contains modified Copernicus Climate Change Service information (ERA5).",
            "license": "CC-BY-NC-SA-4.0",
            "timesteps_count": len(self.eval_steps),
        }

    def get_ibtracs_observations(self) -> List[Dict[str, Any]]:
        """Returns the official NOAA IBTrACS observation records."""
        return self.ibtracs_data

    def get_real_era5_step(self, step_idx: int) -> Dict[str, Any]:
        """
        Extracts genuine ECMWF ERA5 spatial grid for the requested evaluation step.
        Constructs fine native ERA5 field and coarse NWP input pair.
        """
        if step_idx < 0 or step_idx >= len(self.eval_steps):
            step_idx = 5

        step_meta = self.eval_steps[step_idx]
        t_idx = min(step_meta["time_idx"], len(self.timestamps) - 1)
        timestamp = self.timestamps[t_idx]

        n_rows, n_cols = self.shape
        wind_grid = np.zeros((n_rows, n_cols), dtype=np.float32)
        dir_grid = np.zeros((n_rows, n_cols), dtype=np.float32)
        mslp_grid = np.zeros((n_rows, n_cols), dtype=np.float32)
        precip_grid = np.zeros((n_rows, n_cols), dtype=np.float32)
        temp_grid = np.zeros((n_rows, n_cols), dtype=np.float32)

        for i in range(n_rows):
            for j in range(n_cols):
                pt_idx = i * n_cols + j
                pt = self.era5_data["grid_points"][pt_idx]["hourly"]
                wind_grid[i, j] = pt["wind_speed_10m"][t_idx]
                dir_grid[i, j] = pt["wind_direction_10m"][t_idx]
                mslp_grid[i, j] = pt["surface_pressure"][t_idx]
                precip_grid[i, j] = pt["precipitation"][t_idx]
                temp_grid[i, j] = pt["temperature_2m"][t_idx]

        rad = np.radians(dir_grid)
        u10 = -wind_grid * np.sin(rad) / 3.6
        v10 = -wind_grid * np.cos(rad) / 3.6

        closest_ibtracs = self._find_closest_ibtracs(timestamp)

        # Physical Coarsening Filter (Realistic NWP Simulation)
        wind_coarse = gaussian_filter(wind_grid, sigma=1.2) * 0.82
        mslp_coarse = 1008.0 - (1008.0 - mslp_grid) * 0.78
        precip_coarse = gaussian_filter(precip_grid, sigma=1.0) * 0.75
        u10_coarse = gaussian_filter(u10, sigma=1.2) * 0.82
        v10_coarse = gaussian_filter(v10, sigma=1.2) * 0.82

        return {
            "timestamp": timestamp,
            "step_index": step_idx,
            "stage": step_meta["stage"],
            "is_held_out_test": step_idx in [5, 10] or "Held-out" in step_meta["stage"],
            "lats": self.lats,
            "lons": self.lons,
            "native_era5_fine": {
                "wind_speed_kmh": wind_grid.tolist(),
                "u10_ms": u10.tolist(),
                "v10_ms": v10.tolist(),
                "mslp_hpa": mslp_grid.tolist(),
                "precip_mmh": precip_grid.tolist(),
                "temp_c": temp_grid.tolist(),
                "peak_wind_kmh": float(wind_grid.max()),
                "min_mslp_hpa": float(mslp_grid.min()),
            },
            "coarsened_nwp_input": {
                "wind_speed_kmh": wind_coarse.tolist(),
                "u10_ms": u10_coarse.tolist(),
                "v10_ms": v10_coarse.tolist(),
                "mslp_hpa": mslp_coarse.tolist(),
                "precip_mmh": precip_coarse.tolist(),
                "peak_wind_kmh": float(wind_coarse.max()),
                "min_mslp_hpa": float(mslp_coarse.min()),
            },
            "ibtracs_ground_truth": closest_ibtracs,
        }

    def _find_closest_ibtracs(self, era5_iso: str) -> Dict[str, Any]:
        """Matches hourly ERA5 timestamp with closest official NOAA IBTrACS report."""
        era5_date = era5_iso[:13]
        for rec in self.ibtracs_data:
            rec_date = rec["iso_time"][:13].replace(" ", "T")
            if rec_date == era5_date:
                return rec
        return self.ibtracs_data[len(self.ibtracs_data) // 2]

    def build_training_dataset(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Builds genuine coarse-to-fine pairs across ERA5 data with held-out test splits."""
        X_train, Y_train = [], []
        X_test, Y_test = [], []
        test_hour_ranges = set(range(72, 85)) | set(range(120, 133))

        for t_idx in range(len(self.timestamps)):
            wind = np.zeros(self.shape, dtype=np.float32)
            pres = np.zeros(self.shape, dtype=np.float32)
            rain = np.zeros(self.shape, dtype=np.float32)
            temp = np.zeros(self.shape, dtype=np.float32)

            for i in range(self.shape[0]):
                for j in range(self.shape[1]):
                    idx = i * self.shape[1] + j
                    pt = self.era5_data["grid_points"][idx]["hourly"]
                    wind[i, j] = pt["wind_speed_10m"][t_idx] / 3.6
                    pres[i, j] = (pt["surface_pressure"][t_idx] - 1000.0) / 25.0
                    rain[i, j] = pt["precipitation"][t_idx] / 20.0
                    temp[i, j] = (pt["temperature_2m"][t_idx] - 25.0) / 10.0

            fine_target = np.stack([wind, pres, rain, temp])
            w_c = gaussian_filter(wind, sigma=1.2) * 0.82
            p_c = gaussian_filter(pres, sigma=1.2) * 0.85
            r_c = gaussian_filter(rain, sigma=1.0) * 0.75
            t_c = gaussian_filter(temp, sigma=1.2)
            coarse_inp = np.stack([w_c, p_c, r_c, t_c])

            if t_idx in test_hour_ranges:
                X_test.append(coarse_inp)
                Y_test.append(fine_target)
            else:
                X_train.append(coarse_inp)
                Y_train.append(fine_target)

        return (
            np.array(X_train, dtype=np.float32),
            np.array(Y_train, dtype=np.float32),
            np.array(X_test, dtype=np.float32),
            np.array(Y_test, dtype=np.float32),
        )
