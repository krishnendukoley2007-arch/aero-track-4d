"""
Wind Vector Field & Streamline Engine for SIH 26078.
Computes meteorological u/v wind vector components from real ERA5 wind speed and direction:
u = -speed * sin(deg2rad(dir))
v = -speed * cos(deg2rad(dir))

Powers animated canvas particle streamlines and vector quiver overlays on Leaflet.
"""

from typing import Dict, List, Any
import numpy as np
from src.data_loader import WeatherDataLoader


class WindVectorEngine:
    """Calculates physical u/v vector fields from real ERA5 data for streamline visualization."""

    def __init__(self, data_loader: WeatherDataLoader = None):
        self.dl = data_loader or WeatherDataLoader()

    def get_step_vectors(self, step_idx: int) -> Dict[str, Any]:
        """
        Returns the 16x16 wind vector grid for the given evaluation step.
        """
        step = self.dl.get_real_era5_step(step_idx)
        raw_pts = self.dl.era5_data.get("grid_points", [])
        time_str = step["timestamp"]

        vectors = []
        lats = step["lats"]
        lons = step["lons"]

        # Loop through grid points
        for pt in raw_pts:
            lat = pt["lat"]
            lon = pt["lon"]
            hourly = pt["hourly"]
            times = hourly.get("time", [])

            try:
                t_idx = times.index(time_str)
            except ValueError:
                t_idx = min(step_idx, len(times) - 1)

            speed_kmh = float(hourly["wind_speed_10m"][t_idx])
            direction_deg = float(hourly["wind_direction_10m"][t_idx])

            # Convert to u and v in km/h (meteorological convention)
            # 0 deg is North wind blowing South (v < 0), 90 deg is East wind blowing West (u < 0)
            rad = np.radians(direction_deg)
            u = -speed_kmh * np.sin(rad)
            v = -speed_kmh * np.cos(rad)

            vectors.append({
                "lat": round(lat, 2),
                "lon": round(lon, 2),
                "speed_kmh": round(speed_kmh, 1),
                "direction_deg": round(direction_deg, 1),
                "u": round(float(u), 2),
                "v": round(float(v), 2),
            })

        return {
            "timestamp": time_str,
            "step_index": step_idx,
            "stage": step["stage"],
            "grid_shape": [len(lats), len(lons)],
            "lats": lats,
            "lons": lons,
            "vectors": vectors,
            "max_speed_kmh": round(max(v["speed_kmh"] for v in vectors), 1),
        }
