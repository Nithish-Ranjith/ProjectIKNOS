#!/usr/bin/env python3
"""
scripts/fetch_satellite_ortho.py
────────────────────────────────
Downloads real Mapbox satellite tiles for the C01 parcel area and stitches
them into a georeferenced GeoTIFF that the ONNX U-Net can actually process.

Tiles are fetched at zoom 18 (~0.6m/px) from Mapbox Satellite v9.
The resulting GeoTIFF is written to backend/uploads/demo_ortho_C01.tif
and MSN-C01's orthomosaic_uri is updated in the DB.
"""

import os, sys, math, io, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("IKNOS_DEMO", "1")

# ── Mapbox config ─────────────────────────────────────────────────────────────
MAPBOX_TOKEN = (
    os.environ.get("MAPBOX_ACCESS_TOKEN") or
    "YOUR_MAPBOX_TOKEN_HERE"
)
ZOOM = 18          # ~0.6 m/px at equator; fine enough for field boundary detection
TILE_PX = 256

# ── Parcel C01 ────────────────────────────────────────────────────────────────
CASE_ID    = "C01"
MISSION_ID = "MSN-C01"
OUT_PATH   = ROOT / "backend" / "uploads" / "demo_ortho_C01.tif"

# Cadastral polygon centroid + bbox (EPSG:4326)
CADASTRAL_COORDS = [
    [80.097164347, 16.28734498],
    [80.097162746, 16.287694859],
    [80.096811634, 16.28769336],
    [80.096813236, 16.287343481],
    [80.097164347, 16.28734498],
]

# ── Tile math ─────────────────────────────────────────────────────────────────
def lon_to_tile_x(lon: float, zoom: int) -> int:
    return int((lon + 180.0) / 360.0 * (1 << zoom))

def lat_to_tile_y(lat: float, zoom: int) -> int:
    lat_r = math.radians(lat)
    return int((1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * (1 << zoom))

def tile_to_lon(x: int, zoom: int) -> float:
    return x / (1 << zoom) * 360.0 - 180.0

def tile_to_lat(y: int, zoom: int) -> float:
    n = math.pi - 2.0 * math.pi * y / (1 << zoom)
    return math.degrees(math.atan(math.sinh(n)))

def fetch_tile(x: int, y: int, z: int) -> bytes:
    import urllib.request
    url = (
        f"https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.jpg90"
        f"?access_token={MAPBOX_TOKEN}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "IKNOS/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()

def main():
    import numpy as np

    print("=" * 60)
    print("IKNOS Satellite Tile Fetcher — C01")
    print("=" * 60)

    lons = [c[0] for c in CADASTRAL_COORDS]
    lats = [c[1] for c in CADASTRAL_COORDS]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)

    # Expand by 3 tiles on each side for context
    tx_min = lon_to_tile_x(min_lon, ZOOM) - 1
    tx_max = lon_to_tile_x(max_lon, ZOOM) + 1
    ty_min = lat_to_tile_y(max_lat, ZOOM) - 1   # note: y flipped (north = smaller y)
    ty_max = lat_to_tile_y(min_lat, ZOOM) + 1

    n_x = tx_max - tx_min + 1
    n_y = ty_max - ty_min + 1
    print(f"  Fetching {n_x}×{n_y} = {n_x*n_y} tiles at zoom {ZOOM} (512px/tile @2x)")

    # 2x tiles are 512×512
    tile_px = 512
    canvas = np.zeros((n_y * tile_px, n_x * tile_px, 3), dtype=np.uint8)

    for row_i, ty in enumerate(range(ty_min, ty_max + 1)):
        for col_i, tx in enumerate(range(tx_min, tx_max + 1)):
            print(f"  tile {tx}/{ty}...", end=" ", flush=True)
            try:
                data = fetch_tile(tx, ty, ZOOM)
                import cv2
                arr = np.frombuffer(data, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                if img.shape[:2] != (tile_px, tile_px):
                    img = cv2.resize(img, (tile_px, tile_px))
                y0 = row_i * tile_px
                x0 = col_i * tile_px
                canvas[y0:y0+tile_px, x0:x0+tile_px] = img
                print("ok")
            except Exception as e:
                print(f"FAILED: {e}")

    # ── Compute GeoTransform ──────────────────────────────────────────────────
    # NW corner: tile (tx_min, ty_min)
    west  = tile_to_lon(tx_min, ZOOM)
    north = tile_to_lat(ty_min, ZOOM)
    east  = tile_to_lon(tx_max + 1, ZOOM)
    south = tile_to_lat(ty_max + 1, ZOOM)

    h, w = canvas.shape[:2]
    px_lon = (east - west) / w
    px_lat = (north - south) / h   # positive; we flip with negative sign in transform

    print(f"\n  Canvas: {w}×{h} px")
    print(f"  Bounds: W={west:.6f} N={north:.6f} E={east:.6f} S={south:.6f}")
    print(f"  Pixel size: {px_lon:.8f}° lon  {px_lat:.8f}° lat")

    # Verify parcel is inside
    ok = west <= min_lon and east >= max_lon and south <= min_lat and north >= max_lat
    print(f"  Parcel inside raster: {'✓ YES' if ok else '✗ NO — abort'}")
    if not ok:
        print("  [ERROR] Parcel is outside the downloaded tile area. Increase margin.")
        sys.exit(1)

    # ── Write GeoTIFF ─────────────────────────────────────────────────────────
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"\n  Writing GeoTIFF → {OUT_PATH}")

    import rasterio
    from rasterio.transform import from_origin
    from rasterio.crs import CRS
    # from_origin(west, north, x_pixel_size, y_pixel_size)
    transform = from_origin(west, north, px_lon, px_lat)
    with rasterio.open(
        str(OUT_PATH), 'w',
        driver='GTiff',
        height=h, width=w,
        count=3,
        dtype=np.uint8,
        crs=CRS.from_epsg(4326),
        transform=transform,
        compress='lzw',
    ) as dst:
        for i in range(3):
            dst.write(canvas[:, :, i], i + 1)

    print(f"  ✓ Written ({w}×{h} px, {OUT_PATH.stat().st_size//1024} KB)")

    # ── Update mission record ──────────────────────────────────────────────────
    print(f"\n  Updating Mission {MISSION_ID} in DB...")
    from backend.app.database import SessionLocal
    from backend.app import models
    db = SessionLocal()
    mission = db.query(models.Mission).filter(models.Mission.mission_id == MISSION_ID).first()
    if mission:
        mission.orthomosaic_uri = str(OUT_PATH)
        db.commit()
        print(f"  ✓ orthomosaic_uri → {OUT_PATH}")
    else:
        print(f"  [ERROR] Mission {MISSION_ID} not found")
    db.close()

    print("\n✓ Complete. Now run:")
    print(f"  POST /missions/{MISSION_ID}/run-unet  (as surveyor)")
    print("  Then GET /cases/C01/geometry-layers\n")


if __name__ == "__main__":
    main()
