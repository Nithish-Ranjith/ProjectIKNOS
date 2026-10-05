"""
ml/boundary/v2/train_real.py — Corrected training on REAL APSAC parcel data.

Fixes vs the broken train.py:
  1. Points to real data at data_extracted/iknos_dataset_1000 2/dataset/
  2. Input size is 512×512 (matches model_config.json + inference — was wrongly downsampled to 256)
  3. Sigma is 60 (matches model_config.json — was wrong at 30 in dataset.py)
  4. Positive class weight set to ~15 (real data has 2-22% positive px, not 70%)
  5. Early stopping on val_IoU patience=8 to prevent the val_IoU=0.9993 overfit
  6. Dropout=0.3 on decoder to regularize on 1,000-sample dataset
  7. Exports best checkpoint to ONNX automatically for backend use

Usage:
    # Fine-tune from existing checkpoint (recommended — best starting point):
    python -m ml.boundary.v2.train_real --resume models/weights/v2_best_model.pth --epochs 60

    # Scratch:
    python -m ml.boundary.v2.train_real --no-resume --epochs 60
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent.parent.parent  # ProjectIKNOS/
sys.path.insert(0, str(ROOT))

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset, random_split
    from torchvision import transforms
    from PIL import Image
except ImportError:
    print("ERROR: pip install torch torchvision Pillow")
    sys.exit(1)

from ml.boundary.v2.model import CentroidConditionedUNet, FocalDiceLoss, compute_iou

# ---------------------------------------------------------------------------
# Constants — all must match v2_model_config.json and inference.py
# ---------------------------------------------------------------------------
TILE_SIZE  = 512          # Do NOT downsample. Model is 512x512.
SIGMA_PX   = 60.0         # MUST match model_config.json heatmap_sigma_px = 60
_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
_STD  = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


# ---------------------------------------------------------------------------
# Dataset for REAL data (images/ + masks/)
# ---------------------------------------------------------------------------
class RealParcelDataset(Dataset):
    """
    Reads from data_extracted/iknos_dataset_1000 2/dataset/:
      images/   — AP-07-*.png  (512×512 RGB satellite tiles)
      masks/    — AP-07-*.png  (512×512 grayscale, 0=background, 255=parcel)

    Centroid heatmap is synthesized from the mask's centroid at load time.
    This is correct: at inference, the centroid comes from the known cadastral
    coords reprojected into tile pixel space (same information source).
    """

    def __init__(self, data_dir: str | Path, augment: bool = True):
        self.data_dir = Path(data_dir)
        self.img_dir  = self.data_dir / "images"
        self.mask_dir = self.data_dir / "masks"
        self.augment  = augment

        self.ids = sorted([
            p.stem for p in self.img_dir.iterdir()
            if p.suffix in (".png", ".jpg")
        ])
        if not self.ids:
            raise FileNotFoundError(f"No images in {self.img_dir}")
        print(f"[RealDataset] {len(self.ids)} tiles from {self.data_dir}")

    def __len__(self) -> int:
        return len(self.ids)

    def _make_heatmap(self, cy: float, cx: float) -> torch.Tensor:
        """Gaussian heatmap with sigma=60px — matches model_config.json."""
        y = torch.arange(TILE_SIZE, dtype=torch.float32)
        x = torch.arange(TILE_SIZE, dtype=torch.float32)
        yy, xx = torch.meshgrid(y, x, indexing="ij")
        heatmap = torch.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * SIGMA_PX ** 2))
        return heatmap.unsqueeze(0)  # (1, H, W)

    def _centroid(self, mask_np: np.ndarray) -> tuple[float, float]:
        ys, xs = np.where(mask_np > 0)
        if len(ys) == 0:
            return TILE_SIZE / 2.0, TILE_SIZE / 2.0
        return float(ys.mean()), float(xs.mean())

    def __getitem__(self, idx: int):
        name = self.ids[idx]
        img  = np.array(Image.open(self.img_dir  / f"{name}.png").convert("RGB"), dtype=np.uint8)
        mask = np.array(Image.open(self.mask_dir / f"{name}.png").convert("L"),   dtype=np.uint8)

        # ---- Augmentation ----
        if self.augment:
            rng = np.random.default_rng(seed=idx + np.random.randint(0, 1_000_000))
            # Horizontal flip
            if rng.random() > 0.5:
                img  = np.fliplr(img).copy()
                mask = np.fliplr(mask).copy()
            # Vertical flip
            if rng.random() > 0.5:
                img  = np.flipud(img).copy()
                mask = np.flipud(mask).copy()
            # 90° rotation
            k = rng.integers(0, 4)
            if k > 0:
                img  = np.rot90(img,  k).copy()
                mask = np.rot90(mask, k).copy()
            # Colour jitter (RGB only)
            if rng.random() > 0.4:
                img = img.astype(np.float32)
                img *= rng.uniform(0.75, 1.25)                      # brightness
                mean = img.mean()
                img  = mean + rng.uniform(0.85, 1.15) * (img - mean)  # contrast
                img  = np.clip(img, 0, 255).astype(np.uint8)
            # Random scale crop 85-100%
            if rng.random() > 0.5:
                scale  = rng.uniform(0.85, 1.0)
                ch, cw = int(TILE_SIZE * scale), int(TILE_SIZE * scale)
                y0 = rng.integers(0, TILE_SIZE - ch + 1)
                x0 = rng.integers(0, TILE_SIZE - cw + 1)
                img_crop  = img[y0:y0+ch, x0:x0+cw]
                mask_crop = mask[y0:y0+ch, x0:x0+cw]
                img  = np.array(Image.fromarray(img_crop).resize((TILE_SIZE, TILE_SIZE), Image.BILINEAR))
                mask = np.array(Image.fromarray(mask_crop).resize((TILE_SIZE, TILE_SIZE), Image.NEAREST))

        # ---- Build 4-ch input ----
        mask_float = (mask > 127).astype(np.float32)   # binary [0, 1]
        cy, cx = self._centroid(mask_float)

        rgb_t = torch.from_numpy(img.astype(np.float32) / 255.0).permute(2, 0, 1)
        rgb_t = (rgb_t - _MEAN) / _STD                            # ImageNet normalisation
        hmap  = self._make_heatmap(cy, cx)                        # (1, 512, 512)
        x = torch.cat([rgb_t, hmap], dim=0)                       # (4, 512, 512)
        y = torch.from_numpy(mask_float).unsqueeze(0)             # (1, 512, 512)

        return x, y


# ---------------------------------------------------------------------------
class EarlyStopping:
    def __init__(self, patience: int = 8, min_delta: float = 0.001):
        self.patience   = patience
        self.min_delta  = min_delta
        self.best       = 0.0
        self.wait       = 0

    def step(self, val_iou: float) -> bool:
        """Returns True if training should stop."""
        if val_iou > self.best + self.min_delta:
            self.best = val_iou
            self.wait = 0
        else:
            self.wait += 1
        return self.wait >= self.patience


# ---------------------------------------------------------------------------
def train(
    data_dir:   str   = "data_extracted/iknos_dataset_1000 2/dataset",
    epochs:     int   = 60,
    batch_size: int   = 2,     # 512×512 tiles are big; use 2-4 depending on RAM
    lr:         float = 1e-4,  # lower than before — fine-tuning pretrained weights
    encoder_lr_factor: float = 0.05,
    resume:     str | None = "models/weights/v2_best_model.pth",
    device_str: str   = "auto",
    export_onnx: bool = True,
) -> None:

    # ---- Device ----
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

    # ---- Data ----
    full_ds = RealParcelDataset(data_dir, augment=True)
    n_total  = len(full_ds)
    val_size = max(2, int(0.15 * n_total))    # ~150 for 1000 samples
    trn_size = n_total - val_size
    trn_ds, val_ds = random_split(full_ds, [trn_size, val_size],
                                  generator=torch.Generator().manual_seed(42))
    val_ds.dataset.augment = False

    trn_loader = DataLoader(trn_ds, batch_size=batch_size, shuffle=True,  num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
    print(f"[Train] {trn_size} train / {val_size} val tiles  |  batch={batch_size}  |  tile_size={TILE_SIZE}")

    # ---- Estimate positive pixel ratio for loss weighting ----
    # Real data is 2-22% positive. Sample 20 training items.
    pos_ratios = []
    for i in range(min(20, trn_size)):
        _, y = full_ds[i]
        pos_ratios.append(y.mean().item())
    mean_pos = float(np.mean(pos_ratios))
    # pos_weight = (1 - mean_pos) / mean_pos  drives BCE; we pass it to FocalDiceLoss indirectly
    print(f"[Train] Mean positive pixel ratio: {mean_pos:.3f} ({mean_pos*100:.1f}%)")
    # For Focal alpha: higher = more weight on positives. Real data needs ~0.90-0.95.
    focal_alpha = max(0.75, 1.0 - mean_pos)
    print(f"[Train] Focal alpha set to: {focal_alpha:.3f}")

    # ---- Model ----
    model = CentroidConditionedUNet().to(device)

    if resume and Path(resume).exists():
        state = torch.load(resume, map_location=device, weights_only=False)
        missing, unexpected = model._net.load_state_dict(state, strict=False)
        n_loaded = len(state) - len(unexpected)
        print(f"[Train] Resumed from {resume}  ({n_loaded}/{len(state)} keys loaded)")
        if missing:
            print(f"  Missing ({len(missing)}): {missing[:3]} ...")
    else:
        print("[Train] Training from ImageNet-pretrained EfficientNet-B3")

    # ---- Differential LRs ----
    encoder_params = list(model._net.encoder.parameters())
    other_params   = [p for p in model.parameters()
                      if not any(p is ep for ep in encoder_params)]
    optimizer = torch.optim.AdamW([
        {"params": encoder_params, "lr": lr * encoder_lr_factor},
        {"params": other_params,   "lr": lr},
    ], weight_decay=5e-4)

    # Cosine annealing: decays LR smoothly over all epochs — no premature plateau
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-7)

    criterion   = FocalDiceLoss(alpha=focal_alpha, gamma=2.0, dice_weight=0.6, focal_weight=0.4)
    stopper     = EarlyStopping(patience=8, min_delta=0.002)

    # ---- Paths ----
    weights_dir = ROOT / "models" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    best_path   = weights_dir / "v2_real_best.pth"
    log_path    = weights_dir / "v2_real_training_log.json"
    onnx_path   = weights_dir / "v2_real_model.onnx"

    best_val_iou = 0.0
    log_history  = []

    for epoch in range(1, epochs + 1):
        t0 = time.time()

        # Train
        model.train()
        trn_losses, trn_ious = [], []
        for x, y in trn_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(x)
            loss, parts = criterion(logits, y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            trn_losses.append(loss.item())
            trn_ious.append(compute_iou(logits.detach(), y))

        # Validate
        model.eval()
        val_losses, val_ious = [], []
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                logits = model(x)
                loss, _ = criterion(logits, y)
                val_losses.append(loss.item())
                val_ious.append(compute_iou(logits, y))

        trn_loss = float(np.mean(trn_losses))
        val_loss = float(np.mean(val_losses))
        val_iou  = float(np.mean(val_ious))
        trn_iou  = float(np.mean(trn_ious))
        elapsed  = time.time() - t0
        cur_lr   = optimizer.param_groups[1]["lr"]

        scheduler.step()

        entry = {
            "epoch": epoch, "train_loss": round(trn_loss, 4),
            "train_IoU": round(trn_iou, 4), "val_loss": round(val_loss, 4),
            "val_IoU": round(val_iou, 4), "lr": round(cur_lr, 8),
            "time_s": round(elapsed, 1),
        }
        log_history.append(entry)
        print(f"Epoch {epoch:02d}/{epochs} | trn_loss {trn_loss:.4f} trn_IoU {trn_iou:.4f} | "
              f"val_loss {val_loss:.4f} val_IoU {val_iou:.4f} | lr={cur_lr:.2e} | {elapsed:.1f}s")

        if val_iou > best_val_iou:
            best_val_iou = val_iou
            torch.save(model._net.state_dict(), best_path)
            print(f"  -> new best model saved (val IoU {val_iou:.4f})")

        with open(log_path, "w") as f:
            json.dump(log_history, f, indent=2)

        if stopper.step(val_iou):
            print(f"[EarlyStopping] No improvement for {stopper.patience} epochs. Stopping.")
            break

    print(f"\nTraining done. Best val IoU: {best_val_iou:.4f}")
    print(f"Weights: {best_path}")

    # ---- Export ONNX for backend use ----
    if export_onnx:
        print(f"\nExporting ONNX to {onnx_path}...")
        model._net.load_state_dict(torch.load(best_path, map_location="cpu", weights_only=False), strict=False)
        model.eval().cpu()
        dummy = torch.randn(1, 4, TILE_SIZE, TILE_SIZE)
        torch.onnx.export(
            model, dummy, str(onnx_path),
            input_names=["input"], output_names=["logits"],
            dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
            opset_version=17,
        )
        print(f"ONNX exported. Use onnxruntime in backend: session.run(None, {{'input': inp}})[0]")

        # Also update model_config.json to reflect real data training
        config = {
            "encoder": "efficientnet-b3",
            "input_size": TILE_SIZE,
            "in_channels": 4,
            "channel_layout": "RGB (channels 0-2) + centroid Gaussian heatmap (channel 3)",
            "heatmap_sigma_px": int(SIGMA_PX),
            "normalize_mean": [0.485, 0.456, 0.406],
            "normalize_std":  [0.229, 0.224, 0.225],
            "threshold": 0.5,
            "output": "single-channel logits; apply sigmoid + threshold at 0.5; use cv2.morphologyEx(MORPH_GRADIENT) to extract boundary line",
            "centroid_source_at_inference": "known cadastral centroid of the target parcel reprojected into tile pixel coordinates",
            "best_val_iou": best_val_iou,
            "training_data": "real APSAC Guntur cadastral parcels (1000 tiles, 512x512)",
            "onnx_path": str(onnx_path),
        }
        config_path = weights_dir / "v2_real_model_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Config saved: {config_path}")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir",   default="data_extracted/iknos_dataset_1000 2/dataset")
    parser.add_argument("--epochs",     type=int,   default=60)
    parser.add_argument("--batch-size", type=int,   default=2)
    parser.add_argument("--lr",         type=float, default=1e-4)
    parser.add_argument("--resume",     default="models/weights/v2_best_model.pth")
    parser.add_argument("--no-resume",  action="store_true")
    parser.add_argument("--device",     default="auto")
    parser.add_argument("--no-onnx",    action="store_true")
    args = parser.parse_args()

    train(
        data_dir=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        resume=None if args.no_resume else args.resume,
        device_str=args.device,
        export_onnx=not args.no_onnx,
    )
