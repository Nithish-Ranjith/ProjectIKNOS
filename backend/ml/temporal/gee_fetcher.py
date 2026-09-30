"""
backend/ml/temporal/gee_fetcher.py — Google Earth Engine (GEE) Sentinel-2 NDVI & PELT Changepoint Module

This module connects to Google Earth Engine via Service Account credentials to:
1. Fetch Sentinel-2 Surface Reflectance (S2_SR) optical imagery for a given parcel geometry.
2. Compute NDVI time-series (Normalized Difference Vegetation Index).
3. Apply PELT (Pruned Exact Linear Time) changepoint detection via `ruptures` to detect abrupt land-clearing or development.
4. Calculate an instability score (0.0 - 1.0) passed directly into the Decision Engine.

Fallback: If GEE service account key is not present, returns synthetic NDVI time-series and PELT result for local offline development.
"""

import os
import json
import numpy as np

# Try importing ee and ruptures
try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

try:
    import ruptures as rpt
    RUPTURES_AVAILABLE = True
except ImportError:
    RUPTURES_AVAILABLE = False


IS_GEE_INITIALIZED = False


def initialize_gee(service_account_email: str = None, json_key_path: str = None, project_id: str = None) -> bool:
    """
    Initializes Earth Engine using a Service Account or User Auth.
    Supports environment variables:
      GEE_SERVICE_ACCOUNT_EMAIL
      GEE_SERVICE_ACCOUNT_KEY_PATH
      GEE_PROJECT_ID
    """
    global IS_GEE_INITIALIZED
    if not EE_AVAILABLE:
        print("[GEE Fetcher] 'earthengine-api' not installed. Running in mock mode.")
        IS_GEE_INITIALIZED = False
        return False

    email = service_account_email or os.getenv("GEE_SERVICE_ACCOUNT_EMAIL")
    key_path = json_key_path or os.getenv("GEE_SERVICE_ACCOUNT_KEY_PATH")
    project = project_id or os.getenv("GEE_PROJECT_ID")

    if key_path and os.path.exists(key_path):
        try:
            credentials = ee.ServiceAccountCredentials(email, key_path)
            if project:
                ee.Initialize(credentials, project=project)
            else:
                ee.Initialize(credentials)
            print(f"[GEE Fetcher] Successfully authenticated with GEE Service Account: {email}")
            IS_GEE_INITIALIZED = True
            return True
        except Exception as e:
            print(f"[GEE Fetcher] Failed to initialize GEE with Service Account: {e}")
            IS_GEE_INITIALIZED = False
            return False
    else:
        # Try standard EE user OAuth initialization
        try:
            if project:
                ee.Initialize(project=project)
            else:
                # Attempt without project arg
                ee.Initialize()
            print("[GEE Fetcher] Successfully initialized using user OAuth credentials.")
            IS_GEE_INITIALIZED = True
            return True
        except Exception as e:
            print(f"[GEE Fetcher] User OAuth initialization requires GCP project ID: {e}")
            print("[GEE Fetcher] Pass project_id or export GEE_PROJECT_ID='your-gcp-project-id'. Running in fallback mock mode.")
            IS_GEE_INITIALIZED = False
            return False


def get_sentinel2_ndvi_series(bbox: list[float], start_date: str = "2023-01-01", end_date: str = "2024-01-01") -> np.ndarray:
    """
    Fetches Sentinel-2 imagery for a bounding box [min_lon, min_lat, max_lon, max_lat],
    computes monthly mean NDVI, and returns time-series array.
    """
    if not EE_AVAILABLE or not IS_GEE_INITIALIZED:
        # Generate synthetic NDVI time series (e.g. constant vegetation then sudden drop)
        np.random.seed(42)
        baseline = np.random.normal(loc=0.7, scale=0.03, size=8) # 8 months high vegetation
        cleared = np.random.normal(loc=0.2, scale=0.04, size=4)  # 4 months cleared land
        return np.concatenate([baseline, cleared])

    # GEE Geometry
    geom = ee.Geometry.BBox(bbox[0], bbox[1], bbox[2], bbox[3])

    # Sentinel-2 Harmonized Collection
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    )

    def add_ndvi(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        return img.addBands(ndvi)

    s2_ndvi = s2.map(add_ndvi).select("NDVI")
    
    # Calculate mean NDVI over region per image
    def extract_mean(img):
        mean_val = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=10,
            maxPixels=1e9
        ).get("NDVI")
        return img.set("mean_ndvi", mean_val)

    with_mean = s2_ndvi.map(extract_mean)
    ndvi_list = with_mean.aggregate_array("mean_ndvi").getInfo()
    
    # Filter out nulls
    clean_series = np.array([x for x in ndvi_list if x is not None])
    return clean_series if len(clean_series) > 0 else np.full(12, 0.5)


def run_pelt_changepoint_detection(ndvi_series: np.ndarray, penalty: float = 3.0) -> tuple[int, float]:
    """
    Applies PELT (Pruned Exact Linear Time) changepoint detection to NDVI time series.
    Returns:
      - n_changepoints: number of detected structural breaks
      - instability_score: calculated 0.0 - 1.0 score
    """
    if len(ndvi_series) < 4:
        return 0, 0.0

    if RUPTURES_AVAILABLE:
        # Fit PELT model with RBF or L2 cost
        algo = rpt.Pelt(model="rbf", min_size=2, jump=1).fit(ndvi_series)
        result = algo.predict(pen=penalty)
        # result contains boundary indices, excluding final index
        changepoints = len(result) - 1
    else:
        # Fallback simple threshold change detection if ruptures not installed
        diffs = np.abs(np.diff(ndvi_series))
        changepoints = int(np.sum(diffs > 0.25))

    # Calculate magnitude of maximum change
    max_drop = float(np.max(np.abs(np.diff(ndvi_series)))) if len(ndvi_series) > 1 else 0.0

    # Scale score: changepoints count + magnitude
    instability_score = min(1.0, round((changepoints * 0.35) + (max_drop * 0.8), 2))
    return changepoints, instability_score


def analyze_parcel_temporal_anomaly(parcel_id: str, bbox: list[float] = None) -> dict:
    """
    Main entry point for Track A temporal analysis.
    Input: parcel_id and optional bbox [min_lon, min_lat, max_lon, max_lat]
    Output: dict with ndvi_series, changepoints, instability_score.
    """
    if not IS_GEE_INITIALIZED:
        initialize_gee()

    if bbox is None:
        # Default mock Andhra Pradesh coordinates [lon_min, lat_min, lon_max, lat_max]
        bbox = [80.50, 16.50, 80.51, 16.51]

    ndvi_series = get_sentinel2_ndvi_series(bbox)
    n_changepoints, instability_score = run_pelt_changepoint_detection(ndvi_series)

    return {
        "parcel_id": parcel_id,
        "ndvi_series_length": len(ndvi_series),
        "changepoints_detected": n_changepoints,
        "instability_score": instability_score,
        "mode": "GEE_LIVE" if (EE_AVAILABLE and IS_GEE_INITIALIZED) else "OFFLINE_SYNTHETIC"
    }


if __name__ == "__main__":
    print("--- Running Standalone GEE Temporal Anomaly Test ---")
    initialize_gee()
    res = analyze_parcel_temporal_anomaly("AP-07-0103-006-00070")
    print(f"Results for AP-07-0103-006-00070:")
    print(f"  Mode: {res['mode']}")
    print(f"  NDVI Readings: {res['ndvi_series_length']}")
    print(f"  Changepoints Detected: {res['changepoints_detected']}")
    print(f"  Instability Score: {res['instability_score']}")
