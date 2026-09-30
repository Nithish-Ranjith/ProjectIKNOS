"""
train_boundary_model.py — Full PyTorch Training Loop for Multi-Task ResUNet-a.

Trains the 3-head parcel boundary detector on synthetic (or real) drone tiles.

Usage:
    # Quick synthetic training (200 tiles, 20 epochs — runs in ~10 min on CPU)
    python train_boundary_model.py --generate-data --n-tiles 200 --epochs 20

    # Train on existing data
    python train_boundary_model.py --data-dir data/training --epochs 50

    # Fine-tune from a checkpoint
    python train_boundary_model.py --data-dir data/training --resume models/weights/resunet_boundary_detector.pth

Outputs:
    models/weights/resunet_boundary_detector.pth  — best validation checkpoint
    models/weights/training_log.json              — epoch-by-epoch loss history
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader, random_split
    from torchvision import transforms
    _TORCH = True
except ImportError:
    _TORCH = False
    print("ERROR: PyTorch not installed. Run: pip install torch torchvision")
    sys.exit(1)

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

# Project paths
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class ParcelBoundaryDataset(Dataset):
    """
    Loads tiles + 3 ground-truth masks.
    Expected layout:
        data_dir/tiles/         TILE_ID.png  (or .npy)
        data_dir/masks_extent/  TILE_ID.png
        data_dir/masks_boundary/TILE_ID.png
        data_dir/masks_distance/TILE_ID.npy  (float32)
    """

    def __init__(self, data_dir: str | Path, augment: bool = True):
        self.data_dir = Path(data_dir)
        self.augment  = augment

        # Find all tile IDs
        tiles_dir = self.data_dir / "tiles"
        self.tile_ids = sorted([
            p.stem for p in tiles_dir.iterdir()
            if p.suffix in (".png", ".jpg", ".npy")
        ])

        if not self.tile_ids:
            raise FileNotFoundError(
                f"No tiles found in {tiles_dir}. "
                "Run generate_synthetic_drone_data.py first."
            )

        self.to_tensor = transforms.ToTensor()
        self.normalize = transforms.Normalize(
            mean=[0.485, 0.456, 0.406],  # ImageNet stats (ResNet pretrain expects this)
            std=[0.229, 0.224, 0.225]
        )

    def __len__(self) -> int:
        return len(self.tile_ids)

    def _load_image(self, path: Path) -> np.ndarray:
        """Load PNG or NPY, return (H, W, C) uint8 or float."""
        if path.suffix == ".npy":
            return np.load(path)
        if _PIL and path.exists():
            return np.array(Image.open(path).convert("RGB"))
        raise FileNotFoundError(f"Cannot load: {path}")

    def _load_mask(self, path_png: Path, path_npy: Path) -> np.ndarray:
        """Load mask as float32 in [0, 1]."""
        if path_npy.exists():
            return np.load(path_npy).astype(np.float32)
        if path_png.exists() and _PIL:
            arr = np.array(Image.open(path_png).convert("L")).astype(np.float32)
            return arr / 255.0
        return np.zeros((512, 512), dtype=np.float32)

    def __getitem__(self, idx: int) -> tuple:
        tid = self.tile_ids[idx]

        # Load RGB tile
        rgb_png = self.data_dir / "tiles" / f"{tid}.png"
        rgb_npy = self.data_dir / "tiles" / f"{tid}.npy"

        if rgb_png.exists():
            rgb = np.array(Image.open(rgb_png).convert("RGB"))
        elif rgb_npy.exists():
            rgb = np.load(rgb_npy)
        else:
            rgb = np.zeros((512, 512, 3), dtype=np.uint8)

        # Load ground truth masks
        ext  = self._load_mask(
            self.data_dir / "masks_extent"   / f"{tid}.png",
            self.data_dir / "masks_extent"   / f"{tid}.npy",
        )
        bnd  = self._load_mask(
            self.data_dir / "masks_boundary" / f"{tid}.png",
            self.data_dir / "masks_boundary" / f"{tid}.npy",
        )
        dist = self._load_mask(
            self.data_dir / "masks_distance" / f"{tid}.png",
            self.data_dir / "masks_distance" / f"{tid}.npy",
        )

        # Augmentation (random flip + rotation for real tiles)
        if self.augment:
            if np.random.random() > 0.5:
                rgb  = np.fliplr(rgb).copy()
                ext  = np.fliplr(ext).copy()
                bnd  = np.fliplr(bnd).copy()
                dist = np.fliplr(dist).copy()
            if np.random.random() > 0.5:
                rgb  = np.flipud(rgb).copy()
                ext  = np.flipud(ext).copy()
                bnd  = np.flipud(bnd).copy()
                dist = np.flipud(dist).copy()
            k = np.random.randint(0, 4)
            if k > 0:
                rgb  = np.rot90(rgb,  k).copy()
                ext  = np.rot90(ext,  k).copy()
                bnd  = np.rot90(bnd,  k).copy()
                dist = np.rot90(dist, k).copy()

        # To tensor
        rgb_t  = self.normalize(self.to_tensor(rgb.astype(np.uint8)))  # (3, H, W) float32
        ext_t  = torch.from_numpy(ext).unsqueeze(0)   # (1, H, W)
        bnd_t  = torch.from_numpy(bnd).unsqueeze(0)
        dist_t = torch.from_numpy(dist).unsqueeze(0)

        # Compute centroid from the extent mask and generate the 4th channel heatmap
        # This solves the 'random shapes' issue by conditioning the model on the exact parcel!
        try:
            import scipy.ndimage
            cy, cx = scipy.ndimage.center_of_mass(ext)
            if np.isnan(cy) or np.isnan(cx):
                cy, cx = 256.0, 256.0
            elif self.augment:
                # Fix WS-3 Centroid Skew: add noise to simulate inference with erroneous cadastral centroids
                cy += np.random.normal(0, 15.0)
                cx += np.random.normal(0, 15.0)
                cy = np.clip(cy, 0, 511)
                cx = np.clip(cx, 0, 511)
        except Exception:
            cy, cx = 256.0, 256.0

        y, x = np.mgrid[0:512, 0:512]
        sigma = 30.0  # matches model config
        heatmap = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2)).astype(np.float32)
        heatmap_t = torch.from_numpy(heatmap).unsqueeze(0)  # (1, 512, 512)

        # Combine RGB (3 channels) + Heatmap (1 channel) = 4 channels
        input_tensor = torch.cat([rgb_t, heatmap_t], dim=0)

        return input_tensor, {"extent": ext_t, "boundary": bnd_t, "distance": dist_t}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train(
    data_dir:   str  = "data/training",
    epochs:     int  = 30,
    batch_size: int  = 4,
    lr:         float = 1e-4,
    resume:     str | None = None,
    device_str: str  = "auto",
) -> None:
    """Full training loop."""
    from models.architectures.resunet_a import MultiTaskResUNet, MultiTaskLoss

    # Device
    if device_str == "auto":
        if torch.backends.mps.is_available():
            device = torch.device("mps")
        elif torch.cuda.is_available():
            device = torch.device("cuda")
        else:
            device = torch.device("cpu")
    else:
        device = torch.device(device_str)
    print(f"[Train] Device: {device}")

    # Dataset
    full_ds = ParcelBoundaryDataset(data_dir, augment=True)
    
    # Fix WS-3 Split Leakage: Group-based split (by village/region) instead of random_split
    groups = {}
    for i, tid in enumerate(full_ds.tile_ids):
        if tid.startswith("SYNTH_"):
            group_id = int(tid.split("_")[1]) // 20
        else:
            parts = tid.split("-")
            group_id = parts[3] if len(parts) > 3 else "unknown"
        groups.setdefault(group_id, []).append(i)
        
    group_keys = list(groups.keys())
    np.random.shuffle(group_keys)
    
    train_indices, val_indices = [], []
    val_target = max(1, int(0.15 * len(full_ds)))
    
    for g in group_keys:
        if len(val_indices) < val_target:
            val_indices.extend(groups[g])
        else:
            train_indices.extend(groups[g])
            
    if not val_indices and group_keys:
        val_indices.extend(groups[group_keys[0]])
        train_indices = [idx for idx in train_indices if idx not in val_indices]
        
    train_ds = torch.utils.data.Subset(full_ds, train_indices)
    val_ds = torch.utils.data.Subset(full_ds, val_indices)
    
    import copy
    val_ds.dataset = copy.deepcopy(full_ds)
    val_ds.dataset.augment = False  # no augmentation for validation

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=0)

    print(f"[Train] {len(train_indices)} train / {len(val_indices)} val tiles")

    # Model + optimizer + loss
    model = MultiTaskResUNet(in_channels=4).to(device)
    if resume:
        state = torch.load(resume, map_location=device)
        model.load_state_dict(state, strict=False)
        print(f"[Train] Resumed from {resume}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    criterion = MultiTaskLoss(w_extent=0.3, w_boundary=0.5, w_distance=0.2, boundary_pos_weight=10.0)

    # Output dirs
    weights_dir = ROOT / "models" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    best_path   = weights_dir / "resunet_boundary_detector.pth"
    log_path    = weights_dir / "training_log.json"

    best_val_loss = float("inf")
    log_history   = []

    for epoch in range(1, epochs + 1):
        # --- Train ---
        model.train()
        train_losses = []
        t0 = time.time()

        for rgb, targets in train_loader:
            rgb = rgb.to(device)
            targets = {k: v.to(device) for k, v in targets.items()}

            optimizer.zero_grad()
            preds = model(rgb)
            loss, loss_dict = criterion(preds, targets)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_losses.append(loss_dict["loss_total"])

        scheduler.step()

        # --- Validate ---
        model.eval()
        val_losses = []
        with torch.no_grad():
            for rgb, targets in val_loader:
                rgb = rgb.to(device)
                targets = {k: v.to(device) for k, v in targets.items()}
                preds = model(rgb)
                _, loss_dict = criterion(preds, targets)
                val_losses.append(loss_dict["loss_total"])

        train_loss = np.mean(train_losses)
        val_loss   = np.mean(val_losses)
        elapsed    = time.time() - t0

        log_entry = {
            "epoch": epoch, "train_loss": round(float(train_loss), 5),
            "val_loss": round(float(val_loss), 5), "time_s": round(elapsed, 1),
            "lr": optimizer.param_groups[0]["lr"]
        }
        log_history.append(log_entry)

        print(f"Epoch {epoch:03d}/{epochs} | Train: {train_loss:.4f} | Val: {val_loss:.4f} | "
              f"LR: {log_entry['lr']:.2e} | {elapsed:.1f}s")

        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), best_path)
            print(f"  ✅ New best model saved → {best_path}")

        # Save log
        with open(log_path, "w") as f:
            json.dump(log_history, f, indent=2)

    print(f"\n[Train] Complete. Best val loss: {best_val_loss:.4f}")
    print(f"[Train] Weights: {best_path}")
    print(f"[Train] Log:     {log_path}")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Multi-Task ResUNet-a for parcel boundary detection")
    parser.add_argument("--data-dir",       default="data/training",  help="Training data directory")
    parser.add_argument("--epochs",         type=int,   default=30,   help="Number of training epochs")
    parser.add_argument("--batch-size",     type=int,   default=4,    help="Batch size")
    parser.add_argument("--lr",             type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--resume",         default=None,             help="Resume from checkpoint path")
    parser.add_argument("--device",         default="auto",           help="cpu | cuda | mps | auto")
    parser.add_argument("--generate-data",  action="store_true",      help="Generate synthetic data first")
    parser.add_argument("--n-tiles",        type=int,   default=200,  help="Tiles to generate (if --generate-data)")

    args = parser.parse_args()

    if args.generate_data:
        print("[Pre-step] Generating synthetic training data...")
        from generate_synthetic_drone_data import generate_dataset
        generate_dataset(n_tiles=args.n_tiles, out_dir=args.data_dir)

    train(
        data_dir=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        resume=args.resume,
        device_str=args.device,
    )
