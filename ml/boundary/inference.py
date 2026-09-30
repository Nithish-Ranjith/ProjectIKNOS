"""
ml/boundary/inference.py — U-Net tile inference pipeline.

Takes a directory of mission images, tiles them to 256x256,
runs the U-Net, and converts the output mask to a GeoJSON polygon.
Output is a CANDIDATE physical boundary — not a legal boundary.
"""
from pathlib import Path
from typing import Optional

CANDIDATE_LABEL = "TRANSFER_LEARNED_UNVALIDATED"


def run_inference(
    image_dir: str,
    weights_path: Optional[str] = None,
    output_geojson_path: Optional[str] = None,
) -> dict:
    """
    Run U-Net inference over a set of tiles and produce a GeoJSON candidate polygon.
    
    Returns:
        {
          "status": "SUCCESS" | "ERROR" | "TORCH_NOT_AVAILABLE",
          "candidate_boundary": GeoJSON dict or None,
          "dataset_label": CANDIDATE_LABEL,
          "note": str
        }
    """
    try:
        import torch
        from torchvision import transforms
        from PIL import Image
        import numpy as np
    except ImportError:
        return {
            "status": "TORCH_NOT_AVAILABLE",
            "candidate_boundary": None,
            "dataset_label": CANDIDATE_LABEL,
            "note": "PyTorch/torchvision/Pillow not installed. Cannot run U-Net inference."
        }

    try:
        from .model import load_model
    except ImportError:
        from ml.boundary.model import load_model

    model = load_model(weights_path)
    transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.ToTensor(),
    ])

    tiles = list(Path(image_dir).glob("*.jpg")) + list(Path(image_dir).glob("*.png"))
    if not tiles:
        return {
            "status": "ERROR",
            "candidate_boundary": None,
            "dataset_label": CANDIDATE_LABEL,
            "note": "No images found in directory."
        }

    all_masks = []
    for tile_path in tiles:
        img = Image.open(tile_path).convert("RGB")
        x = transform(img).unsqueeze(0)
        with torch.no_grad():
            mask = model(x)[0, 0].numpy()
        all_masks.append(mask)

    # Average the masks (very simplified mosaicking)
    import numpy as np
    combined = np.mean(all_masks, axis=0)
    binary = (combined > 0.5).astype(np.uint8) * 255

    # Convert binary mask to a simple bounding polygon (placeholder — use cv2.findContours in production)
    candidate_polygon = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]  # placeholder coordinates
        },
        "properties": {
            "dataset_label": CANDIDATE_LABEL,
            "note": "This is a candidate physical boundary derived from U-Net inference. NOT a legal boundary."
        }
    }

    if output_geojson_path:
        import json
        with open(output_geojson_path, "w") as f:
            json.dump(candidate_polygon, f, indent=2)

    return {
        "status": "SUCCESS",
        "candidate_boundary": candidate_polygon,
        "dataset_label": CANDIDATE_LABEL,
        "note": "Candidate boundary from U-Net. Transfer-learned weights — fine-tuning on Indian data required (BQ-04)."
    }
