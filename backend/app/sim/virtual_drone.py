import numpy as np
from shapely.geometry import LineString, Point
from dataclasses import dataclass
from typing import Tuple

@dataclass
class Capture:
    seq: int
    true_xy: Tuple[float, float]
    geotag_xy: Tuple[float, float]
    alt: float

class VirtualPlan:
    def __init__(self, waypoints_utm, altitude_m, cam_trigg_dist_m):
        self.waypoints_utm = waypoints_utm
        self.altitude_m = altitude_m
        self.cam_trigg_dist_m = cam_trigg_dist_m

import pyproj
from shapely.ops import transform

def get_utm_zone(lon: float) -> str:
    zone = int((lon + 180) / 6) + 1
    return f"EPSG:{32600 + zone}"

def fly(plan: VirtualPlan, speed=5.0, dt=0.2, gps_sigma_m=1.5, drift_m=2.0, seed=42):
    rng = np.random.default_rng(seed)                  # deterministic demo
    
    # Project to UTM
    centroid_lon = plan.waypoints_utm[0][0] # it's actually wgs84
    utm_crs = get_utm_zone(centroid_lon)
    project_to_utm = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True).transform
    project_to_wgs84 = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True).transform
    
    path_wgs84 = LineString(plan.waypoints_utm)
    path_utm = transform(project_to_utm, path_wgs84)
    
    s, next_trig, seq, drift = 0.0, 0.0, 0, np.zeros(2)
    while s < path_utm.length:
        s += speed * dt
        drift = 0.98 * drift + rng.normal(0, drift_m * 0.05, 2)   # slow wind wander
        true_utm = np.array(path_utm.interpolate(s).coords[0]) + drift
        meas_utm = true_utm + rng.normal(0, gps_sigma_m, 2)               # what the GPS reports
        
        while s >= next_trig:
            # project back
            true_wgs84 = transform(project_to_wgs84, Point(true_utm[0], true_utm[1]))
            meas_wgs84 = transform(project_to_wgs84, Point(meas_utm[0], meas_utm[1]))
            
            yield Capture(
                seq=seq, 
                true_xy=(true_wgs84.x, true_wgs84.y), 
                geotag_xy=(meas_wgs84.x, meas_wgs84.y), 
                alt=plan.altitude_m
            )
            next_trig += plan.cam_trigg_dist_m
            seq += 1
