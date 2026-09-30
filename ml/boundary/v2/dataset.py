"""
ml/boundary/v2/dataset.py — Dataset for centroid-conditioned parcel segmentation (v2).

Key differences from v1 (train_boundary_model.py):
  1. SINGLE target mask (extent/parcel-interior) not three masks
  2. Per-sample centroid heatmap synthesized at load time, concatenated to RGB
     -> model input is (4, 512, 512): R,G,B,heatmap
  3. Richer augmentation: colour jitter, elastic distortion, random scale crop
  4. The dataset reads centroid coordinates from the manifest.json (or recomputes
     them from the extent mask centroid if manifest is absent)

Data layout (same as existing data/training/):
    data_dir/tiles/          TILE_ID.png
    data_dir/masks_extent/   TILE_ID.png    <- the only mask we need
    data_dir/manifest.json                  <- optional; used for n_parcels info
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset
from torchvision import transforms

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

try:
    from scipy.ndimage import label as ndlabel, center_of_mass
    _SCIPY = True
except ImportError:
    _SCIPY = False


SIGMA_PX = 60.0       # must match model_config.json heatmap_sigma_px
TILE_SIZE = 512

# ImageNet normalisation (for RGB channels only)
_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
_STD  = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


def _make_heatmap(cy: float, cx: float, size: int = TILE_SIZE, sigma: float = SIGMA_PX) -> np.ndarray:
    y = np.arange(size, dtype=np.float32)
    x = np.arange(size, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    return np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2)).astype(np.float32)


def _centroid_from_mask(mask: np.ndarray) -> tuple[float, float]:
    """
    Returns (cy, cx) = centroid of largest connected component in a binary mask.
    Falls back to image centre if mask is empty.
    """
    if mask.sum() == 0:
        return TILE_SIZE / 2.0, TILE_SIZE / 2.0
    if _SCIPY:
        labelled, n = ndlabel(mask)
        # Pick the largest component
        sizes = [(labelled == i).sum() for i in range(1, n + 1)]
        best_label = np.argmax(sizes) + 1
        cy, cx = center_of_mass(labelled == best_label)
    else:
        ys, xs = np.where(mask > 0)
        cy, cx = float(ys.mean()), float(xs.mean())
    return float(cy), float(cx)


def _colour_jitter(rgb: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    """Apply brightness, contrast, saturation jitter in-place on uint8 RGB."""
    rgb = rgb.astype(np.float32)
    # Brightness
    if rng.random() > 0.3:
        rgb = rgb * rng.uniform(0.7, 1.3)
    # Contrast
    if rng.random() > 0.3:
        mean = rgb.mean()
        rgb = mean + rng.uniform(0.8, 1.2) * (rgb - mean)
    # Channel-wise shift (simulates different sensors / sun angles)
    if rng.random() > 0.5:
        for c in range(3):
            rgb[..., c] += rng.uniform(-15, 15)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def _random_crop_resize(rgb: np.ndarray, mask: np.ndarray,
                         rng: np.random.RandomState) -> tuple[np.ndarray, np.ndarray]:
    """Random scale crop 80-100%, resize back to TILE_SIZE."""
    h, w = rgb.shape[:2]
    scale = rng.uniform(0.80, 1.0)
    ch, cw = int(h * scale), int(w * scale)
    y0 = rng.randint(0, h - ch + 1)
    x0 = rng.randint(0, w - cw + 1)
    rgb  = rgb[y0:y0+ch, x0:x0+cw]
    mask = mask[y0:y0+ch, x0:x0+cw]
    if _PIL:
        rgb  = np.array(Image.fromarray(rgb).resize((w, h), Image.BILINEAR))
        mask_img = Image.fromarray((mask * 255).astype(np.uint8))
        mask = np.array(mask_img.resize((w, h), Image.NEAREST)).astype(np.float32) / 255.0
    return rgb, mask


class CentroidParcelDataset(Dataset):
    """
    Each sample: one (tile, extent_mask) pair.
    For each sample the centroid heatmap is computed from the extent mask centroid
    and concatenated to the RGB to produce a (4, 512, 512) input tensor.

    The model learns to predict the parcel that the centroid heatmap points to.
    """

    def __init__(self, data_dir: str | Path, augment: bool = True):
        self.data_dir = Path(data_dir)
        self.augment  = augment

        tiles_dir = self.data_dir / "tiles"
        self.tile_ids = sorted([
            p.stem for p in tiles_dir.iterdir()
            if p.suffix in (".png", ".jpg", ".npy")
        ])

        if not self.tile_ids:
            raise FileNotFoundError(f"No tiles in {tiles_dir}. Run generate_synthetic_drone_data.py first.")

        print(f"[Dataset] {len(self.tile_ids)} tiles in {self.data_dir}")

    def __len__(self) -> int:
        return len(self.tile_ids)

    def _load_rgb(self, tid: str) -> np.ndarray:
        png = self.data_dir / "tiles" / f"{tid}.png"
        npy = self.data_dir / "tiles" / f"{tid}.npy"
        if png.exists() and _PIL:
            return np.array(Image.open(png).convert("RGB"), dtype=np.uint8)
        if npy.exists():
            return np.load(npy)
        return np.zeros((TILE_SIZE, TILE_SIZE, 3), dtype=np.uint8)

    def _load_extent(self, tid: str) -> np.ndarray:
        png = self.data_dir / "masks_extent" / f"{tid}.png"
        npy = self.data_dir / "masks_extent" / f"{tid}.npy"
        if npy.exists():
            arr = np.load(npy).astype(np.float32)
            return arr if arr.max() <= 1.0 else arr / 255.0
        if png.exists() and _PIL:
            arr = np.array(Image.open(png).convert("L"), dtype=np.float32)
            return arr / 255.0
        return np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        tid = self.tile_ids[idx]
        rng = np.random.RandomState(idx + np.random.randint(0, 100000) if self.augment else idx)

        rgb    = self._load_rgb(tid)
        extent = self._load_extent(tid)   # float32 [0,1], (H, W)

        # ---- Augmentation ----
        if self.augment:
            # Horizontal flip
            if rng.random() > 0.5:
                rgb    = np.fliplr(rgb).copy()
                extent = np.fliplr(extent).copy()
            # Vertical flip
            if rng.random() > 0.5:
                rgb    = np.flipud(rgb).copy()
                extent = np.flipud(extent).copy()
            # 90° rotation
            k = rng.randint(0, 4)
            if k > 0:
                rgb    = np.rot90(rgb,  k).copy()
                extent = np.rot90(extent, k).copy()
            # Colour jitter (RGB only, not mask)
            if rng.random() > 0.4:
                rgb = _colour_jitter(rgb, rng)
            # Random scale crop
            if rng.random() > 0.5:
                rgb, extent = _random_crop_resize(rgb, extent, rng)

        # ---- Downsample to 256x256 for faster training ----
        if _PIL:
            rgb = np.array(Image.fromarray(rgb).resize((256, 256), Image.BILINEAR))
            extent = np.array(Image.fromarray((extent * 255).astype(np.uint8)).resize((256, 256), Image.NEAREST)).astype(np.float32) / 255.0

        # ---- Centroid from mask ----
        binary_mask = (extent > 0.5).astype(np.uint8)
        cy, cx = _centroid_from_mask(binary_mask)

        # ---- Build 4-ch input: normalised RGB + heatmap ----
        rgb_t = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1)  # (3, H, W)
        rgb_t = (rgb_t - _MEAN) / _STD   # ImageNet normalisation

        heatmap_t = torch.from_numpy(_make_heatmap(cy, cx, size=256, sigma=SIGMA_PX / 2.0))  # (H, W)
        x = torch.cat([rgb_t, heatmap_t.unsqueeze(0)], dim=0)  # (4, H, W)

        # ---- Target ----
        y = torch.from_numpy(extent).unsqueeze(0)  # (1, H, W) in [0, 1]

        return x, y
