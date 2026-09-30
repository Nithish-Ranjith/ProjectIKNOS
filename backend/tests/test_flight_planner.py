import yaml
from pathlib import Path
from shapely.geometry import Polygon
from app.flight_planner import plan

def test_simulated_camera_profile():
    config_path = Path("app/config/camera.sim.yaml")
    assert config_path.exists(), "camera.sim.yaml is missing"
    
    with open(config_path, "r") as f:
        cam_config = yaml.safe_load(f)
        
    assert cam_config.get("simulated") is True
    
    planning_cfg = cam_config.get("planning", {})
    gsd_m = planning_cfg.get("target_gsd_m", 0.02)
    fwd = planning_cfg.get("forward_overlap", 0.8)
    side = planning_cfg.get("side_overlap", 0.7)
    
    # Create a dummy 100x100m parcel around equator roughly
    poly = Polygon([
        (0.0, 0.0),
        (0.001, 0.0),
        (0.001, 0.001),
        (0.0, 0.001),
        (0.0, 0.0)
    ])
    
    res = plan(
        poly_wgs84=poly,
        cam=cam_config,
        gsd_m=gsd_m,
        fwd=fwd,
        side=side
    )
    
    assert abs(res["altitude_m"] - 54.2) < 0.1, f"Expected ~54.2m, got {res['altitude_m']}"
    assert abs(res["cam_trigg_dist_m"] - 9.9) < 0.1, f"Expected ~9.9m, got {res['cam_trigg_dist_m']}"
    assert abs(res["line_spacing_m"] - 19.7) < 0.1, f"Expected ~19.7m, got {res['line_spacing_m']}"
    
    print(f"Test passed! Altitude: {res['altitude_m']:.2f}m, Trigger Dist: {res['cam_trigg_dist_m']:.2f}m, Line Spacing: {res['line_spacing_m']:.2f}m")

if __name__ == '__main__':
    test_simulated_camera_profile()
