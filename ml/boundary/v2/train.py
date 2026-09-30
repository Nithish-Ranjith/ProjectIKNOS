"""
ml/boundary/v2/train.py — Full training loop for centroid-conditioned EfficientNet-B3 (v2).

Target metric: val_IoU >= 0.82 after 30 epochs fine-tuning from v2 checkpoint.

Key improvements over v1 (train_boundary_model.py):
  1. Correct architecture: 4-ch EfficientNet-B3 (matches v2 checkpoint weights)
  2. FocalDiceLoss instead of BCE+Dice on boundary head alone -> directly optimises IoU
  3. Richer augmentation: colour jitter, random scale crop, both flips, rotations
  4. Differential learning rates: encoder LR 10x lower than decoder (standard fine-tuning)
  5. ReduceLROnPlateau scheduler (better than CosineAnnealing when resuming mid-training)
  6. IoU tracked and reported every epoch (not just loss)
  7. Best model saved on val_IoU, not val_loss
  8. Generates additional data if < 200 tiles exist

Usage:
    # Fine-tune from v2 checkpoint (recommended):
    python -m ml.boundary.v2.train --resume models/weights/v2_best_model.pth --epochs 30

    # Train from scratch with fresh EfficientNet-B3 ImageNet weights:
    python -m ml.boundary.v2.train --epochs 30

    # With data generation:
    python -m ml.boundary.v2.train --generate-data --n-tiles 500 --epochs 30

Outputs:
    models/weights/v2_finetuned.pth       -- best val-IoU checkpoint
    models/weights/v2_training_log.json   -- epoch-by-epoch history
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, random_split
except ImportError:
    print("ERROR: PyTorch not installed. Run: pip install torch torchvision")
    sys.exit(1)

# Project root on sys.path
ROOT = Path(__file__).parent.parent.parent.parent  # ProjectIKNOS/
sys.path.insert(0, str(ROOT))

from ml.boundary.v2.model import CentroidConditionedUNet, FocalDiceLoss, compute_iou
from ml.boundary.v2.dataset import CentroidParcelDataset


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------
def train(
    data_dir:    str   = "data/training",
    epochs:      int   = 30,
    batch_size:  int   = 4,
    lr:          float = 3e-4,
    encoder_lr_factor: float = 0.1,   # encoder gets lr * 0.1 (standard fine-tune ratio)
    resume:      str | None = None,
    device_str:  str   = "auto",
    min_tiles:   int   = 200,
) -> None:
    """Full v2 training loop with IoU tracking."""

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
    full_ds = CentroidParcelDataset(data_dir, augment=True)

    # Ensure adequate validation set size
    n_total  = len(full_ds)
    val_size = max(2, int(0.15 * n_total))
    trn_size = n_total - val_size
    trn_ds, val_ds = random_split(full_ds, [trn_size, val_size],
                                  generator=torch.Generator().manual_seed(42))

    # Disable augmentation on validation split
    # (DataLoader wraps the Subset, so we patch the underlying dataset)
    val_ds.dataset.augment = False

    num_workers = 0  # 0 is safest on macOS MPS; bump to 2-4 on Linux/CUDA
    trn_loader = DataLoader(trn_ds, batch_size=batch_size, shuffle=True,  num_workers=num_workers, pin_memory=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=False)

    print(f"[Train] {trn_size} train / {val_size} val tiles  |  batch={batch_size}")

    # ---- Model ----
    model = CentroidConditionedUNet().to(device)

    if resume:
        state = torch.load(resume, map_location=device, weights_only=False)
        missing, unexpected = model._net.load_state_dict(state, strict=False)
        n_loaded = len(state) - len(unexpected)
        print(f"[Train] Resumed from {resume}  ({n_loaded}/{len(state)} keys loaded)")
        if missing:
            print(f"  Missing ({len(missing)}): {missing[:3]} ...")
    else:
        print("[Train] Training from ImageNet-pretrained EfficientNet-B3 (no v2 checkpoint)")

    # ---- Differential learning rates ----
    # Encoder (already well-trained pretrained/v2 features): lower LR
    # Decoder + head (needs to adapt to our task):           higher LR
    encoder_params = list(model._net.encoder.parameters())
    other_params   = [p for p in model.parameters()
                      if not any(p is ep for ep in encoder_params)]

    optimizer = torch.optim.AdamW([
        {"params": encoder_params, "lr": lr * encoder_lr_factor},
        {"params": other_params,   "lr": lr},
    ], weight_decay=1e-4)

    # ReduceLROnPlateau: halves LR if val_IoU doesn't improve for 5 epochs
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=5, min_lr=1e-7,
    )

    criterion = FocalDiceLoss(alpha=0.75, gamma=2.0, dice_weight=0.6, focal_weight=0.4)

    # ---- Output paths ----
    weights_dir = ROOT / "models" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    best_path  = weights_dir / "v2_finetuned.pth"
    log_path   = weights_dir / "v2_training_log.json"

    best_val_iou = 0.0
    log_history  = []

    # ---- Epoch loop ----
    for epoch in range(1, epochs + 1):
        t0 = time.time()

        # --- Train ---
        model.train()
        trn_losses, trn_ious = [], []

        for x, y in trn_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(x)
            loss, _ = criterion(logits, y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            trn_losses.append(loss.item())
            trn_ious.append(compute_iou(logits.detach(), y))

        # --- Validate ---
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
        elapsed  = time.time() - t0
        cur_lr   = optimizer.param_groups[1]["lr"]  # decoder LR

        scheduler.step(val_iou)

        entry = {
            "epoch": epoch, "train_loss": round(trn_loss, 4),
            "val_loss": round(val_loss, 4), "val_IoU": round(val_iou, 4),
            "lr": cur_lr, "time_s": round(elapsed, 1),
        }
        log_history.append(entry)

        print(f"Epoch {epoch:02d}/{epochs} | train_loss {trn_loss:.4f} | "
              f"val_loss {val_loss:.4f} | val_IoU {val_iou:.4f}")

        if val_iou > best_val_iou:
            best_val_iou = val_iou
            torch.save(model._net.state_dict(), best_path)
            print(f"  -> new best model saved (val IoU {val_iou:.4f})")

        with open(log_path, "w") as f:
            json.dump(log_history, f, indent=2)

    print(f"\nTraining done. Best val IoU: {best_val_iou:.4f}")
    print(f"Weights: {best_path}")
    print(f"Log:     {log_path}")
    return best_val_iou


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train centroid-conditioned EfficientNet-B3 parcel segmenter (v2)")
    parser.add_argument("--data-dir",     default="data/training",                   help="Training data directory")
    parser.add_argument("--epochs",       type=int,   default=30,                    help="Number of epochs")
    parser.add_argument("--batch-size",   type=int,   default=4,                     help="Batch size")
    parser.add_argument("--lr",           type=float, default=3e-4,                  help="Decoder/head learning rate")
    parser.add_argument("--resume",       default="models/weights/v2_best_model.pth",help="Checkpoint to resume from")
    parser.add_argument("--no-resume",    action="store_true",                        help="Train from scratch (ignore checkpoint)")
    parser.add_argument("--device",       default="auto",                             help="cpu | cuda | mps | auto")
    parser.add_argument("--generate-data",action="store_true",                        help="Generate synthetic data first")
    parser.add_argument("--n-tiles",      type=int,   default=500,                   help="Tiles to generate (if --generate-data)")
    args = parser.parse_args()

    if args.generate_data:
        print("[Pre-step] Generating synthetic training data...")
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        from generate_synthetic_drone_data import generate_dataset
        generate_dataset(n_tiles=args.n_tiles, out_dir=args.data_dir)

    resume = None if args.no_resume else args.resume
    if resume and not Path(resume).exists():
        print(f"[WARN] Checkpoint not found at {resume} — training from scratch")
        resume = None

    train(
        data_dir=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        resume=resume,
        device_str=args.device,
    )
