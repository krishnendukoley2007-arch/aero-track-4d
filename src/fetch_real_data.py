"""
Real Meteorological Data Fetcher for SIH 26078.
Pulls real ECMWF ERA5 reanalysis spatial grid data (hourly)
and official NOAA IBTrACS observation records for:
1. Super Cyclone Amphan (May 2020)
2. Extremely Severe Cyclonic Storm Fani (April-May 2019)
3. Very Severe Cyclonic Storm Yaas (May 2021)
Saves genuine datasets to data/raw/ and derives real climatology baselines to data/climatology/.
"""

import os
import sys
import json
import csv
import io
import urllib.request
import numpy as np
from typing import Dict, List, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CLIM_DIR = os.path.join(DATA_DIR, "climatology")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(CLIM_DIR, exist_ok=True)

IBTRACS_URL = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv"


def fetch_ibtracs_for_storm(storm_name_query: str, output_prefix: str) -> List[Dict[str, Any]]:
    """
    Downloads official observation records for a requested storm
    from NOAA's International Best Track Archive for Climate Stewardship (IBTrACS v04r01).
    """
    print(f"Fetching official NOAA IBTrACS records for {storm_name_query}...")
    req = urllib.request.Request(IBTRACS_URL, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            text = resp.read().decode("utf-8", errors="ignore")

        reader = csv.reader(io.StringIO(text))
        header = next(reader)
        units = next(reader)

        storm_rows = []
        for row in reader:
            if len(row) > 9 and storm_name_query.upper() in row[5].upper():
                iso_time = row[6].strip()
                lat_str = row[8].strip()
                lon_str = row[9].strip()
                wmo_wind = row[10].strip()
                wmo_pres = row[11].strip()
                agency = row[12].strip()

                if lat_str and lon_str:
                    lat = float(lat_str)
                    lon = float(lon_str)
                    wind_kts = float(wmo_wind) if wmo_wind else None
                    pres_hpa = float(wmo_pres) if wmo_pres else None

                    storm_rows.append({
                        "sid": row[0].strip(),
                        "name": row[5].strip(),
                        "iso_time": iso_time,
                        "lat": lat,
                        "lon": lon,
                        "wind_kts": wind_kts,
                        "wind_kmh": round(wind_kts * 1.852, 1) if wind_kts else None,
                        "mslp_hpa": pres_hpa,
                        "agency": agency,
                    })

        json_path = os.path.join(RAW_DIR, f"{output_prefix}_ibtracs_real.json")
        with open(json_path, "w") as f:
            json.dump(storm_rows, f, indent=2)

        csv_path = os.path.join(RAW_DIR, f"{output_prefix}_ibtracs_real.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["sid", "name", "iso_time", "lat", "lon", "wind_kts", "wind_kmh", "mslp_hpa", "agency"])
            writer.writeheader()
            writer.writerows(storm_rows)

        print(f"  -> Successfully saved {len(storm_rows)} official IBTrACS observation records to {json_path}")
        return storm_rows
    except Exception as e:
        print(f"  -> Warning: IBTrACS download error ({e})")
        return []


def fetch_era5_spatial_grid_for_dates(start_date: str, end_date: str, filename: str) -> Dict[str, Any]:
    """
    Downloads real ECMWF ERA5 reanalysis fields over the Bay of Bengal (10N-25N, 80E-95E)
    via Open-Meteo's historical ERA5 reanalysis API.
    """
    print(f"Fetching real ECMWF ERA5 reanalysis grid for {start_date} to {end_date} -> {filename}...")
    raw_file = os.path.join(RAW_DIR, filename)

    lats = np.linspace(10.0, 25.0, 16)
    lons = np.linspace(80.0, 95.0, 16)
    grid_lats, grid_lons = np.meshgrid(lats, lons, indexing="ij")
    flat_lats = grid_lats.ravel()
    flat_lons = grid_lons.ravel()
    n_points = len(flat_lats)

    batch_size = 64
    all_point_data = []

    for i in range(0, n_points, batch_size):
        b_lats = flat_lats[i:i + batch_size]
        b_lons = flat_lons[i:i + batch_size]
        lat_str = ",".join(f"{x:.2f}" for x in b_lats)
        lon_str = ",".join(f"{x:.2f}" for x in b_lons)

        url = (
            f"https://archive-api.open-meteo.com/v1/archive?"
            f"latitude={lat_str}&longitude={lon_str}&"
            f"start_date={start_date}&end_date={end_date}&"
            f"hourly=wind_speed_10m,wind_direction_10m,surface_pressure,precipitation,temperature_2m"
        )

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                all_point_data.extend(data)
            else:
                all_point_data.append(data)

    timestamps = all_point_data[0]["hourly"]["time"]
    n_hours = len(timestamps)

    era5_dataset = {
        "domain": {
            "lat_min": 10.0, "lat_max": 25.0, "lon_min": 80.0, "lon_max": 95.0,
            "shape": [16, 16],
            "lats": [round(float(x), 2) for x in lats],
            "lons": [round(float(x), 2) for x in lons],
        },
        "timestamps": timestamps,
        "grid_points": []
    }

    for p in all_point_data:
        era5_dataset["grid_points"].append({
            "lat": round(float(p["latitude"]), 2),
            "lon": round(float(p["longitude"]), 2),
            "hourly": p["hourly"]
        })

    with open(raw_file, "w") as f:
        json.dump(era5_dataset, f)

    print(f"  -> Successfully saved real ERA5 spatial grid ({n_points} points x {n_hours} hours) to {raw_file}")
    return era5_dataset


def fetch_all_cyclone_datasets():
    """Fetches real datasets for Amphan (2020), Fani (2019), and Yaas (2021)."""
    # 1. Cyclone Amphan (May 2020)
    amphan_ibtracs = os.path.join(RAW_DIR, "amphan_ibtracs_real.json")
    amphan_era5 = os.path.join(RAW_DIR, "era5_amphan_may2020.json")
    if not os.path.exists(amphan_ibtracs):
        fetch_ibtracs_for_storm("AMPHAN", "amphan")
    if not os.path.exists(amphan_era5):
        fetch_era5_spatial_grid_for_dates("2020-05-15", "2020-05-21", "era5_amphan_may2020.json")

    # 2. Cyclone Fani (April-May 2019)
    fani_ibtracs = os.path.join(RAW_DIR, "fani_ibtracs_real.json")
    fani_era5 = os.path.join(RAW_DIR, "era5_fani_may2019.json")
    if not os.path.exists(fani_ibtracs):
        fetch_ibtracs_for_storm("FANI", "fani")
    if not os.path.exists(fani_era5):
        fetch_era5_spatial_grid_for_dates("2019-04-28", "2019-05-04", "era5_fani_may2019.json")

    # 3. Cyclone Yaas (May 2021)
    yaas_ibtracs = os.path.join(RAW_DIR, "yaas_ibtracs_real.json")
    yaas_era5 = os.path.join(RAW_DIR, "era5_yaas_may2021.json")
    if not os.path.exists(yaas_ibtracs):
        fetch_ibtracs_for_storm("YAAS", "yaas")
    if not os.path.exists(yaas_era5):
        fetch_era5_spatial_grid_for_dates("2021-05-23", "2021-05-28", "era5_yaas_may2021.json")


if __name__ == "__main__":
    fetch_all_cyclone_datasets()
    print("Multi-cyclone data fetch complete!")
