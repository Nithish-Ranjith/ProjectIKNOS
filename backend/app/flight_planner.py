import math
import numpy as np
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from shapely.affinity import rotate, translate, scale
import pyproj
from shapely.ops import transform

def get_utm_zone(lon: float) -> str:
    """Returns the EPSG code for the UTM zone of a given longitude."""
    zone = int((lon + 180) / 6) + 1
    return f"EPSG:{32600 + zone}"

def long_edge_angle(poly: Polygon) -> float:
    """Returns the angle (in degrees) of the longest edge of the minimum rotated rectangle."""
    coords = list(poly.exterior.coords)
    max_len = 0
    best_angle = 0
    for i in range(len(coords)-1):
        p1 = coords[i]
        p2 = coords[i+1]
        length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if length > max_len:
            max_len = length
            best_angle = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
    return best_angle

def plan(poly_wgs84: Polygon, cam: dict, gsd_m: float, fwd: float = 0.80, side: float = 0.70, speed_ms: float = 5.0, turn_s: float = 6.0):
    if not poly_wgs84 or poly_wgs84.is_empty:
        raise ValueError("Invalid or empty polygon provided")

    centroid = poly_wgs84.centroid
    utm_crs = get_utm_zone(centroid.x)
    
    project_to_utm = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True).transform
    project_to_wgs84 = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True).transform
    
    p_utm = transform(project_to_utm, poly_wgs84)
    
    # Camera spec extraction
    f = cam['focal_length_mm']
    img_w = cam['image_width_px']
    img_h = cam['image_height_px']
    sensor_w = cam['sensor_width_mm']
    
    altitude_m = (gsd_m * f * img_w) / sensor_w
    if altitude_m > 120:
        raise ValueError(f"Requested GSD requires altitude > 120m ({altitude_m:.1f}m)")
        
    footprint_w = gsd_m * img_w
    footprint_h = gsd_m * img_h
    
    line_spacing = footprint_w * (1 - side)
    trigger_dist = footprint_h * (1 - fwd)
    
    mrr = p_utm.minimum_rotated_rectangle
    theta = long_edge_angle(mrr)
    
    r_utm = rotate(p_utm, -theta, origin=p_utm.centroid, use_radians=False)
    
    # Buffer polygon slightly to ensure full edge coverage
    clip = r_utm.buffer(footprint_w / 2)
    
    minx, miny, maxx, maxy = clip.bounds
    
    ys = np.arange(miny + line_spacing/2, maxy, line_spacing)
    
    waypoints_utm = []
    direction = 1
    
    path_length_m = 0
    n_lines = 0
    
    for y in ys:
        line = LineString([(minx - 1, y), (maxx + 1, y)])
        intersection = clip.intersection(line)
        
        if intersection.is_empty:
            continue
            
        if isinstance(intersection, MultiPolygon) or intersection.geom_type == 'MultiLineString':
            ix_minx, _, ix_maxx, _ = intersection.bounds
            pts = [(ix_minx, y), (ix_maxx, y)]
        else:
            coords = list(intersection.coords)
            if not coords:
                continue
            pts = [coords[0], coords[-1]]
            
        if direction == -1:
            pts.reverse()
            
        waypoints_utm.extend(pts)
        n_lines += 1
        direction *= -1
        
    for i in range(len(waypoints_utm)-1):
        path_length_m += math.hypot(waypoints_utm[i+1][0] - waypoints_utm[i][0], waypoints_utm[i+1][1] - waypoints_utm[i][1])
        
    # Rotate back and reproject
    final_waypoints_wgs84 = []
    if waypoints_utm:
        line_utm = LineString(waypoints_utm)
        line_rotated = rotate(line_utm, theta, origin=p_utm.centroid, use_radians=False)
        line_wgs84 = transform(project_to_wgs84, line_rotated)
        final_waypoints_wgs84 = [list(c) for c in line_wgs84.coords]
        
    duration_s = (path_length_m / speed_ms) + (n_lines * turn_s)
    
    return {
        "waypoints": final_waypoints_wgs84,
        "altitude_m": altitude_m,
        "cam_trigg_dist_m": trigger_dist,
        "line_spacing_m": line_spacing,
        "path_length_m": path_length_m,
        "n_lines": n_lines,
        "est_images": path_length_m / trigger_dist if trigger_dist > 0 else 0,
        "duration_s": duration_s
    }
