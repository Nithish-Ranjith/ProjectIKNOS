#!/usr/bin/env python3
"""
scripts/generate_demo_ortho.py
─────────────────────────────
Generates a deterministic, synthetic GeoTIFF orthomosaic for case C01
so the ONNX U-Net pipeline can run on real pixel data without a drone flight.

What this does:
  1. Reads the cadastral polygon for AP-07-0103-008-00001 from PostGIS.
  2. Creates a small (1024×1024) GeoTIFF in EPSG:4326 with UTM-style resolution
     (~0.25m GSD equivalent at this latitude) centred on the parcel bounding box.
  3. Fills the image with a realistic texture:
     - Gaussian-noise base (bare ground spectral signature)
     - The parcel interior gets a different RGB mean (vegetation/field crop)
     - A thin encroachment strip (shifted polygon) with yet another spectral mean
  4. Writes the .tif to backend/uploads/demo_ortho_C01.tif
  5. Updates Mission MSN-C01's orthomosaic_uri to point at the local path.

The resulting GeoTIFF is NOT real aerial imagery but is geometrically correct —
the cadastral centroid is at the image centre, pixels have real lat/lon transforms,
and the boundary shift is physically encoded in the pixel signature. The ONNX
model will see a realistic distribution (boundary somewhere in the patch) and
should segment a polygon close to the true parcel.
"""

import os
import sys
import json
import math
import struct
import numpy as np
from pathlib import Path

# ── bootstrap PYTHONPATH ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("IKNOS_DEMO", "1")

# ── config ────────────────────────────────────────────────────────────────────
CASE_ID    = "C01"
PARCEL_ID  = "AP-07-0103-008-00001"
MISSION_ID = "MSN-C01"
OUT_PATH   = ROOT / "backend" / "uploads" / "demo_ortho_C01.tif"

# Cadastral polygon (EPSG:4326) — matches seed data in DB
CADASTRAL_COORDS = [
    [80.097164347, 16.28734498],
    [80.097162746, 16.287694859],
    [80.096811634, 16.28769336],
    [80.096813236, 16.287343481],
    [80.097164347, 16.28734498],
]

# ── helpers ───────────────────────────────────────────────────────────────────
def write_minimal_geotiff(path: Path, img_rgb: np.ndarray, 
                           west_lon: float, north_lat: float,
                           pixel_size_deg: float) -> None:
    """
    Write a GeoTIFF. west_lon / north_lat are the NW corner coordinates.
    """
    try:
        import rasterio
        from rasterio.transform import from_origin
        from rasterio.crs import CRS
        h, w, _ = img_rgb.shape
        # from_origin(west, north, xsize, ysize)  — NW corner
        transform = from_origin(west_lon, north_lat, pixel_size_deg, pixel_size_deg)
        with rasterio.open(
            str(path), 'w',
            driver='GTiff',
            height=h, width=w,
            count=3,
            dtype=np.uint8,
            crs=CRS.from_epsg(4326),
            transform=transform,
            compress='lzw',
        ) as dst:
            for i in range(3):
                dst.write(img_rgb[:, :, i], i + 1)
        print(f"  [rasterio] Written {path} ({w}×{h} px)")
    except ImportError:
        print("  [WARNING] rasterio not available, writing raw RGB PNG instead.")
        try:
            import cv2
            png_path = path.with_suffix('.png')
            cv2.imwrite(str(png_path), cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
            with open(path.with_suffix('.pgw'), 'w') as f:
                f.write(f"{pixel_size_deg}\n0.0\n0.0\n{-pixel_size_deg}\n{west_lon}\n{north_lat}\n")
            if path.exists():
                path.unlink()
            path.symlink_to(png_path.name)
            print(f"  [cv2 fallback] Written {png_path}")
        except Exception as e:
            print(f"  [ERROR] Cannot write image: {e}")
            raise


def polygon_mask(h: int, w: int, coords_pixel: list) -> np.ndarray:
    """Rasterize a polygon given pixel coordinates. Returns bool mask."""
    import cv2
    pts = np.array(coords_pixel, dtype=np.int32).reshape((-1, 1, 2))
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 1)
    return mask.astype(bool)


def main():
    print("=" * 60)
    print("IKNOS Demo Orthomosaic Generator — C01")
    print("=" * 60)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ── 1. Derive bounding box ──────────────────────────────────────────────
    lons = [c[0] for c in CADASTRAL_COORDS]
    lats = [c[1] for c in CADASTRAL_COORDS]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)

    # Physical padding: 50 m on each side (generous to ensure parcel is well inside)
    lat_centre = (min_lat + max_lat) / 2
    pad_lat = 50.0 / 111320.0
    pad_lon = 50.0 / (111320.0 * math.cos(math.radians(lat_centre)))

    # NW corner = (min_lon - pad, max_lat + pad)
    west_lon  = min_lon - pad_lon
    north_lat = max_lat + pad_lat     # top of image (largest lat)
    east_lon  = max_lon + pad_lon
    south_lat = min_lat - pad_lat

    extent_lon = east_lon - west_lon
    extent_lat = north_lat - south_lat

    # Resolution: ~0.25 m GSD equivalent
    lat_per_m = 1.0 / 111320.0
    pixel_size_deg = 0.25 * lat_per_m   # 0.25 m in degrees at this latitude

    img_w = max(512, int(extent_lon / pixel_size_deg))
    img_h = max(512, int(extent_lat / pixel_size_deg))
    # Cap at 1024 to keep file small for demo
    if img_w > 1024:
        pixel_size_deg = extent_lon / 1024
        img_w = 1024
        img_h = int(extent_lat / pixel_size_deg)
    img_h = min(img_h, 1024)

    print(f"  Image size: {img_w}×{img_h}  pixel_size: {pixel_size_deg:.8f} deg")
    print(f"  NW corner (west_lon, north_lat): {west_lon:.6f}, {north_lat:.6f}")
    print(f"  Parcel lat range: {south_lat:.6f} → {north_lat:.6f} | image covers this fully: {south_lat >= north_lat - img_h * pixel_size_deg}")

    # ── 2. Lon/lat → pixel transform ─────────────────────────────────────────
    def ll2px(lon, lat):
        x = (lon - west_lon) / pixel_size_deg
        y = (north_lat - lat) / pixel_size_deg   # y increases downward
        return int(round(x)), int(round(y))

    # ── 3. Build RGB image ────────────────────────────────────────────────────
    rng = np.random.default_rng(42)  # deterministic

    # Base: bare soil / dry ground  (brownish-tan)
    base_rgb = np.array([135, 115, 90], dtype=np.float32)
    img = (rng.normal(0, 12, (img_h, img_w, 3)) + base_rgb).clip(0, 255).astype(np.float32)

    # Convert cadastral polygon to pixel coords
    cad_px = [ll2px(c[0], c[1]) for c in CADASTRAL_COORDS]

    # Draw parcel interior: green-ish field crop
    cad_mask = polygon_mask(img_h, img_w, cad_px)
    field_rgb = np.array([95, 145, 80], dtype=np.float32)
    noise_field = rng.normal(0, 15, (img_h, img_w, 3)).astype(np.float32)
    img[cad_mask] = (field_rgb + noise_field[cad_mask]).clip(0, 255)

    # Draw encroachment strip: shifted boundary (≈7m east → ~28 px)
    shift_px = max(8, int(7.0 / (111320.0 * math.cos(math.radians(lat_centre)) * pixel_size_deg)))
    encroach_px = [(x + shift_px, y) for x, y in cad_px]
    encroach_mask = polygon_mask(img_h, img_w, encroach_px)
    # Encroachment region: dead/dry grass
    encroach_rgb = np.array([160, 150, 100], dtype=np.float32)
    # Only paint the DIFFERENCE (pixels in encroached but not cadastral)
    diff_mask = encroach_mask & ~cad_mask
    noise_enc = rng.normal(0, 10, (img_h, img_w, 3)).astype(np.float32)
    img[diff_mask] = (encroach_rgb + noise_enc[diff_mask]).clip(0, 255)

    # Berm / boundary line — slightly darker
    import cv2
    pts_cad = np.array(cad_px, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(img.astype(np.uint8), [pts_cad], True, (60, 50, 40), thickness=2)

    img_u8 = img.clip(0, 255).astype(np.uint8)

    # ── 4. Write GeoTIFF ─────────────────────────────────────────────────────
    print(f"  Writing GeoTIFF → {OUT_PATH}")
    write_minimal_geotiff(OUT_PATH, img_u8, west_lon, north_lat, pixel_size_deg)

    # ── 5. Update mission record ──────────────────────────────────────────────
    print(f"  Updating Mission {MISSION_ID} orthomosaic_uri in DB...")
    try:
        from backend.app.database import SessionLocal
        from backend.app import models
        db = SessionLocal()
        mission = db.query(models.Mission).filter(models.Mission.mission_id == MISSION_ID).first()
        if not mission:
            print(f"  [ERROR] Mission {MISSION_ID} not found in DB.")
        else:
            mission.orthomosaic_uri = str(OUT_PATH)
            db.commit()
            print(f"  ✓ Mission {MISSION_ID} orthomosaic_uri → {OUT_PATH}")
        db.close()
    except Exception as e:
        print(f"  [ERROR] DB update failed: {e}")

    print("\n✓ Done. Now trigger:")
    print(f"  POST /missions/{MISSION_ID}/run-unet  (as surveyor)")
    print("  Then GET /cases/C01/geometry-layers to see the AI boundary.\n")


if __name__ == "__main__":
    main()
