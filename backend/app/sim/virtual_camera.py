import os
import json
import uuid
import numpy as np
from datetime import datetime, timezone
from PIL import Image, ImageFilter
from .virtual_drone import Capture

def capture_image(capture: Capture, out_dir: str, cam_config: dict, is_blurry: bool = False):
    """
    Simulates a camera trigger.
    Writes image_{seq}.jpg and image_{seq}.json.
    """
    os.makedirs(out_dir, exist_ok=True)
    img_w = cam_config.get("image_width_px", 3280)
    img_h = cam_config.get("image_height_px", 2464)
    
    import cv2 # for laplacian variance
    # Generate a dummy synthetic field texture with high frequency details so it passes blur check
    base = np.random.randint(50, 200, (img_h, img_w, 3), dtype=np.uint8)
    # Add strong edges
    for i in range(100):
        cv2.circle(base, (np.random.randint(0, img_w), np.random.randint(0, img_h)), np.random.randint(5, 50), (255, 255, 255), -1)
    img = Image.fromarray(base)
    
    if is_blurry:
        img = img.filter(ImageFilter.GaussianBlur(radius=5.0))
        
    img_name = f"image_{capture.seq:04d}.jpg"
    json_name = f"image_{capture.seq:04d}.json"
    
    img_path = os.path.join(out_dir, img_name)
    img.save(img_path, quality=80)
    
    # Calculate blur score like the API would, just to have realistic numbers in the sidecar
    # The API might recalculate it, or we supply it. The schema has blur_score.
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    quality_flag = "REJECT" if blur_score < 100 else "OK" # The API's threshold might differ
    
    image_id = str(uuid.uuid4())
    meta = {
        "image_id": image_id,
        "mission_id": cam_config.get("mission_id", "sim_mission"),
        "seq": capture.seq,
        "lat": capture.geotag_xy[1],
        "lon": capture.geotag_xy[0],
        "alt_m": capture.alt,
        "yaw_deg": 0.0,
        "gps_fix_type": "3D_FIX",
        "timestamp_gps": datetime.now(timezone.utc).isoformat(),
        "blur_score": float(blur_score),
        "quality_flag": quality_flag,
        "camera_id": cam_config.get("profile_id", "picam_v2_sim_01"),
        "simulated": True,
        "true_lat": capture.true_xy[1],
        "true_lon": capture.true_xy[0]
    }
    
    with open(os.path.join(out_dir, json_name), "w") as f:
        json.dump(meta, f, indent=2)
        
    return img_path, meta
