import onnxruntime as ort
import numpy as np
from ml.boundary.v2.train_satellite import SatelliteParcelDataset
from torch.utils.data import Subset

def run():
    print("Evaluating IoU vs Max Probability on test set...")
    data_dir = "ml/boundary/v2/satellite_training_data"
    full_ds = SatelliteParcelDataset(data_dir, augment=True)
    villages = {}
    for idx, name in enumerate(full_ds.ids):
        parts = name.split('-')
        village = parts[3] if len(parts) >= 4 else "UNKNOWN"
        villages.setdefault(village, []).append(idx)
    sorted_villages = sorted(list(villages.keys()))
    val_village = sorted_villages[-1] if len(sorted_villages) >= 2 else sorted_villages[0]
    test_indices = villages[val_village]
    val_ds_base = SatelliteParcelDataset(data_dir, augment=False)
    
    sess_fp32 = ort.InferenceSession("models/weights/v2_real_model.onnx", providers=["CPUExecutionProvider"])
    input_name = sess_fp32.get_inputs()[0].name
    
    results = []
    for i in range(len(test_indices)):
        x, y = val_ds_base[test_indices[i]]
        inp = x.unsqueeze(0).numpy()
        y_mask = (y[0].numpy() > 0.5)
        
        out_fp32 = sess_fp32.run(None, {input_name: inp})[0][0, 0]
        prob = 1.0 / (1.0 + np.exp(-out_fp32))
        pred_fp32 = prob > 0.5
        inter = (pred_fp32 & y_mask).sum()
        uni = (pred_fp32 | y_mask).sum()
        iou = inter / uni if uni > 0 else 0
        max_prob = prob.max()
        results.append((max_prob, iou))
        print(f"Tile {i}: Max Prob = {max_prob:.4f}, IoU = {iou:.4f}")
        
    results.sort(key=lambda x: x[0])
    
    # We want to find a threshold that filters out low IoU (< 0.25)
    # but keeps high IoU (> 0.25).
    best_thresh = 0.20
    for prob_thresh in np.linspace(0.1, 0.9, 81):
        filtered_ious = [iou for (p, iou) in results if p >= prob_thresh]
        if not filtered_ious: continue
        mean_iou = np.mean(filtered_ious)
        if mean_iou > 0.60:
            best_thresh = prob_thresh
            break
            
    print(f"\nRecommended confidence gate threshold: {best_thresh:.4f}")

if __name__ == "__main__":
    run()
