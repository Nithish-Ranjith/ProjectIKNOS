#!/usr/bin/env python3
"""
scripts/fetch_satellite_training_data.py
─────────────────────────────────────────
Step 1 of the 3-Layer Boundary Fusion plan.

PURPOSE:
  Downloads real Mapbox satellite tiles for ALL 1,000 APSAC parcels in the
  training dataset and renders their real cadastral polygon as a binary mask.
  This produces a matched (satellite_image, boundary_mask) pair for each parcel,
  which is the input needed to retrain the U-Net on real imagery instead of
  the synthetic rendered tiles it was trained on before.

OUTPUT:
  ml/boundary/v2/satellite_training_data/
    images/   → AP-07-*.png   (512×512 RGB satellite tiles)
    masks/    → AP-07-*.png   (512×512 binary masks, white=parcel, black=background)
    index.json → metadata for every parcel (parcel_key, lon, lat, area_sqm, zoom, gsd)
    FAILED.txt → list of any parcels that could not be fetched

USAGE:
  # Export your Mapbox token first:
  export MAPBOX_ACCESS_TOKEN=pk.eyJ1Ijoia2...

  # Dry run (no downloads, just validates geometry):
  python3 scripts/fetch_satellite_training_data.py --dry-run

  # Full run (all 1000 parcels):
  python3 scripts/fetch_satellite_training_data.py

  # Partial run (for testing):
  python3 scripts/fetch_satellite_training_data.py --limit 10

  # Resume interrupted run (skips already-fetched parcels):
  python3 scripts/fetch_satellite_training_data.py --resume
"""

import argparse
import json
import math
import os
import sys
import time
import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Config ─────────────────────────────────────────────────────────────────────
MAPBOX_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "")
ZOOM = 18                   # ~0.6m/px at equator — enough for field boundary detection
TILE_PX = 512               # @2x tiles are 512×512
OUTPUT_SIZE = 512           # Final image/mask size fed to the model
MARGIN_M = 40               # Metres of padding around each parcel boundary

DATASET_DIR = ROOT / "data_extracted" / "iknos_dataset_1000 2"
GEOJSON_PATH = DATASET_DIR / "output_real" / "parcels.geojson"
IMG_INPUT_DIR = DATASET_DIR / "dataset" / "images"

OUTPUT_DIR = ROOT / "ml" / "boundary" / "v2" / "satellite_training_data"
OUT_IMAGES = OUTPUT_DIR / "images"
OUT_MASKS  = OUTPUT_DIR / "masks"
INDEX_PATH = OUTPUT_DIR / "index.json"
FAILED_PATH = OUTPUT_DIR / "FAILED.txt"

# ── Tile math ──────────────────────────────────────────────────────────────────
def lon_to_tx(lon: float, z: int) -> int:
    return int((lon + 180.0) / 360.0 * (1 << z))

def lat_to_ty(lat: float, z: int) -> int:
    lat_r = math.radians(lat)
    return int((1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * (1 << z))

def tx_to_lon(x: int, z: int) -> float:
    return x / (1 << z) * 360.0 - 180.0

def ty_to_lat(y: int, z: int) -> float:
    n = math.pi - 2.0 * math.pi * y / (1 << z)
    return math.degrees(math.atan(math.sinh(n)))

def metres_to_deg_lon(m: float, lat: float) -> float:
    return m / (111320.0 * math.cos(math.radians(lat)))

def metres_to_deg_lat(m: float) -> float:
    return m / 111320.0

# ── Mapbox tile fetch ──────────────────────────────────────────────────────────
def fetch_tile_bytes(tx: int, ty: int, z: int) -> bytes:
    url = (
        f"https://api.mapbox.com/v4/mapbox.satellite/{z}/{tx}/{ty}@2x.jpg90"
        f"?access_token={MAPBOX_TOKEN}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "IKNOS-TerraTrace/2.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

# ── Build satellite image for one parcel ──────────────────────────────────────
def fetch_parcel_satellite(parcel_key: str, geometry: dict, lon: float, lat: float):
    """
    Returns (rgb_array H×W×3, west, north, px_lon, px_lat, zoom_used)
    """
    import numpy as np
    import cv2

    if geometry["type"] == "Polygon":
        coords = geometry["coordinates"][0]
    elif geometry["type"] == "MultiPolygon":
        coords = max(geometry["coordinates"], key=lambda r: len(r[0]))[0]
    else:
        raise ValueError(f"Unsupported geometry: {geometry['type']}")

    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)

    pad_lon = metres_to_deg_lon(MARGIN_M, lat)
    pad_lat = metres_to_deg_lat(MARGIN_M)
    min_lon -= pad_lon
    max_lon += pad_lon
    min_lat -= pad_lat
    max_lat += pad_lat

    zoom = ZOOM
    tx_min = lon_to_tx(min_lon, zoom)
    tx_max = lon_to_tx(max_lon, zoom)
    ty_min = lat_to_ty(max_lat, zoom)
    ty_max = lat_to_ty(min_lat, zoom)
    n_x = tx_max - tx_min + 1
    n_y = ty_max - ty_min + 1

    # Large parcel: drop to zoom 17 to keep tile count < 25
    if n_x * n_y > 25:
        zoom = 17
        tx_min = lon_to_tx(min_lon, zoom)
        tx_max = lon_to_tx(max_lon, zoom)
        ty_min = lat_to_ty(max_lat, zoom)
        ty_max = lat_to_ty(min_lat, zoom)
        n_x = tx_max - tx_min + 1
        n_y = ty_max - ty_min + 1

    canvas = None
    for row_i, ty in enumerate(range(ty_min, ty_max + 1)):
        for col_i, tx in enumerate(range(tx_min, tx_max + 1)):
            tile_bytes = fetch_tile_bytes(tx, ty, zoom)
            arr = np.frombuffer(tile_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            if img.shape[:2] != (TILE_PX, TILE_PX):
                img = cv2.resize(img, (TILE_PX, TILE_PX))
            if canvas is None:
                canvas = np.zeros((n_y * TILE_PX, n_x * TILE_PX, 3), dtype=np.uint8)
            canvas[row_i * TILE_PX:(row_i + 1) * TILE_PX,
                   col_i * TILE_PX:(col_i + 1) * TILE_PX] = img

    west  = tx_to_lon(tx_min, zoom)
    north = ty_to_lat(ty_min, zoom)
    east  = tx_to_lon(tx_max + 1, zoom)
    south = ty_to_lat(ty_max + 1, zoom)

    h, w = canvas.shape[:2]
    px_lon = (east - west) / w
    px_lat = (north - south) / h

    canvas_resized = cv2.resize(canvas, (OUTPUT_SIZE, OUTPUT_SIZE), interpolation=cv2.INTER_AREA)
    px_lon_r = (east - west) / OUTPUT_SIZE
    px_lat_r = (north - south) / OUTPUT_SIZE

    return canvas_resized, west, north, px_lon_r, px_lat_r, zoom

# ── Render binary mask from polygon ───────────────────────────────────────────
def render_mask(geometry: dict, west: float, north: float, px_lon: float, px_lat: float):
    import numpy as np
    import cv2

    mask = np.zeros((OUTPUT_SIZE, OUTPUT_SIZE), dtype=np.uint8)

    if geometry["type"] == "Polygon":
        rings = geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        rings = [r for poly in geometry["coordinates"] for r in poly]
    else:
        return mask

    for ring in rings:
        pts = []
        for lon, lat in ring:
            px = int((lon - west) / px_lon)
            py = int((north - lat) / px_lat)
            pts.append([px, py])
        pts_arr = __import__("numpy").array([pts], dtype=__import__("numpy").int32)
        cv2.fillPoly(mask, pts_arr, 255)

    return mask

# ── Build lookup ───────────────────────────────────────────────────────────────
def build_lookup() -> dict:
    with open(GEOJSON_PATH) as f:
        data = json.load(f)
    lookup = {}
    for feat in data["features"]:
        p = feat["properties"]
        key = p.get("internal_parcel_key")
        if key:
            lookup[key] = {
                "lon": p.get("longitude"),
                "lat": p.get("latitude"),
                "area_sqm": p.get("area_sqm"),
                "geometry": feat["geometry"],
            }
    return lookup

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Fetch satellite training tiles for all APSAC parcels")
    parser.add_argument("--dry-run", action="store_true", help="Validate geometry only, no downloads")
    parser.add_argument("--limit", type=int, default=0, help="Process only N parcels (0=all)")
    parser.add_argument("--resume", action="store_true", help="Skip already-fetched parcels")
    args = parser.parse_args()

    if not args.dry_run and not MAPBOX_TOKEN:
        print("ERROR: MAPBOX_ACCESS_TOKEN is not set.")
        print("  export MAPBOX_ACCESS_TOKEN=pk.eyJ1...")
        sys.exit(1)

    OUT_IMAGES.mkdir(parents=True, exist_ok=True)
    OUT_MASKS.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("IKNOS TerraTrace — Satellite Training Data Fetcher v1.0")
    print("=" * 60)
    print(f"  Output:  {OUTPUT_DIR}")
    print(f"  Zoom:    {ZOOM} (~0.6m/px)")
    print(f"  Margin:  {MARGIN_M}m around each parcel")
    print(f"  Dry run: {args.dry_run}")
    print()

    print("Loading APSAC GeoJSON...")
    lookup = build_lookup()
    print(f"  {len(lookup)} parcels loaded.")

    img_stems = sorted([p.stem for p in IMG_INPUT_DIR.glob("*.png")])
    print(f"  {len(img_stems)} parcels in training set.")

    parcel_list = []
    for stem in img_stems:
        parts = stem.split("-")
        if len(parts) >= 5:
            key = f"AP-07-{parts[2]}-{parts[3]}-{parts[4]}"
            if key in lookup:
                parcel_list.append((stem, key, lookup[key]))

    print(f"  {len(parcel_list)} matched and ready.")

    if args.limit > 0:
        parcel_list = parcel_list[:args.limit]
        print(f"  Limiting to {args.limit} parcels.")

    print()

    existing_index = {}
    if args.resume and INDEX_PATH.exists():
        with open(INDEX_PATH) as f:
            existing_index = {e["parcel_key"]: e for e in json.load(f)}
        print(f"Resuming — {len(existing_index)} already fetched.\n")

    index = list(existing_index.values())
    failed = []
    success = 0
    skipped = 0

    for i, (stem, parcel_key, info) in enumerate(parcel_list):
        print(f"[{i+1:4d}/{len(parcel_list)}] {parcel_key}", end="  ")

        out_img  = OUT_IMAGES / f"{stem}.png"
        out_mask = OUT_MASKS / f"{stem}.png"

        if args.resume and parcel_key in existing_index:
            print("SKIP")
            skipped += 1
            continue

        if args.dry_run:
            geom = info["geometry"]
            n_verts = len(geom["coordinates"][0]) if geom["type"] == "Polygon" else "?"
            print(f"DRY-RUN  area={info['area_sqm']:.0f}sqm  lon={info['lon']:.5f}  lat={info['lat']:.5f}  verts={n_verts}")
            continue

        try:
            import numpy as np
            import cv2

            img_arr, west, north, px_lon, px_lat, zoom_used = fetch_parcel_satellite(
                parcel_key, info["geometry"], info["lon"], info["lat"]
            )
            mask_arr = render_mask(info["geometry"], west, north, px_lon, px_lat)

            fg_px = int(mask_arr.sum()) // 255
            fg_pct = 100.0 * fg_px / (OUTPUT_SIZE * OUTPUT_SIZE)

            if fg_px == 0:
                print(f"WARN — empty mask, polygon may be outside tile bounds")
                failed.append(f"{parcel_key}  EMPTY_MASK")

            cv2.imwrite(str(out_img), cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR))
            cv2.imwrite(str(out_mask), mask_arr)

            gsd_m = 111320.0 * px_lon * math.cos(math.radians(info["lat"]))
            index.append({
                "parcel_key": parcel_key,
                "stem": stem,
                "lon": info["lon"],
                "lat": info["lat"],
                "area_sqm": info["area_sqm"],
                "zoom": zoom_used,
                "gsd_m_per_px": round(gsd_m, 4),
                "mask_fg_pct": round(fg_pct, 2),
                "west": west,
                "north": north,
                "px_lon": px_lon,
                "px_lat": px_lat,
            })
            success += 1
            print(f"OK  gsd={gsd_m:.2f}m/px  mask={fg_pct:.1f}%fg  zoom={zoom_used}")

            time.sleep(0.2)  # ~5 req/s, respect Mapbox TOS

        except Exception as e:
            print(f"FAILED — {e}")
            failed.append(f"{parcel_key}  {e}")

    if not args.dry_run:
        with open(INDEX_PATH, "w") as f:
            json.dump(index, f, indent=2)
        if failed:
            with open(FAILED_PATH, "w") as f:
                f.write("\n".join(failed))

    print()
    print("=" * 60)
    print("DONE")
    print(f"  Success:  {success}")
    print(f"  Skipped:  {skipped}")
    print(f"  Failed:   {len(failed)}")
    if not args.dry_run and success > 0:
        print()
        print("Next step — retrain the U-Net on satellite imagery:")
        print("  python3 -m ml.boundary.v2.train_satellite --epochs 60")

if __name__ == "__main__":
    main()
