"""
ml/temporal/sentinel_fetch.py — Sentinel-2 NDVI time series fetcher via Google Earth Engine.

Design contracts:
  - Requires GEE authentication. Uses env var GEE_PROJECT for project ID.
  - If GEE_PROJECT is not set, returns a stub result that is flagged as
    'NOT_RUN_GEE_PROJECT_MISSING' — never silently returns fake data.
  - NDVI time series is raw satellite data, NOT a land-use classification.
  - This is a temporal consistency check — not a legal boundary determination.

Blocker: BQ-03 — GEE project ID and service account credentials required.
"""
import os
import json
from datetime import datetime
from typing import Optional

GEE_PROJECT = os.environ.get("GEE_PROJECT")


def fetch_ndvi_timeseries(
    parcel_geojson: dict,
    start_year: int = 2017,
    end_year: Optional[int] = None,
) -> dict:
    """
    Fetch NDVI time series for a parcel from Sentinel-2.
    
    Returns:
        dict with keys:
          status: 'SUCCESS' | 'NOT_RUN_GEE_PROJECT_MISSING' | 'ERROR'
          dates: list[str]
          ndvi_values: list[float]
          n_observations: int
          gee_project: str
    """
    if not GEE_PROJECT:
        return {
            "status": "NOT_RUN_GEE_PROJECT_MISSING",
            "dates": [],
            "ndvi_values": [],
            "n_observations": 0,
            "gee_project": None,
            "note": (
                "BQ-03 BLOCKER: GEE_PROJECT environment variable not set. "
                "Set GEE_PROJECT=<your-gee-project-id> and ensure service account credentials "
                "are configured to enable Sentinel-2 temporal analysis."
            )
        }

    end_year = end_year or datetime.now().year

    try:
        import ee
        ee.Initialize(project=GEE_PROJECT)

        # Build AOI geometry from GeoJSON
        if parcel_geojson.get("type") == "Feature":
            geometry = ee.Geometry(parcel_geojson["geometry"])
        else:
            geometry = ee.Geometry(parcel_geojson)

        # Sentinel-2 SR, cloud filter
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geometry)
            .filterDate(f"{start_year}-01-01", f"{end_year}-12-31")
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
            .select(["B4", "B8"])
        )

        def add_ndvi(image):
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            return image.addBands(ndvi).set("date", image.date().format("YYYY-MM-dd"))

        with_ndvi = collection.map(add_ndvi)

        def compute_mean(image):
            mean = image.select("NDVI").reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=10,
                maxPixels=1e9
            )
            return ee.Feature(None, {"date": image.get("date"), "ndvi": mean.get("NDVI")})

        features = with_ndvi.map(compute_mean)
        result = features.getInfo()

        dates, ndvi_vals = [], []
        for feat in result["features"]:
            props = feat["properties"]
            if props.get("ndvi") is not None:
                dates.append(props["date"])
                ndvi_vals.append(props["ndvi"])

        # Sort by date
        pairs = sorted(zip(dates, ndvi_vals))
        dates = [p[0] for p in pairs]
        ndvi_vals = [p[1] for p in pairs]

        return {
            "status": "SUCCESS",
            "dates": dates,
            "ndvi_values": ndvi_vals,
            "n_observations": len(dates),
            "gee_project": GEE_PROJECT
        }

    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "dates": [],
            "ndvi_values": [],
            "n_observations": 0,
            "gee_project": GEE_PROJECT
        }
