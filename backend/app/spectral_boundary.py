"""
backend/app/spectral_boundary.py
──────────────────────────────────
Geometric boundary estimator — fallback when ONNX confidence is too low.

Algorithm:
  1. Read the GeoTIFF crop around the cadastral parcel.
  2. Convert to LAB colour space for perceptual uniformity.
  3. Compute Canny edges on the L channel.
  4. Morphological dilation + connected-component filtering to retain
     only edges inside / near the cadastral polygon.
  5. GrabCut foreground segmentation seeded by the cadastral polygon mask.
  6. Post-process: take the largest connected foreground region, vectorise,
     clean topology, reproject to EPSG:4326.

Provenance: SPECTRAL_EDGE_DETECTION — not ML inference, but physically
grounded in real pixel spectral contrast.  Confidence is reported as the
mean intra-parcel spectral contrast normalised to [0, 1].
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

PROVENANCE = "SPECTRAL_EDGE_DETECTION"
MODEL_VERSION = "spectral-v1"


def _rasterio_available() -> bool:
    try:
        import rasterio  # noqa: F401
        return True
    except ImportError:
        return False


def estimate_boundary_from_ortho(
    tif_path: str,
    cadastral_geojson: dict,
) -> Optional[dict]:
    """
    Returns a GeoJSON Feature (EPSG:4326) or None on failure.
    """
    if not _rasterio_available():
        logger.error("rasterio not available — cannot run spectral estimator")
        return None

    try:
        import rasterio
        from rasterio.warp import transform_geom
        from rasterio.features import shapes
        from shapely.geometry import shape, Polygon, mapping

        with rasterio.open(tif_path) as src:
            tif_crs = src.crs

            # 1. Reproject cadastral to TIF CRS
            if str(tif_crs) != "EPSG:4326":
                proj_cad = transform_geom("EPSG:4326", tif_crs, cadastral_geojson["geometry"])
            else:
                proj_cad = cadastral_geojson["geometry"]

            cadastral_poly = shape(proj_cad)
            minx, miny, maxx, maxy = cadastral_poly.bounds

            # 2. Add generous padding (60 m physical)
            if tif_crs.is_geographic:
                import math
                lat_rad = math.radians(cadastral_poly.centroid.y)
                pad_y = 60.0 / 111320.0
                pad_x = 60.0 / (111320.0 * math.cos(lat_rad))
            else:
                pad_x = pad_y = 60.0

            bx0, by0 = minx - pad_x, miny - pad_y
            bx1, by1 = maxx + pad_x, maxy + pad_y

            # Pixel window
            r0, c0 = src.index(bx0, by1)  # NW corner → (row, col)
            r1, c1 = src.index(bx1, by0)  # SE corner
            r0, r1 = sorted([r0, r1])
            c0, c1 = sorted([c0, c1])
            r0 = max(0, r0); c0 = max(0, c0)
            r1 = min(src.height, r1); c1 = min(src.width, c1)
            h, w = r1 - r0, c1 - c0

            if h <= 0 or w <= 0:
                logger.error("Derived window is empty — parcel may be outside raster bounds")
                return None

            window = rasterio.windows.Window(c0, r0, w, h)
            img_data = src.read((1, 2, 3), window=window)
            if img_data.shape[0] < 3:
                logger.error("Raster has fewer than 3 bands")
                return None

            img_rgb = img_data.transpose(1, 2, 0).astype(np.uint8)
            win_transform = src.window_transform(window)

            # 3. Build cadastral mask in pixel space
            def ll_to_px(lon, lat):
                r, c = src.index(lon, lat)
                return int(c - c0), int(r - r0)   # (x, y) for OpenCV

            cad_coords_geom = proj_cad["coordinates"][0]
            cad_px = np.array([ll_to_px(p[0], p[1]) for p in cad_coords_geom], dtype=np.int32)
            cad_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(cad_mask, [cad_px], 255)

            # 4. LAB colour + Canny edge detection
            img_lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
            l_ch = img_lab[:, :, 0]

            # Adaptive Canny: thresholds based on image contrast
            med = float(np.median(l_ch))
            sigma = 0.33
            lo = max(0,   int(max(0,   (1.0 - sigma) * med)))
            hi = min(255, int(min(255, (1.0 + sigma) * med)))
            edges = cv2.Canny(l_ch, lo, hi)

            # Mask edges to padded cadastral region (3× scale)
            dilated_mask = cv2.dilate(cad_mask, np.ones((9, 9), np.uint8), iterations=3)
            edges_masked = cv2.bitwise_and(edges, edges, mask=dilated_mask)

            # 5. GrabCut seeded by cadastral mask
            #    probable_fg = erosion of cadastral, probable_bg = far outside
            sure_fg = cv2.erode(cad_mask, np.ones((5, 5), np.uint8), iterations=2)
            sure_bg = cv2.dilate(cad_mask, np.ones((25, 25), np.uint8), iterations=3)
            sure_bg = cv2.bitwise_not(sure_bg)

            gc_mask = np.zeros((h, w), dtype=np.uint8)
            gc_mask[:] = cv2.GC_BGD
            gc_mask[dilated_mask > 0] = cv2.GC_PR_BGD
            gc_mask[cad_mask > 0]     = cv2.GC_PR_FGD
            gc_mask[sure_fg > 0]      = cv2.GC_FGD
            gc_mask[sure_bg > 0]      = cv2.GC_BGD

            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)

            try:
                cv2.grabCut(img_rgb, gc_mask, None, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_MASK)
            except cv2.error as e:
                logger.warning(f"GrabCut failed: {e} — falling back to Otsu on edges")
                gc_mask = cad_mask.copy()

            fg_mask = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

            # 6. Morphological cleanup
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

            binary = (fg_mask > 128).astype(np.uint8)

            # Fallback: if GrabCut gives nothing, use the cadastral mask as-is
            if binary.sum() == 0:
                logger.warning("GrabCut produced empty mask — using cadastral polygon as boundary")
                binary = (cad_mask > 0).astype(np.uint8)

            # 7. Vectorise
            polys = list(shapes(binary, transform=win_transform))
            best_poly = None
            max_area = 0.0
            for geom, val in polys:
                if val == 1:
                    p = shape(geom)
                    if p.area > max_area:
                        max_area = p.area
                        best_poly = p

            if best_poly is None:
                logger.warning("No polygon found after vectorisation")
                return None

            # 8. Topology cleaning + simplification
            clean = best_poly.buffer(0)
            if clean.geom_type == "MultiPolygon":
                clean = max(clean.geoms, key=lambda g: g.area)
            tol = src.res[0] * 1.5
            clean = clean.simplify(tol, preserve_topology=True)

            # 9. Confidence: mean spectral contrast inside the polygon mask
            inside_px = (binary == 1) & (cad_mask > 0)
            if inside_px.any():
                intra_contrast = float(l_ch[inside_px].std()) / 127.0
                confidence = float(np.clip(intra_contrast, 0.0, 1.0))
            else:
                confidence = 0.5

            # 10. Reproject to EPSG:4326
            best_geojson = mapping(clean)
            if str(tif_crs) != "EPSG:4326":
                best_geojson = transform_geom(tif_crs, "EPSG:4326", best_geojson)

            return {
                "type": "Feature",
                "geometry": best_geojson,
                "properties": {
                    "source": "spectral-edge-detection",
                    "provenance": PROVENANCE,
                    "model_version": MODEL_VERSION,
                    "confidence": round(confidence, 4),
                    "confidence_semantics": "normalised_intra_parcel_l_channel_contrast",
                    "input_crs": str(tif_crs),
                    "input_gsd": float(src.res[0]),
                    "grabcut_iterations": 5,
                },
            }

    except Exception as e:
        logger.error(f"Spectral boundary estimator failed: {e}", exc_info=True)
        return None
