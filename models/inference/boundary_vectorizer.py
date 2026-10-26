"""
models/inference/boundary_vectorizer.py — Watershed post-processing + GeoJSON polygonization.

The Watershed Post-Processing Pipeline (Waldner–Diakogiannis):
  1. Threshold `extent` mask → binary field interior
  2. Use `distance` map as the landscape for watershed markers
  3. Find local maxima (field centers) as seed markers
  4. Run marker-controlled Watershed on the inverted distance map
  5. Each watershed basin = one field parcel
  6. Trace basin boundaries → vector polygon
  7. Reproject pixel coords to geographic coords using rasterio Affine transform

Why Watershed over simple contours:
  - Earthen bunds often have gaps from vegetation or moisture
  - Watershed "fills" gaps using the distance field — no manual morphological closure needed
  - Cleanly separates adjacent parcels sharing a bund without double-counting

Design Contracts:
  - Output is a GeoJSON FeatureCollection — CANDIDATE BOUNDARIES, NOT LEGAL BOUNDARIES
  - Each feature has dataset_label = 'TRANSFER_LEARNED_UNVALIDATED'
  - Polygon must pass ST_IsValid before being stored in PostGIS
  - Area in m² is estimated from pixel count × (m/pixel)²
"""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    from scipy import ndimage as ndi
    _SCIPY = True
except ImportError:
    _SCIPY = False

try:
    from shapely.geometry import Polygon, mapping
    from shapely.ops import unary_union
    _SHAPELY = True
except ImportError:
    _SHAPELY = False

CANDIDATE_LABEL = "TRANSFER_LEARNED_UNVALIDATED"


def _pixel_to_geo(px: int, py: int, affine) -> tuple[float, float]:
    """Convert pixel (col, row) to (lon, lat) via rasterio Affine transform."""
    lon = affine.c + px * affine.a + py * affine.b
    lat = affine.f + px * affine.d + py * affine.e
    return lon, lat


def vectorize_predictions(
    extent_mask:   np.ndarray,     # (H, W) float32, [0,1]
    boundary_mask: np.ndarray,     # (H, W) float32, [0,1]
    distance_map:  np.ndarray,     # (H, W) float32, [0,1]
    affine_transform,              # rasterio Affine (from tiler)
    extent_thresh:   float = 0.45,
    boundary_thresh: float = 0.40,
    min_parcel_area: int   = 200,  # pixels; ~0.01 ha @ 5cm/px
    simplify_tolerance: float = 2.0,  # pixels
) -> dict:
    """
    Convert raw mask predictions to a GeoJSON FeatureCollection of candidate parcels.

    Returns:
        GeoJSON FeatureCollection dict with candidate_boundary polygons.
    """
    if not _CV2:
        return _fallback_vectorize(extent_mask, boundary_mask, affine_transform, extent_thresh)

    # 1. Binary interior mask (extent) — morphological clean-up
    binary_extent = (extent_mask > extent_thresh).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary_extent = cv2.morphologyEx(binary_extent, cv2.MORPH_CLOSE, kernel)
    binary_extent = cv2.morphologyEx(binary_extent, cv2.MORPH_OPEN,  kernel)

    # 2. Prepare distance map for watershed
    dist_normalized = (distance_map * 255).astype(np.uint8)

    # 3. Find seed markers: local maxima of distance map within extent
    if _SCIPY:
        dist_smooth = ndi.gaussian_filter(distance_map, sigma=3.0)
        # Peak detection: pixel is a maximum if it's the largest within a 15px window
        from scipy.ndimage import maximum_filter
        local_max = (maximum_filter(dist_smooth, size=15) == dist_smooth)
        local_max = local_max & (dist_smooth > 0.15) & (binary_extent == 1)
        local_max_uint8 = local_max.astype(np.uint8) * 255
    else:
        # Fallback: distance transform from extent mask
        dist_cv = cv2.distanceTransform(binary_extent, cv2.DIST_L2, 5)
        dist_cv = cv2.normalize(dist_cv, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
        _, local_max_uint8 = cv2.threshold(dist_cv, 0.5 * dist_cv.max(), 255, cv2.THRESH_BINARY)

    # 4. Label connected components of local maxima → marker labels
    n_markers, markers = cv2.connectedComponents(local_max_uint8)

    # 5. Marker-controlled Watershed
    #    Input image: 3-channel from extent+boundary (watershed needs 8UC3)
    boundary_binary = (boundary_mask > boundary_thresh).astype(np.uint8) * 255
    ws_input = cv2.merge([
        binary_extent * 255,
        boundary_binary,
        dist_normalized
    ])
    cv2.watershed(ws_input, markers)

    # 6. Extract polygon for each label
    features = []
    for label_id in range(1, n_markers):
        label_mask = (markers == label_id).astype(np.uint8)
        area_px = int(label_mask.sum())

        if area_px < min_parcel_area:
            continue

        # Find contours of this label
        contours, _ = cv2.findContours(label_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        # Use the largest contour
        best = max(contours, key=cv2.contourArea)
        if cv2.contourArea(best) < min_parcel_area:
            continue

        # Simplify with Douglas-Peucker
        eps = simplify_tolerance * cv2.arcLength(best, True) / 1000.0
        simplified = cv2.approxPolyDP(best, eps, True)

        if len(simplified) < 4:
            continue

        # Reproject pixel → geographic coords
        geo_ring = []
        for pt in simplified:
            px, py = int(pt[0][0]), int(pt[0][1])
            lon, lat = _pixel_to_geo(px, py, affine_transform)
            geo_ring.append([lon, lat])

        # Close the ring
        if geo_ring[0] != geo_ring[-1]:
            geo_ring.append(geo_ring[0])

        # Estimate area using Haversine
        est_area_m2 = _estimate_area_m2(geo_ring)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [geo_ring]
            },
            "properties": {
                "candidate_id":   str(uuid.uuid4()),
                "dataset_label":  CANDIDATE_LABEL,
                "area_px":        area_px,
                "area_m2_est":    round(est_area_m2, 2),
                "note": (
                    "Candidate physical boundary derived from Multi-Task ResUNet-a "
                    "with Watershed post-processing. This is NOT a legal boundary. "
                    "Transfer-learned from AI4Boundaries/Eurocrops — Indian fine-tuning pending (BQ-04)."
                )
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "model":         "MultiTaskResUNet-a (ResNet-34 backbone)",
            "dataset_label": CANDIDATE_LABEL,
            "n_candidates":  len(features),
            "warning": (
                "Output is a CANDIDATE boundary derived from pixel-level segmentation. "
                "It must be reviewed by a licensed surveyor before any legal use."
            )
        }
    }


def _estimate_area_m2(ring: list[list[float]]) -> float:
    """Approximate polygon area in m² using the Shoelace formula + meters/degree scale."""
    if len(ring) < 4:
        return 0.0
    lats = [p[1] for p in ring]
    lons = [p[0] for p in ring]
    lat_c = sum(lats) / len(lats)
    lon_c = sum(lons) / len(lons)

    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat_c))

    # Convert to approximate meters
    xs = [(lon - lon_c) * m_per_deg_lon for lon in lons]
    ys = [(lat - lat_c) * m_per_deg_lat for lat in lats]

    # Shoelace
    n = len(xs)
    area = 0.0
    for i in range(n - 1):
        area += xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
    return abs(area) / 2.0


def _fallback_vectorize(
    extent_mask: np.ndarray,
    boundary_mask: np.ndarray,
    affine_transform,
    thresh: float = 0.45,
) -> dict:
    """Minimal fallback without OpenCV: threshold → bounding box polygon."""
    binary = (extent_mask > thresh).astype(np.uint8)
    rows = np.any(binary, axis=1)
    cols = np.any(binary, axis=0)
    if not rows.any():
        return {"type": "FeatureCollection", "features": [], "metadata": {"n_candidates": 0}}

    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]

    corners = [[c0, r0], [c1, r0], [c1, r1], [c0, r1], [c0, r0]]
    geo_ring = [list(_pixel_to_geo(px, py, affine_transform)) for px, py in corners]

    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [geo_ring]},
            "properties": {
                "candidate_id":  str(uuid.uuid4()),
                "dataset_label": CANDIDATE_LABEL,
                "note":          "Fallback bounding-box polygon (OpenCV not available).",
                "area_m2_est":   _estimate_area_m2(geo_ring),
            }
        }],
        "metadata": {"n_candidates": 1, "dataset_label": CANDIDATE_LABEL}
    }


def save_geojson(geojson: dict, path: str | Path) -> Path:
    """Save GeoJSON to file and return path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"[Vectorizer] Saved {len(geojson['features'])} candidate polygons → {out}")
    return out
