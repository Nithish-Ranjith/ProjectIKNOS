import cv2
import numpy as np
import onnxruntime as ort
import matplotlib.pyplot as plt
from pathlib import Path
import json

def main():
    model_path = Path("models/weights/v2_real_model.onnx")
    data_dir = Path("ml/boundary/v2/satellite_training_data")
    images_dir = data_dir / "images"
    masks_dir = data_dir / "masks"
    
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    
    # Grab the first 3 images
    image_paths = sorted(list(images_dir.glob("*.png")))[:3]
    
    fig, axes = plt.subplots(3, 3, figsize=(15, 15))
    
    for i, img_path in enumerate(image_paths):
        mask_path = masks_dir / img_path.name
        
        # Load image
        img = cv2.imread(str(img_path))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Load mask
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        # Preprocess for ONNX
        inp = img.astype(np.float32) / 255.0
        inp = np.transpose(inp, (2, 0, 1))
        # Add a dummy centroid channel since model expects 4 channels
        centroid_channel = np.zeros((1, 512, 512), dtype=np.float32)
        # We simulate the centroid by placing a 1 in the center
        centroid_channel[0, 256, 256] = 1.0
        inp = np.concatenate([inp, centroid_channel], axis=0)
        inp = np.expand_dims(inp, axis=0)
        
        # Run inference
        out = session.run(None, {input_name: inp})[0]
        # Sigmoid
        out = 1.0 / (1.0 + np.exp(-out))
        pred_mask = (out[0, 0] > 0.5).astype(np.uint8) * 255
        
        # Plot
        axes[i, 0].imshow(img)
        axes[i, 0].set_title(f"Image {i+1}")
        axes[i, 0].axis('off')
        
        axes[i, 1].imshow(gt_mask, cmap='gray')
        axes[i, 1].set_title(f"Ground Truth {i+1}")
        axes[i, 1].axis('off')
        
        axes[i, 2].imshow(pred_mask, cmap='gray')
        axes[i, 2].set_title(f"Prediction {i+1}")
        axes[i, 2].axis('off')
        
    out_path = Path("/Users/nithishranjith/.gemini/antigravity-ide/brain/01bad735-f95e-460f-a7a6-222c014cc4a4/scratch/inference_overlay.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(str(out_path))
    print(f"Saved inference overlay to {out_path}")

if __name__ == "__main__":
    main()
