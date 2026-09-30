"""
boundary_extractor.py -- Extracts closed parcel boundaries from drone GeoTIFFs
and reprojects pixel coordinates into geographic vector Polygons.
"""

from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
import rasterio
from shapely.geometry import Polygon


def extract_parcel_polygon_from_ortho(
    tif_path: Path,
    min_area_ratio: float = 0.25,
) -> tuple[Polygon, str]:
    """
    Performs ridge segmentation on drone GeoTIFF and extracts the dominant closed polygon.
    """
    with rasterio.open(tif_path) as src:
        r = src.read(1)
        g = src.read(2)
        b = src.read(3)
        transform = src.transform

    # 1. Feature Representation: Soil/Bund Color Ratio (ExG - Excess Green / Soil Index)
    # Earthen bunds in smallholder setups have distinct clay/soil signatures vs crop interior
    rgb = np.stack([r, g, b], axis=-1)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    
    # Threshold for dry earthen bunds / high brightness boundaries
    lower_bund = np.array([10, 20, 140])
    upper_bund = np.array([40, 160, 255])
    binary_bunds = cv2.inRange(hsv, lower_bund, upper_bund)

    # 2. Morphological Closure to connect intermittent bund vegetation gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed_bunds = cv2.morphologyEx(binary_bunds, cv2.MORPH_CLOSE, kernel)

    # 3. Contour Detection & Extraction of Parcel Interior
    # Invert to find the closed interior region surrounded by bunds
    field_interior = cv2.bitwise_not(closed_bunds)
    contours, _ = cv2.findContours(field_interior, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        raise ValueError(f"No boundary ridges detected in {tif_path}")

    # Select the largest coherent field parcel contour
    h, w = r.shape
    min_area = (h * w) * min_area_ratio
    valid_contours = [c for c in contours if cv2.contourArea(c) >= min_area]

    if not valid_contours:
        # Fallback to absolute maximum contour if threshold is strict
        best_contour = max(contours, key=cv2.contourArea)
    else:
        best_contour = max(valid_contours, key=cv2.contourArea)

    # Simplify contour vertices (Douglas-Peucker algorithm)
    epsilon = 0.005 * cv2.arcLength(best_contour, True)
    approx_contour = cv2.approxPolyDP(best_contour, epsilon, True)

    # 4. Pixel-to-Geo Coordinate Reprojection using Rasterio Affine Transform
    geo_coords = []
    for point in approx_contour:
        px_x, px_y = point[0]
        # Affine multiplication: (lon, lat) = transform * (col, row)
        lon, lat = transform * (px_x, px_y)
        geo_coords.append((lon, lat))

    # Ensure closed polygon loop
    if geo_coords[0] != geo_coords[-1]:
        geo_coords.append(geo_coords[0])

    observed_polygon = Polygon(geo_coords)
    geo_ref = f"geo://survey/orthomosaic/{tif_path.stem}/observed_v1"
    
    return observed_polygon, geo_ref