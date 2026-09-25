"""
Builds photorealistic 4096x2048 global Earth satellite texture, bump map,
and regional sector high-res patches for AERO-TRACK 4D 3D Globe.
"""

import os
import io
import time
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageFilter, ImageOps
import numpy as np
import cv2

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "vendor", "textures")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_tile(z, x, y):
    url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    req = urllib.request.Request(url, headers={"User-Agent": "AeroTrack4D/2.0 (MoES SIH 26078)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return (x, y, Image.open(io.BytesIO(res.read())).convert("RGB"))
    except Exception as e:
        print(f"Failed tile {z}/{y}/{x}: {e}")
        return (x, y, Image.new("RGB", (256, 256), (15, 25, 35)))

def build_global_texture():
    print("--> Fetching 256 tiles for Level 4 Global Satellite Texture (4096 x 4096 Web Mercator)...")
    z = 4
    tasks = [(z, x, y) for y in range(16) for x in range(16)]
    
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=24) as executor:
        results = list(executor.map(lambda p: fetch_tile(*p), tasks))
    print(f"Downloaded 256 tiles in {time.time()-t0:.2f}s")

    # Stitch into 4096 x 4096 Web Mercator
    merc_img = Image.new("RGB", (4096, 4096))
    for x, y, tile in results:
        merc_img.paste(tile, (x * 256, y * 256))
    
    merc_np = np.array(merc_img)

    # Remap Web Mercator to Equirectangular (Plate Carrée, 4096 x 2048)
    print("--> Remapping to Equirectangular (4096 x 2048) for Three.js sphere...")
    out_w, out_h = 4096, 2048
    in_w, in_h = 4096, 4096

    lons = np.linspace(-np.pi, np.pi, out_w, endpoint=False)
    lats = np.linspace(np.pi / 2.0, -np.pi / 2.0, out_h)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    max_lat = 85.05112878 * np.pi / 180.0
    lat_clamped = np.clip(lat_grid, -max_lat, max_lat)

    x_norm = (lon_grid + np.pi) / (2.0 * np.pi)
    y_norm = 0.5 - np.log(np.tan(np.pi / 4.0 + lat_clamped / 2.0)) / (2.0 * np.pi)

    map_x = (x_norm * (in_w - 1)).astype(np.float32)
    map_y = (y_norm * (in_h - 1)).astype(np.float32)

    equi_np = cv2.remap(merc_np, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    
    # Save high-res global satellite texture
    sat_path = os.path.join(OUTPUT_DIR, "earth_satellite_4096.jpg")
    cv2.imwrite(sat_path, cv2.cvtColor(equi_np, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    print(f"Saved {sat_path} ({os.path.getsize(sat_path) / 1024 / 1024:.2f} MB)")

    # Compute high-fidelity topographic relief bump map
    print("--> Generating 4096x2048 topographic relief bump map...")
    gray = cv2.cvtColor(equi_np, cv2.COLOR_RGB2GRAY)
    
    # Enhance mountains and terrain while keeping smooth water bodies
    blur = cv2.GaussianBlur(gray, (5, 5), 1.0)
    high_pass = cv2.subtract(gray, blur)
    bump = cv2.addWeighted(gray, 0.7, high_pass, 1.5, 0)
    
    # Normalize bump
    bump_norm = cv2.normalize(bump, None, 0, 255, cv2.NORM_MINMAX)
    bump_path = os.path.join(OUTPUT_DIR, "earth_bump_4096.jpg")
    cv2.imwrite(bump_path, bump_norm, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    print(f"Saved {bump_path} ({os.path.getsize(bump_path) / 1024 / 1024:.2f} MB)")

def build_regional_patches():
    """Generates ultra-high-resolution feathered regional patches for major global basins."""
    regions = [
        {
            "name": "americas_highres.jpg",
            "z": 5,
            # Gulf of Mexico / Atlantic / Florida
            # xtiles 6..10 (lon ~ -112.5 to -67.5)
            # ytiles 11..14 (lat ~ 14 to 38)
            "x_range": range(6, 11),
            "y_range": range(11, 15)
        },
        {
            "name": "europe_highres.jpg",
            "z": 5,
            # Western Europe / Mediterranean
            # xtiles 14..18 (lon ~ -22.5 to 22.5)
            # ytiles 9..13 (lat ~ 28 to 55)
            "x_range": range(14, 19),
            "y_range": range(9, 13)
        },
        {
            "name": "asia_highres.jpg",
            "z": 5,
            # East Asia / Japan / Philippines / China Sea
            # xtiles 25..30 (lon ~ 101 to 146)
            # ytiles 10..15 (lat ~ 9 to 45)
            "x_range": range(25, 30),
            "y_range": range(10, 15)
        }
    ]

    for reg in regions:
        print(f"--> Building regional patch: {reg['name']} (z={reg['z']})...")
        tasks = [(reg['z'], x, y) for y in reg['y_range'] for x in reg['x_range']]
        with ThreadPoolExecutor(max_workers=16) as ex:
            tiles = list(ex.map(lambda p: fetch_tile(*p), tasks))
        
        nx = len(reg['x_range'])
        ny = len(reg['y_range'])
        patch = Image.new("RGB", (nx * 256, ny * 256))
        for (x, y, t) in tiles:
            px = (x - reg['x_range'].start) * 256
            py = (y - reg['y_range'].start) * 256
            patch.paste(t, (px, py))
        
        out_p = os.path.join(OUTPUT_DIR, reg['name'])
        patch.save(out_p, quality=90)
        print(f"Saved {out_p} ({os.path.getsize(out_p) / 1024 / 1024:.2f} MB)")

if __name__ == "__main__":
    t_start = time.time()
    build_global_texture()
    build_regional_patches()
    print(f"==> All photorealistic textures generated in {time.time()-t_start:.2f}s!")
