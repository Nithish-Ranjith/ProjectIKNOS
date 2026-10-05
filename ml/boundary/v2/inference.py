Standalone inference script for the IKNOS v2 (centroid-conditioned) model.
Only needs: onnxruntime, opencv-python, numpy

The model needs to know WHICH parcel to extract -- pass the target parcel's
pixel-space centroid (cx, cy) within this tile, derived from its known
cadastral coordinates.

Usage:
    python inference.py path/to/satellite_tile.png <centroid_x> <centroid_y>
"""
import sys, json
import numpy as np
import cv2
import onnxruntime as ort

CONFIG_PATH = "model_config.json"
ONNX_PATH = "model.onnx"

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def make_gaussian_heatmap(cy, cx, size, sigma):
    y, x = np.mgrid[0:size, 0:size]
    return np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2)).astype(np.float32)

def preprocess(img_path, cx, cy, cfg):
    size = cfg["input_size"]
    img = cv2.cvtColor(cv2.imread(img_path), cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (size, size)).astype(np.float32) / 255.0
    mean = np.array(cfg["normalize_mean"], dtype=np.float32)
    std = np.array(cfg["normalize_std"], dtype=np.float32)
    img = (img - mean) / std
    img = img.transpose(2, 0, 1)  # 3 x H x W

    heatmap = make_gaussian_heatmap(cy, cx, size, cfg["heatmap_sigma_px"])[None, ...]  # 1 x H x W
    inp = np.concatenate([img, heatmap], axis=0)[None, ...].astype(np.float32)  # 1 x 4 x H x W
    return inp

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def main():
    img_path, cx, cy = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    cfg = load_config()
    session = ort.InferenceSession(ONNX_PATH)
    inp = preprocess(img_path, cx, cy, cfg)
    logits = session.run(None, {"input": inp})[0]
    prob = sigmoid(logits)[0, 0]
    mask = (prob > cfg["threshold"]).astype(np.uint8) * 255
    boundary = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    cv2.imwrite("filled_mask.png", mask)
    cv2.imwrite("boundary.png", boundary)
    print("Saved filled_mask.png and boundary.png")

if __name__ == "__main__":
    main()
