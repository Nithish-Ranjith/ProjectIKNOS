"""
drone/blur_check.py — Fast Laplacian variance blur detection.

Design contracts:
  - Must run fast enough on RPi4 to keep up with 1-2 Hz capture rate.
  - Updates the sidecar JSON with blur_score and quality_flag.
  - Does NOT delete the image, just flags it.
"""
import cv2
import json
import os
import glob
from pathlib import Path

def variance_of_laplacian(image_path: str) -> float:
    """Compute the Laplacian variance as a proxy for blur."""
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return 0.0
    
    # Resize down to speed up calculation on Pi
    image_small = cv2.resize(image, (640, 480))
    return cv2.Laplacian(image_small, cv2.CV_64F).var()

def process_unscored_images(capture_dir: str, threshold: float = 100.0):
    """Scan directory for sidecars with quality_flag='PENDING' and score them."""
    search_pattern = os.path.join(capture_dir, "*.json")
    for sidecar_path in glob.glob(search_pattern):
        with open(sidecar_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue
                
        if data.get("quality_flag") == "PENDING":
            img_path = sidecar_path.replace(".json", ".jpg")
            if not os.path.exists(img_path):
                continue
                
            score = variance_of_laplacian(img_path)
            data["blur_score"] = round(score, 2)
            data["quality_flag"] = "PASS" if score >= threshold else "BLUR"
            
            with open(sidecar_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"Scored {img_path}: {data['blur_score']} -> {data['quality_flag']}")

if __name__ == "__main__":
    # Test execution
    process_unscored_images("/tmp/iknos_captures")
