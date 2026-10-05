import onnxruntime as ort
import numpy as np
import glob
import os
from PIL import Image
import matplotlib.pyplot as plt

def generate_proofs():
    model_path = "models/weights/v2_real_model.onnx"
    data_dir = "data_extracted/iknos_dataset_1000 2/dataset"
    out_dir = "/Users/nithishranjith/.gemini/antigravity-ide/brain/01bad735-f95e-460f-a7a6-222c014cc4a4"
    
    print(f"Loading ONNX model: {model_path}")
    session = ort.InferenceSession(model_path)
    input_name = session.get_inputs()[0].name
    
    mask_files = glob.glob(os.path.join(data_dir, "masks", "*.png"))
    # We will pick 5 samples from the END of the dataset to ensure they are validation tiles
    test_files = mask_files[-10:] 
    
    valid_count = 0
    
    for i, mask_path in enumerate(test_files):
        if valid_count >= 5:
            break
            
        filename = os.path.basename(mask_path)
        img_path = os.path.join(data_dir, "images", filename)
        
        if not os.path.exists(img_path):
            continue
            
        img_pil = Image.open(img_path).convert("RGB")
        mask_pil = Image.open(mask_path).convert("L")
        
        img = np.array(img_pil)
        mask = np.array(mask_pil)
            
        if img.shape[0] != 512 or img.shape[1] != 512:
            continue
            
        # Create input tensor
        # 1. Normalize image
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        img_norm = (img.astype(np.float32) / 255.0 - mean) / std
        img_norm = img_norm.transpose(2, 0, 1) # (3, H, W)
        
        # 2. Gaussian Heatmap (Centroid of mask)
        coords = np.argwhere(mask > 0)
        dist_map = np.zeros((1, 512, 512), dtype=np.float32)
        if len(coords) > 0:
            cy, cx = coords.mean(axis=0)
            y, x = np.ogrid[:512, :512]
            dist_map[0] = np.exp(-((x - cx)**2 + (y - cy)**2) / (2.0 * 50**2))
            
        input_tensor = np.concatenate([img_norm, dist_map], axis=0) # (4, 512, 512)
        input_tensor = np.expand_dims(input_tensor, axis=0).astype(np.float32) # (1, 4, 512, 512)
        
        # Inference
        outputs = session.run(None, {input_name: input_tensor})
        pred = outputs[0][0, 0] # (512, 512)
        
        # Sigmoid
        pred_sig = 1.0 / (1.0 + np.exp(-pred))
        pred_bin = (pred_sig > 0.5).astype(np.uint8)
        
        import scipy.ndimage as ndimage
        
        # Visualization
        fig, axes = plt.subplots(1, 4, figsize=(20, 5))
        
        # 1. Original RGB
        axes[0].imshow(img)
        axes[0].set_title("Original Drone Tile")
        axes[0].axis('off')
        
        # 2. Ground Truth Mask
        axes[1].imshow(mask, cmap='gray')
        axes[1].set_title("Ground Truth (Cadastral)")
        axes[1].axis('off')
        
        # 3. AI Prediction Heatmap
        axes[2].imshow(pred_sig, cmap='jet')
        axes[2].set_title("AI Heatmap Prediction")
        axes[2].axis('off')
        
        # 4. Overlay with Contours
        overlay = img.copy()
        
        # Get edges using erosion
        gt_erosion = ndimage.binary_erosion(mask > 0, iterations=2)
        gt_edges = (mask > 0) ^ gt_erosion
        
        pred_erosion = ndimage.binary_erosion(pred_bin, iterations=2)
        pred_edges = pred_bin ^ pred_erosion
        
        # Ground truth edges in Green
        overlay[gt_edges, 0] = 0
        overlay[gt_edges, 1] = 255
        overlay[gt_edges, 2] = 0
        
        # Predicted edges in Red
        overlay[pred_edges, 0] = 255
        overlay[pred_edges, 1] = 0
        overlay[pred_edges, 2] = 0
        
        axes[3].imshow(overlay)
        axes[3].set_title(f"Overlay (GT=Green, AI=Red)")
        axes[3].axis('off')
        
        plt.tight_layout()
        save_path = os.path.join(out_dir, f"practical_proof_{valid_count}.png")
        plt.savefig(save_path, dpi=150)
        plt.close()
        
        print(f"Saved proof {valid_count} to {save_path}")
        valid_count += 1

if __name__ == "__main__":
    generate_proofs()
