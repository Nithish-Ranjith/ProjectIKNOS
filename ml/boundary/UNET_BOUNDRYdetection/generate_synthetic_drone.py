"""
generate_synthetic_drone.py -- Synthesizes realistic georeferenced drone orthomosaics
simulating rural agricultural field bunds (medhas), crop rows, and ground encroachments.
"""

from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from scipy.ndimage import gaussian_filter


def generate_drone_ortho(
    case_path: Path,
    output_tif: Path,
    encroachment_meters: float = 3.5,
    resolution_px: int = 512,
):
    with open(case_path, "r", encoding="utf-8") as f:
        case = json.load(f)

    minx, miny, maxx, maxy = case["parcel"]["bbox"]
    output_tif.parent.mkdir(parents=True, exist_ok=True)

    # 1. Coordinate Transform Setup
    transform = from_bounds(minx, miny, maxx, maxy, resolution_px, resolution_px)
    
    # Approx meters per pixel at this latitude
    lat_center = (miny + maxy) / 2
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(lat_center))
    dx_px = (maxx - minx) * meters_per_deg_lon / resolution_px
    
    encroachment_px = int(encroachment_meters / dx_px)

    # 2. Base Agricultural Field Textures (Perlin-like Soil Noise + Crop Rows)
    np.random.seed(42)
    soil_noise = np.random.normal(120, 15, (resolution_px, resolution_px))
    soil_noise = gaussian_filter(soil_noise, sigma=2.0)

    # Crop furrow wave pattern
    y_coords, x_coords = np.indices((resolution_px, resolution_px))
    crop_stripes = 25 * np.sin(x_coords / 4.0)

    # Base RGB Channels (Vegetation + Brown Earthen Soil)
    r_channel = np.clip(soil_noise * 0.9 + crop_stripes * 0.4, 40, 200).astype(np.uint8)
    g_channel = np.clip(soil_noise * 1.2 + crop_stripes * 0.9, 60, 240).astype(np.uint8)
    b_channel = np.clip(soil_noise * 0.6 + crop_stripes * 0.2, 20, 150).astype(np.uint8)

    # 3. Burn Physical Bund / Ridge (Medha)
    # Cadastral border with realistic human encroachment along the western boundary
    pad = 40
    top, bottom = pad, resolution_px - pad
    left, right = pad - encroachment_px, resolution_px - pad  # Shift left to simulate encroachment

    bund_mask = np.zeros((resolution_px, resolution_px), dtype=np.uint8)
    bund_thickness = 4

    # Top & bottom bunds
    bund_mask[top - bund_thickness:top + bund_thickness, max(0, left):right] = 1
    bund_mask[bottom - bund_thickness:bottom + bund_thickness, max(0, left):right] = 1
    # West & east bunds
    bund_mask[top:bottom, max(0, left - bund_thickness):left + bund_thickness] = 1
    bund_mask[top:bottom, right - bund_thickness:right + bund_thickness] = 1

    # Apply bright earthen bund coloring (dry clay / elevated ridge)
    r_channel[bund_mask == 1] = 215
    g_channel[bund_mask == 1] = 195
    b_channel[bund_mask == 1] = 140

    # 4. Write Georeferenced GeoTIFF (EPSG:4326)
    with rasterio.open(
        output_tif,
        "w",
        driver="GTiff",
        height=resolution_px,
        width=resolution_px,
        count=3,
        dtype=rasterio.uint8,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(r_channel, 1)
        dst.write(g_channel, 2)
        dst.write(b_channel, 3)

    print(f"[generator] Synthetic drone GeoTIFF written -> {output_tif}")
    print(f"[generator] Injected western bund encroachment: {encroachment_meters}m ({encroachment_px}px).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-file", required=True)
    parser.add_argument("--out-tif", default="data/drone_imagery/survey_demo.tif")
    parser.add_argument("--encroachment-m", type=float, default=3.5)
    args = parser.parse_args()

    generate_drone_ortho(
        Path(args.case_file),
        Path(args.out_tif),
        encroachment_meters=args.encroachment_m,
    )