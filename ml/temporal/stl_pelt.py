"""
ml/temporal/stl_pelt.py — STL decomposition + PELT changepoint detection.

Design contracts:
  - Input: NDVI time series from sentinel_fetch.py.
  - STL separates trend/seasonal/residual components.
  - PELT detects structural breaks in the residual.
  - Output: instability_score (0-1), onset_year (if detected), analysis_quality.
  - Output is a temporal signal, NOT a legal verdict.
  - "instability_score > 0.5" means temporal deviation detected — it does NOT
    mean an illegal land partition was detected.
"""
import math
from typing import Optional

try:
    from statsmodels.tsa.seasonal import STL
    from ruptures import Pelt
    import numpy as np
    _FULL_DEPS = True
except ImportError:
    _FULL_DEPS = False


def analyse_timeseries(
    dates: list,
    ndvi_values: list,
    parcel_id: str = "unknown"
) -> dict:
    """
    Run STL decomposition + PELT changepoint detection on NDVI time series.
    Returns:
        instability_score: 0.0 - 1.0
        onset_year: Optional[int]
        analysis_quality: 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA'
        changepoints: list[int]  (indices into time series)
        note: str (mandatory interpretation caveat)
    """
    n = len(ndvi_values)
    
    if n < 12:
        return {
            "instability_score": None,
            "onset_year": None,
            "analysis_quality": "INSUFFICIENT_DATA",
            "changepoints": [],
            "note": (
                f"Only {n} observations available (minimum 12 required for STL). "
                "Temporal analysis was not run — this is not a clean signal, treat as absent."
            )
        }

    if not _FULL_DEPS:
        # Graceful degradation — compute simple variance as a proxy
        mean_ndvi = sum(ndvi_values) / n
        variance = sum((v - mean_ndvi) ** 2 for v in ndvi_values) / n
        std = math.sqrt(variance)
        
        # Crude instability: coefficient of variation
        cv = std / max(abs(mean_ndvi), 0.01)
        instability = min(cv * 2.0, 1.0)  # scale: CV > 0.5 → instability ≈ 1.0
        
        return {
            "instability_score": round(instability, 3),
            "onset_year": None,
            "analysis_quality": "LOW",
            "changepoints": [],
            "note": (
                "statsmodels/ruptures not available — using fallback variance measure. "
                "Install full ML dependencies for STL+PELT analysis. "
                "This score is an approximation, NOT a legal land-use determination."
            )
        }

    try:
        import numpy as np
        ndvi_arr = np.array(ndvi_values)
        
        # Seasonal period: approximate monthly sampling → 12
        period = min(12, n // 2)
        stl = STL(ndvi_arr, period=period, robust=True)
        res = stl.fit()
        residual = res.resid
        trend = res.trend

        # PELT on the residual
        model = Pelt(model="rbf").fit(residual.reshape(-1, 1))
        changepoints = model.predict(pen=3)
        changepoints = [c for c in changepoints if c < n]

        # Instability score = magnitude of residual at changepoints vs baseline variance
        baseline_std = float(np.std(residual))
        if changepoints and baseline_std > 0:
            magnitudes = [abs(float(residual[c - 1])) for c in changepoints if c > 0]
            instability = min(max(magnitudes) / (baseline_std * 3.0), 1.0)
        else:
            instability = 0.0

        # Onset year from first changepoint date
        onset_year = None
        if changepoints and dates:
            first_cp = changepoints[0]
            if first_cp < len(dates):
                onset_year = int(dates[first_cp][:4])

        quality = "HIGH" if n >= 48 else ("MEDIUM" if n >= 24 else "LOW")

        return {
            "instability_score": round(instability, 3),
            "onset_year": onset_year,
            "analysis_quality": quality,
            "changepoints": changepoints,
            "note": (
                "Temporal anomaly detected via STL+PELT on Sentinel-2 NDVI. "
                "This identifies a structural break in vegetation pattern — "
                "it is NOT evidence of illegal land partition or ownership change."
            )
        }

    except Exception as e:
        return {
            "instability_score": None,
            "onset_year": None,
            "analysis_quality": "INSUFFICIENT_DATA",
            "changepoints": [],
            "note": f"Analysis failed: {e}"
        }
