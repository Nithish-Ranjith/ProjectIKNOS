import os
import sys
import json
import uuid
import argparse
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import geopandas as gpd
from statsmodels.tsa.seasonal import STL
from sklearn.ensemble import RandomForestClassifier

# ==============================================================================
# 1. CONFIGURATION & DIRECTORY PATHS
# ==============================================================================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_INPUT_DIR = os.path.join(PROJECT_ROOT, "data", "input")
DATA_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "output")
os.makedirs(DATA_OUTPUT_DIR, exist_ok=True)

CONFIG = {
    "BASE_DATA_DIR": DATA_INPUT_DIR,
    "OUTPUT_DIR": DATA_OUTPUT_DIR,
    "PARCELS_PATH": os.path.join(DATA_INPUT_DIR, "parcels.geojson"),
    "ROR_PATH": os.path.join(DATA_INPUT_DIR, "ror.csv"),
    "REG_PATH": os.path.join(DATA_INPUT_DIR, "registration.csv"),
    "HISTORY_PATH": os.path.join(DATA_INPUT_DIR, "parcel_history.csv"),
    "TIMESERIES_PATH": os.path.join(DATA_INPUT_DIR, "satellite_ndvi_sar_timeseries.csv"),

    "SCORE_WEIGHTS": {
        "ror_missing": 0.20,
        "registration_missing": 0.15,
        "satellite_activity_anomaly": 0.25,
        "crop_landuse_unusual": 0.15,
        "acreage_discrepancy": 0.15,
        "boundary_geometry_anomaly": 0.10,
    },
    "INVESTIGATION_THRESHOLDS": {
        "low_max": 0.35,      # < 0.35 -> ROUTINE_MONITORING
        "medium_max": 0.65,   # 0.35 to 0.65 -> INCREASED_MONITORING; >= 0.65 -> INVESTIGATION_REQUIRED
    },
    "TRIAGE": {
        "persistence_min_cycles": 2,
    },
    "GRIEVANCE": {
        "max_per_parcel_per_30_days": 2,
        "min_evidence_items": 1,
    },
}

# ==============================================================================
# 2. DATA INGESTION & RESHAPING
# ==============================================================================
def load_and_prep_data():
    print("[1/5] Ingesting cadastral records and satellite time-series...")
    if not os.path.exists(CONFIG["PARCELS_PATH"]):
        sys.exit(f"Error: Parcels file not found at {CONFIG['PARCELS_PATH']}")

    parcels = gpd.read_file(CONFIG["PARCELS_PATH"])
    ror = pd.read_csv(CONFIG["ROR_PATH"]) if os.path.exists(CONFIG["ROR_PATH"]) else pd.DataFrame()
    reg = pd.read_csv(CONFIG["REG_PATH"]) if os.path.exists(CONFIG["REG_PATH"]) else pd.DataFrame()
    history = pd.read_csv(CONFIG["HISTORY_PATH"]) if os.path.exists(CONFIG["HISTORY_PATH"]) else pd.DataFrame()

    raw_ts = pd.read_csv(CONFIG["TIMESERIES_PATH"])
    if "ndvi" in raw_ts.columns and "sar_vh" in raw_ts.columns:
        id_col = "internal_parcel_key" if "internal_parcel_key" in raw_ts.columns else "parcel_id"
        melted = raw_ts.melt(
            id_vars=[id_col, "date"],
            value_vars=["ndvi", "sar_vh"],
            var_name="variable",
            value_name="value"
        ).rename(columns={id_col: "internal_parcel_key"})
        melted["variable"] = melted["variable"].str.upper()
        ts_df = melted
    else:
        ts_df = raw_ts

    parquet_out = os.path.join(CONFIG["OUTPUT_DIR"], "parcel_time_series.parquet")
    ts_df.to_parquet(parquet_out, index=False)
    print(f"      Cached normalized time series -> {parquet_out}")

    return parcels, ror, reg, history, ts_df

# ==============================================================================
# 3. TIME SERIES ANOMALY DETECTION (STL + CUSUM)
# ==============================================================================
def detect_change(parcel_key: str, ts_df: pd.DataFrame, variable="NDVI"):
    sub = ts_df[(ts_df.internal_parcel_key.astype(str) == str(parcel_key)) & (ts_df.variable == variable)].copy()
    sub = sub.sort_values("date").drop_duplicates(subset=["date"])

    if len(sub) < 8:
        return {
            "change_detected": False,
            "persistent": False,
            "reason": "insufficient_observations",
            "n_observations": len(sub),
            "raw_cusum_strength": 0.0,
            "change_magnitude": 0.0,
            "component": "none",
            "estimated_break_date": None,
            "estimated_break_window": None,
        }

    series = pd.Series(sub["value"].values, index=pd.to_datetime(sub["date"].values))
    series = series.interpolate(method="time").bfill().ffill()

    period = 12 if len(series) >= 24 else max(3, len(series) // 2)
    if period % 2 == 0:
        period += 1

    try:
        stl = STL(series, period=period, robust=True).fit()
        resid = stl.resid.dropna()
        trend = stl.trend
    except Exception as e:
        return {
            "change_detected": False,
            "persistent": False,
            "reason": f"stl_failed: {str(e)}",
            "n_observations": len(series),
            "raw_cusum_strength": 0.0,
            "change_magnitude": 0.0,
            "component": "none",
            "estimated_break_date": None,
            "estimated_break_window": None,
        }

    cusum = (resid - resid.mean()).cumsum()
    cusum_std = cusum / (resid.std() + 1e-9)
    break_idx = int(np.argmax(np.abs(cusum_std.values)))
    break_date = cusum_std.index[break_idx]
    break_strength = float(np.abs(cusum_std.values[break_idx]))

    raw_break_detected = break_strength > 2.5
    trend_slope_before = float(np.polyfit(range(break_idx), trend.values[:break_idx], 1)[0]) if break_idx > 2 else 0.0
    trend_slope_after = float(np.polyfit(range(len(trend) - break_idx), trend.values[break_idx:], 1)[0]) if (len(trend) - break_idx) > 2 else 0.0

    min_cycles = CONFIG["TRIAGE"]["persistence_min_cycles"]
    persistent = False
    if raw_break_detected and break_idx + min_cycles <= len(trend):
        pre_break_level = trend.values[:break_idx].mean() if break_idx > 0 else trend.values[0]
        post_window = trend.values[break_idx: break_idx + min_cycles]
        deviation = post_window - pre_break_level
        persistent = bool(np.all(np.sign(deviation) == np.sign(deviation[0])) and
                          np.all(np.abs(deviation) > 0.15 * abs(resid.std())))

    change_detected = bool(raw_break_detected and persistent)

    return {
        "change_detected": change_detected,
        "persistent": persistent,
        "likely_seasonal": bool(raw_break_detected and not persistent),
        "estimated_break_date": break_date.date().isoformat(),
        "estimated_break_window": [
            (break_date - pd.Timedelta(days=32)).date().isoformat(),
            (break_date + pd.Timedelta(days=32)).date().isoformat(),
        ],
        "change_magnitude": round(min(break_strength / 10.0, 1.0), 3) if change_detected else 0.0,
        "raw_cusum_strength": round(break_strength, 2),
        "trend_slope_before": round(trend_slope_before, 5),
        "trend_slope_after": round(trend_slope_after, 5),
        "component": "trend" if abs(trend_slope_after - trend_slope_before) > 0.001 else "seasonal",
        "n_observations": len(series),
    }

# ==============================================================================
# 4. CROP / PHENOLOGY CLASSIFIER
# ==============================================================================
def train_crop_classifier(ts_df: pd.DataFrame):
    piv = ts_df.groupby(["internal_parcel_key", "variable"])["value"].agg(["mean", "std", "max", "min"]).unstack()
    piv.columns = [f"{c[0]}_{c[1]}" for c in piv.columns]
    piv = piv.fillna(0.0)

    classes = ["paddy", "cotton", "chilli", "maize", "fallow"]
    np.random.seed(0)
    mock_labels = [classes[i % len(classes)] for i in range(len(piv))]

    clf = RandomForestClassifier(n_estimators=30, random_state=0)
    clf.fit(piv, mock_labels)
    return clf, piv

# ==============================================================================
# 5. PRIORITY SCORING & CASE COMPILER
# ==============================================================================
def compute_priority_score(parcel_key, parcel_row, ror_df, reg_df, change_res, crop_pred, crop_conf):
    w = CONFIG["SCORE_WEIGHTS"]
    ror_match = not ror_df[ror_df.internal_parcel_key.astype(str) == str(parcel_key)].empty if not ror_df.empty else False
    reg_match = not reg_df[reg_df.internal_parcel_key.astype(str) == str(parcel_key)].empty if not reg_df.empty else False

    ror_act = 0.0 if ror_match else 1.0
    reg_act = 0.0 if reg_match else 1.0
    sat_act = 1.0 if change_res.get("change_detected", False) else 0.0
    crop_act = float(np.clip(1.0 - crop_conf, 0.0, 1.0))
    acreage_act = 0.0
    geom_act = 0.0

    raw_score = (
        w["ror_missing"] * ror_act +
        w["registration_missing"] * reg_act +
        w["satellite_activity_anomaly"] * sat_act +
        w["crop_landuse_unusual"] * crop_act +
        w["acreage_discrepancy"] * acreage_act +
        w["boundary_geometry_anomaly"] * geom_act
    )

    factors = [
        {"factor": "ror_missing", "weight": w["ror_missing"], "activation": ror_act},
        {"factor": "registration_missing", "weight": w["registration_missing"], "activation": reg_act},
        {"factor": "satellite_activity_anomaly", "weight": w["satellite_activity_anomaly"], "activation": sat_act},
        {"factor": "crop_landuse_unusual", "weight": w["crop_landuse_unusual"], "activation": round(crop_act, 3)},
        {"factor": "acreage_discrepancy", "weight": w["acreage_discrepancy"], "activation": acreage_act},
        {"factor": "boundary_geometry_anomaly", "weight": w["boundary_geometry_anomaly"], "activation": geom_act},
    ]

    return round(raw_score, 3), factors, ror_match, reg_match

def build_case_json(parcel_key, parcel_row, score, factors, change_res, crop_pred, crop_conf, ror_match, reg_match, trigger_source="proactive_satellite"):
    now_iso = datetime.now(timezone.utc).isoformat()
    case_uid = f"CASE-2026-{uuid.uuid4().hex[:6].upper()}"

    centroid = [parcel_row.geometry.centroid.x, parcel_row.geometry.centroid.y] if hasattr(parcel_row, "geometry") and parcel_row.geometry else [0.0, 0.0]
    bbox = list(parcel_row.geometry.bounds) if hasattr(parcel_row, "geometry") and parcel_row.geometry else [0, 0, 0, 0]

    return {
        "case_id": case_uid,
        "schema_version": "1.1",
        "status": "OFFICER_REVIEW_PENDING",
        "created_at": now_iso,
        "updated_at": now_iso,
        "parcel": {
            "internal_parcel_key": str(parcel_key),
            "ulpin": getattr(parcel_row, "ulpin", None),
            "survey_number": str(getattr(parcel_row, "survey_number", "unknown")),
            "village_code": str(getattr(parcel_row, "village_code", "000")),
            "tehsil_code": str(getattr(parcel_row, "tehsil_code", "0000")),
            "district_code": str(getattr(parcel_row, "district_code", "AP00")),
            "state_code": "AP",
            "centroid": {"type": "Point", "coordinates": centroid},
            "bbox": bbox,
            "cadastral_geometry_ref": f"geo://cadastral/{parcel_key}/v1",
            "record_refs": {"ror_id": None, "registration_id": None, "mutation_id": None}
        },
        "trigger": {
            "source": trigger_source,
            "triggered_at": now_iso,
            "triggering_ref": f"CLI-{parcel_key}-{datetime.now().strftime('%Y-%m-%d')}"
        },
        "priority_score": {
            "value": score,
            "raw_score": score,
            "history_adjustment": 0.0,
            "history_adjustment_basis": "No prior case history on this parcel",
            "scale": "0_to_1",
            "contributing_factors": factors
        },
        "parcel_lock": {
            "locked": True,
            "locked_at": now_iso,
            "locked_by_case_id": case_uid,
            "lock_ttl_hours": 168,
            "escalated": False
        },
        "evidence": {
            "record_evidence": {
                "ror_status": "present" if ror_match else "missing",
                "registration_status": "present" if reg_match else "missing",
                "last_mutation_date": None,
                "dispute_history_ref": None
            },
            "satellite_evidence": {
                "analysis_window": {"start": "2023-01-01", "end": "2026-08-31"},
                "anomaly_score": 1.0 if change_res.get("change_detected") else 0.0,
                "anomaly_category": "unusual_vegetation_pattern" if change_res.get("change_detected") else "none",
                "ndvi_series_ref": f"ts://sentinel2/ndvi/{parcel_key}",
                "sar_series_ref": f"ts://sentinel1/vh/{parcel_key}",
                "confidence": "high" if change_res.get("change_detected") else "low",
                "track_a_extended_signals": {
                    "change_detected": change_res.get("change_detected", False),
                    "estimated_break_date": change_res.get("estimated_break_date"),
                    "estimated_break_window": change_res.get("estimated_break_window"),
                    "component": change_res.get("component"),
                    "crop_prediction": crop_pred,
                    "crop_confidence": round(crop_conf, 3),
                    "acreage_estimated_sqm": None,
                    "acreage_discrepancy_pct": None
                }
            },
            "spatial_evidence": None
        },
        "explanation": {
            "summary": f"Satellite time series break evaluated. Predicted crop: {crop_pred}.",
            "reasoning_trace": [
                {"rule": "ror_missing_check", "result": str(not ror_match).lower(), "detail": "RoR record missing" if not ror_match else "Found"},
                {"rule": "registration_missing_check", "result": str(not reg_match).lower(), "detail": "Registration record missing" if not reg_match else "Found"},
                {"rule": "ndvi_trend_break_check", "result": "deviation_detected" if change_res.get("change_detected") else "normal", "detail": f"Break on {change_res.get('estimated_break_date')}"}
            ]
        },
        "field_verification": None,
        "officer_decision": {"decision": None, "decided_by": None, "decided_at": None, "reason": None, "signature_ref": None},
        "update_classification": None,
        "record_update": None,
        "audit": None,
        "history": []
    }

# ==============================================================================
# 6. EXECUTION MODES
# ==============================================================================
def run_sweep_mode():
    parcels, ror, reg, history, ts_df = load_and_prep_data()
    print("[2/5] Running STL + CUSUM time series anomaly detection...")
    change_results = {str(k): detect_change(str(k), ts_df, "NDVI") for k in parcels["internal_parcel_key"]}

    print("[3/5] Classifying land-use phenology...")
    clf, piv = train_crop_classifier(ts_df)

    print("[4/5] Evaluating triage gate and assembling cases...")
    cases, screening_log = [], []
    for _, row in parcels.iterrows():
        pkey = str(row["internal_parcel_key"])
        c_res = change_results.get(pkey, {})

        if pkey in piv.index:
            probs = clf.predict_proba(piv.loc[[pkey]])[0]
            pred_class = clf.classes_[np.argmax(probs)]
            conf = float(np.max(probs))
        else:
            pred_class, conf = "unknown", 0.0

        score, factors, ror_match, reg_match = compute_priority_score(pkey, row, ror, reg, c_res, pred_class, conf)

        if score >= CONFIG["INVESTIGATION_THRESHOLDS"]["medium_max"]:
            case = build_case_json(pkey, row, score, factors, c_res, pred_class, conf, ror_match, reg_match, "proactive_satellite")
            cases.append(case)
            action = "ESCALATED_TO_CASE"
        elif score >= CONFIG["INVESTIGATION_THRESHOLDS"]["low_max"]:
            action = "INCREASED_MONITORING"
        else:
            action = "ROUTINE_MONITORING"

        screening_log.append({
            "parcel_key": pkey,
            "priority_score": score,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    print("[5/5] Writing pipeline outputs...")
    cases_path = os.path.join(CONFIG["OUTPUT_DIR"], "track_a_cases.json")
    log_path = os.path.join(CONFIG["OUTPUT_DIR"], "track_a_screening_log.json")

    with open(cases_path, "w") as f:
        json.dump(cases, f, indent=2)
    with open(log_path, "w") as f:
        json.dump(screening_log, f, indent=2)

    print(f"\nCompleted Satellite Sweep:")
    print(f"  * Total Parcels Processed: {len(parcels)}")
    print(f"  * Cases Escalated (Score >= {CONFIG['INVESTIGATION_THRESHOLDS']['medium_max']}): {len(cases)}")
    print(f"  * Cases JSON -> {cases_path}")
    print(f"  * Screening Log -> {log_path}\n")

def run_grievance_mode(target_parcel: str, claimant: str, desc: str):
    parcels, ror, reg, history, ts_df = load_and_prep_data()
    matches = parcels[parcels.internal_parcel_key.astype(str) == str(target_parcel)]

    if matches.empty:
        sys.exit(f"Error: Parcel key '{target_parcel}' not found in cadastral registry.")

    row = matches.iloc[0]
    print(f"Processing grievance for parcel: {target_parcel}...")

    c_res = detect_change(str(target_parcel), ts_df, "NDVI")
    clf, piv = train_crop_classifier(ts_df)

    if str(target_parcel) in piv.index:
        probs = clf.predict_proba(piv.loc[[str(target_parcel)]])[0]
        pred_class = clf.classes_[np.argmax(probs)]
        conf = float(np.max(probs))
    else:
        pred_class, conf = "unknown", 0.0

    score, factors, ror_match, reg_match = compute_priority_score(target_parcel, row, ror, reg, c_res, pred_class, conf)
    case = build_case_json(target_parcel, row, score, factors, c_res, pred_class, conf, ror_match, reg_match, "citizen_grievance")

    out_path = os.path.join(CONFIG["OUTPUT_DIR"], "citizen_grievance_case.json")
    with open(out_path, "w") as f:
        json.dump(case, f, indent=2)

    print("\nCitizen Intake Accepted:")
    print(f"  * Case ID: {case['case_id']}")
    print(f"  * Priority Score: {case['priority_score']['value']}")
    print(f"  * Parcel Locked: {case['parcel_lock']['locked']}")
    print(f"  * Saved Case -> {out_path}\n")

# ==============================================================================
# 7. COMMAND-LINE INTERFACE (CLI) ENTRYPOINT
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IKNOS Track A - Land Monitoring Pipeline")
    parser.add_argument(
        "--mode",
        choices=["sweep", "grievance"],
        default="sweep",
        help="Execution mode: 'sweep' for proactive monitoring or 'grievance' for on-demand complaint intake."
    )
    parser.add_argument("--parcel", type=str, default="AP-07-0103-006-00070", help="Target parcel key (grievance mode)")
    parser.add_argument("--claimant", type=str, default="Citizen Claimant", help="Claimant name (grievance mode)")
    parser.add_argument("--desc", type=str, default="Boundary encroachment reported", help="Grievance description")

    args = parser.parse_args()

    if args.mode == "sweep":
        run_sweep_mode()
    elif args.mode == "grievance":
        run_grievance_mode(args.parcel, args.claimant, args.desc)