import json
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import cv2
import numpy as np

try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False

try:
    import rasterio
    from rasterio.features import shapes
    from shapely.geometry import shape, Polygon
    _RASTERIO_AVAILABLE = True
except ImportError:
    _RASTERIO_AVAILABLE = False

logger = logging.getLogger(__name__)

# Constants matched to v2_real_model_config.json
MODEL_VERSION = "v2_efficientnet_b3"
TILE_SIZE = 512
SIGMA_PX = 60.0
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_SESSION = None

def get_ort_session() -> ort.InferenceSession:
    global _SESSION
    if _SESSION is None:
        if not _ORT_AVAILABLE:
            raise ImportError("onnxruntime is not installed")
        model_path = Path(__file__).parent.parent.parent / "models" / "weights" / "v2_real_model_quantized.onnx"
        if not model_path.exists():
            # Fallback to the original real model or v2 model
            model_path = Path(__file__).parent.parent.parent / "models" / "weights" / "v2_real_model.onnx"
        logger.info(f"Loading ONNX model from {model_path}")
        _SESSION = ort.InferenceSession(str(model_path))
    return _SESSION

def make_gaussian_heatmap(cy: float, cx: float, size: int = TILE_SIZE, sigma: float = SIGMA_PX) -> np.ndarray:
    y, x = np.mgrid[0:size, 0:size]
    hmap = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))
    return hmap.astype(np.float32)

def run_inference_on_tile_prob(img_rgb: np.ndarray, cx_px: float, cy_px: float) -> np.ndarray:
    """
    Run the v2 EfficientNet-B3 ONNX model on a single 512x512 RGB tile.
    Returns the float32 probability mask (0.0 to 1.0) so it can be blended.
    """
    if img_rgb.shape[:2] != (TILE_SIZE, TILE_SIZE):
        img_rgb = cv2.resize(img_rgb, (TILE_SIZE, TILE_SIZE))
    
    img_norm = (img_rgb.astype(np.float32) / 255.0 - MEAN) / STD
    img_norm = img_norm.transpose(2, 0, 1)
    
    accumulated_prob = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)
    session = get_ort_session()
    
    for k in range(4):
        img_rot = np.rot90(img_norm, k, axes=(1, 2))
        
        if k == 0:
            rx, ry = cx_px, cy_px
        elif k == 1:
            rx, ry = cy_px, TILE_SIZE - cx_px
        elif k == 2:
            rx, ry = TILE_SIZE - cx_px, TILE_SIZE - cy_px
        elif k == 3:
            rx, ry = TILE_SIZE - cy_px, cx_px
            
        heatmap = make_gaussian_heatmap(ry, rx)[np.newaxis, ...]
        inp = np.concatenate([img_rot, heatmap], axis=0)[np.newaxis, ...]
        
        logits = session.run(None, {"input": inp})[0][0, 0]
        prob = 1.0 / (1.0 + np.exp(-logits))
        
        prob_back = np.rot90(prob, -k, axes=(0, 1))
        accumulated_prob += prob_back
        
    return accumulated_prob / 4.0

def process_orthophoto_for_parcel(tif_path: str, cadastral_geojson: dict) -> Optional[dict]:
    """
    TRUE GEOSPATIAL PIPELINE:
    1. Opens GeoTIFF and reads its CRS (e.g. UTM).
    2. Reprojects Cadastral GeoJSON (EPSG:4326) to TIF CRS.
    3. Calculates a dynamic bounding box with physical padding (e.g. +30 meters).
    4. Crops the exact window from the massive Orthomosaic.
    5. Resizes the dynamic crop to 512x512 for the ML model.
    6. Runs ONNX inference.
    7. Vectorizes, cleans topology, and maps back to the crop's Affine transform.
    8. Reprojects the final polygon back to EPSG:4326 for the UI.
    """
    if not _RASTERIO_AVAILABLE:
        logger.error("rasterio/shapely not available")
        return None

    from rasterio.warp import transform_geom
    
    try:
        with rasterio.open(tif_path) as src:
            tif_crs = src.crs
            # 1. Reproject Cadastral to TIF CRS
            if tif_crs != 'EPSG:4326':
                proj_cadastral = transform_geom('EPSG:4326', tif_crs, cadastral_geojson["geometry"])
            else:
                proj_cadastral = cadastral_geojson["geometry"]
                
            cadastral_poly = shape(proj_cadastral)
            
            # 2. Get physical bounds and add padding (e.g., 30 units/meters)
            minx, miny, maxx, maxy = cadastral_poly.bounds
            if tif_crs.is_geographic:
                import math
                lat_rad = math.radians(cadastral_poly.centroid.y)
                pad_y = 30.0 / 111320.0
                pad_x = 30.0 / (111320.0 * math.cos(lat_rad))
            else:
                pad_x = 30.0
                pad_y = 30.0
            minx, miny, maxx, maxy = minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y
            
            # 3. Convert physical bounds to pixel window
            py_max, px_min = src.index(minx, miny)
            py_min, px_max = src.index(maxx, maxy)
            
            # Keep py_min < py_max
            if py_min > py_max:
                py_min, py_max = py_max, py_min
            if px_min > px_max:
                px_min, px_max = px_max, px_min
                
            # Clamp to map boundaries to prevent window truncation crash
            px_min = max(0, int(px_min))
            py_min = max(0, int(py_min))
            px_max = min(src.width, int(px_max))
            py_max = min(src.height, int(py_max))
                
            w_width = px_max - px_min
            w_height = py_max - py_min
            window = rasterio.windows.Window(px_min, py_min, w_width, w_height)
            
            # 4. Read RGB Crop
            img_data = src.read((1, 2, 3), window=window)
            if img_data.shape[0] != 3:
                logger.error("Orthophoto does not have 3 bands")
                return None
            img_rgb = img_data.transpose(1, 2, 0)
            
            # 5. Calculate Centroid relative to the crop
            centroid = cadastral_poly.centroid
            cy_raw, cx_raw = src.index(centroid.x, centroid.y)
            cx_crop = cx_raw - px_min
            cy_crop = cy_raw - py_min
            
            # 6. SLIDING WINDOW INFERENCE (No resizing, true GSD)
            h, w, _ = img_rgb.shape
            accum_prob = np.zeros((h, w), dtype=np.float32)
            weight_map = np.zeros((h, w), dtype=np.float32)
            
            # 2D Gaussian mask to down-weight edge predictions of each patch
            y_grid, x_grid = np.mgrid[0:TILE_SIZE, 0:TILE_SIZE]
            center_px = TILE_SIZE / 2.0
            patch_weight = np.exp(-((x_grid - center_px)**2 + (y_grid - center_px)**2) / (2.0 * (TILE_SIZE / 4.0)**2)).astype(np.float32)
            
            stride = int(TILE_SIZE * 0.75) # 25% overlap
            
            # Ensure at least one pass if image is smaller than tile size
            if h <= TILE_SIZE and w <= TILE_SIZE:
                y_steps = [0]
                x_steps = [0]
            else:
                y_steps = list(range(0, max(1, h - TILE_SIZE + stride), stride))
                x_steps = list(range(0, max(1, w - TILE_SIZE + stride), stride))
            
            for y0 in y_steps:
                for x0 in x_steps:
                    # Boundary clamping for edge patches
                    y1, x1 = min(h, y0 + TILE_SIZE), min(w, x0 + TILE_SIZE)
                    y0, x0 = max(0, y1 - TILE_SIZE), max(0, x1 - TILE_SIZE)
                    
                    patch = img_rgb[y0:y1, x0:x1]
                    # Compute centroid relative to this sliding patch
                    patch_cx = cx_crop - x0
                    patch_cy = cy_crop - y0
                    
                    # Pad if the entire image is smaller than 512
                    if patch.shape[:2] != (TILE_SIZE, TILE_SIZE):
                        ph, pw = patch.shape[:2]
                        padded = cv2.copyMakeBorder(patch, 0, TILE_SIZE - ph, 0, TILE_SIZE - pw, cv2.BORDER_REFLECT)
                        prob_patch = run_inference_on_tile_prob(padded, patch_cx, patch_cy)
                        prob_patch = prob_patch[:ph, :pw]
                        p_weight = patch_weight[:ph, :pw]
                    else:
                        prob_patch = run_inference_on_tile_prob(patch, patch_cx, patch_cy)
                        p_weight = patch_weight
                        
                    accum_prob[y0:y1, x0:x1] += prob_patch * p_weight
                    weight_map[y0:y1, x0:x1] += p_weight
                    
            final_prob = np.divide(accum_prob, weight_map, out=np.zeros_like(accum_prob), where=weight_map!=0)
            
            # ── Adaptive thresholding (Otsu on probability map) ─────────────
            # Hard threshold (> 0.5) fails when the model is applied to imagery
            # outside its training distribution (domain shift). Otsu's method
            # finds the natural foreground/background split in the probability
            # histogram, which works even when absolute logit values are low.
            prob_u8 = (final_prob * 255).astype(np.uint8)
            otsu_thresh, mask = cv2.threshold(prob_u8, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            otsu_prob_thresh = otsu_thresh / 255.0
            logger.info(f"Otsu threshold: {otsu_prob_thresh:.4f}  (prob max={final_prob.max():.4f}  mean={final_prob.mean():.5f})")
            
            # Morphological cleanup: close small holes, remove tiny specks
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # Reject if the entire image is thresholded as foreground (degenerate case)
            fg_frac = mask.sum() / mask.size
            if fg_frac > 0.85 or mask.sum() == 0:
                # Fall back to top-5% percentile threshold
                p95 = np.percentile(final_prob, 95)
                mask = (final_prob >= p95).astype(np.uint8)
                logger.info(f"Otsu degenerate (fg={fg_frac:.2%}); using p95={p95:.4f} fallback")
            
            # 7. Vectorize and Georeference
            win_transform = src.window_transform(window)
            results = list(shapes(mask, transform=win_transform))
            
            best_poly = None
            max_area = 0
            for geom, val in results:
                if val == 1:
                    p = shape(geom)
                    if p.area > max_area:
                        max_area = p.area
                        best_poly = p
            
            if not best_poly:
                logger.warning("No parcel detected in the tile")
                return None
                
            # Dynamic simplification tolerance based on TIF resolution
            tolerance = src.res[0] * 2.0  # 2 pixels tolerance
            
            # ENTERPRISE GEOMETRY CLEANING
            clean_poly = best_poly.buffer(0)
            if clean_poly.geom_type == 'MultiPolygon':
                clean_poly = max(clean_poly.geoms, key=lambda a: a.area)
                
            # Keep legitimate internal holes (e.g. lakes, large barns), delete noise
            interiors = []
            for ring in clean_poly.interiors:
                if Polygon(ring).area > (tolerance ** 2) * 5:
                    interiors.append(ring)
            clean_poly = Polygon(clean_poly.exterior, interiors)
            
            clean_poly = clean_poly.simplify(tolerance, preserve_topology=True)
            
            from shapely.geometry import mapping
            from rasterio.features import geometry_mask
            best_poly_tif_crs = mapping(clean_poly)
            
            # Measured (not assumed) confidence: mean model foreground probability
            # over the pixels covered by the final polygon. This is a model-output
            # statistic, NOT a calibrated probability of being correct.
            inside = ~geometry_mask([best_poly_tif_crs], out_shape=final_prob.shape,
                                    transform=win_transform, all_touched=False)
            if not inside.any():
                logger.warning("Final polygon covers no pixels; cannot compute confidence")
                return None
            mean_fg_prob = float(final_prob[inside].mean())
            
            # 8. Reproject back to EPSG:4326 for the Frontend
            if tif_crs != 'EPSG:4326':
                final_geojson = transform_geom(tif_crs, 'EPSG:4326', best_poly_tif_crs)
            else:
                final_geojson = best_poly_tif_crs
                
            return {
                "type": "Feature",
                "geometry": final_geojson,
                "properties": {
                    "source": "u-net-inference",
                    "model_version": MODEL_VERSION,
                    "dataset_label": "TRANSFER_LEARNED_UNVALIDATED",
                    "confidence": round(mean_fg_prob, 4),
                    "confidence_semantics": "mean_foreground_probability_inside_polygon",
                    "input_crs": str(tif_crs),
                    "input_gsd": float(src.res[0]),
                    "n_tiles": len(y_steps) * len(x_steps)
                }
            }
            
    except Exception as e:
        logger.error(f"Error processing orthophoto: {e}")
        return None
