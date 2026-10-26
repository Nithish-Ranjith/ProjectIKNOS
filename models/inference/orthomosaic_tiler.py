"""
models/inference/orthomosaic_tiler.py — Slice large GeoTIFFs into 512×512 inference tiles.

Design Contracts:
  - Input: georeferenced GeoTIFF (any size) from WebODM output
  - Output: list of (tile_tensor, tile_transform, tile_window) tuples
  - 25% overlap between adjacent tiles — prevents boundary artifacts at tile edges
  - Tiles are padded to 512×512 if the image edge is smaller
  - All coordinates preserved via rasterio Window + Affine transforms
  - Output is CANDIDATE boundary data — not a legal determination

Stitch logic (in boundary_vectorizer.py) reconstructs the full mask by
averaging overlapping tile predictions before vectorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Generator

import numpy as np

try:
    import rasterio
    from rasterio.windows import Window
    _RASTERIO = True
except ImportError:
    _RASTERIO = False

try:
    import torch
    _TORCH = True
except ImportError:
    _TORCH = False


TILE_SIZE = 512
OVERLAP = 128          # 25% overlap
STRIDE   = TILE_SIZE - OVERLAP   # 384


@dataclass
class TileRecord:
    tensor: "torch.Tensor"         # (1, 3, 512, 512) float32 [0,1]
    window: "rasterio.windows.Window"
    transform: object               # rasterio Affine
    row_off: int
    col_off: int
    orig_h: int                     # actual tile height (may be < 512 at edges)
    orig_w: int                     # actual tile width


class OrthomosaicTiler:
    """
    Slices a GeoTIFF into overlapping 512×512 tiles for ResUNet-a inference.
    Preserves full geospatial metadata so predictions can be stitched back.
    """

    def __init__(self, tif_path: str | Path, tile_size: int = TILE_SIZE, overlap: int = OVERLAP):
        if not _RASTERIO:
            raise ImportError("rasterio is required: pip install rasterio")
        if not _TORCH:
            raise ImportError("torch is required: pip install torch")

        self.tif_path  = Path(tif_path)
        self.tile_size = tile_size
        self.overlap   = overlap
        self.stride    = tile_size - overlap

        self._src = rasterio.open(self.tif_path)
        self.height   = self._src.height
        self.width    = self._src.width
        self.crs      = self._src.crs
        self.transform = self._src.transform

    def __del__(self):
        if hasattr(self, "_src") and self._src:
            self._src.close()

    @property
    def n_tiles(self) -> int:
        rows = max(1, (self.height - self.overlap + self.stride - 1) // self.stride)
        cols = max(1, (self.width  - self.overlap + self.stride - 1) // self.stride)
        return rows * cols

    def tiles(self) -> Generator[TileRecord, None, None]:
        """Yield TileRecord objects for each tile."""
        import torch
        from rasterio.windows import Window

        row_off = 0
        while row_off < self.height:
            col_off = 0
            while col_off < self.width:
                # Clamp to image bounds
                real_h = min(self.tile_size, self.height - row_off)
                real_w = min(self.tile_size, self.width  - col_off)

                win = Window(col_off, row_off, real_w, real_h)
                data = self._src.read(window=win)  # (C, H, W) uint8 or float

                # Keep only first 3 channels (RGB)
                if data.shape[0] >= 3:
                    data = data[:3]
                elif data.shape[0] == 1:
                    data = np.repeat(data, 3, axis=0)

                # Normalize to [0, 1]
                if data.dtype == np.uint8:
                    data = data.astype(np.float32) / 255.0
                else:
                    vmin, vmax = data.min(), data.max()
                    data = (data - vmin) / (vmax - vmin + 1e-8)
                    data = data.astype(np.float32)

                # Pad to tile_size × tile_size
                pad_h = self.tile_size - real_h
                pad_w = self.tile_size - real_w
                if pad_h > 0 or pad_w > 0:
                    data = np.pad(data, ((0, 0), (0, pad_h), (0, pad_w)),
                                  mode="reflect")

                tensor = torch.from_numpy(data).unsqueeze(0)  # (1, 3, 512, 512)
                tile_transform = self._src.window_transform(win)

                yield TileRecord(
                    tensor=tensor,
                    window=win,
                    transform=tile_transform,
                    row_off=row_off,
                    col_off=col_off,
                    orig_h=real_h,
                    orig_w=real_w,
                )

                col_off += self.stride
                if col_off >= self.width:
                    break

            row_off += self.stride
            if row_off >= self.height:
                break

    def stitch_masks(self, tile_predictions: list[tuple[TileRecord, np.ndarray]]) -> np.ndarray:
        """
        Reconstruct the full-resolution mask by averaging overlapping predictions.

        Args:
            tile_predictions: list of (TileRecord, mask_array) where
                              mask_array is (tile_size, tile_size) float32 [0,1]
        Returns:
            (height, width) float32 array
        """
        accumulator = np.zeros((self.height, self.width), dtype=np.float32)
        count_map   = np.zeros((self.height, self.width), dtype=np.float32)

        for tile, mask in tile_predictions:
            # Crop prediction back to original (unpadded) tile dimensions
            pred_crop = mask[:tile.orig_h, :tile.orig_w]
            r0, c0 = tile.row_off, tile.col_off
            r1 = min(r0 + tile.orig_h, self.height)
            c1 = min(c0 + tile.orig_w, self.width)

            accumulator[r0:r1, c0:c1] += pred_crop[:r1-r0, :c1-c0]
            count_map  [r0:r1, c0:c1] += 1.0

        count_map = np.maximum(count_map, 1.0)
        return accumulator / count_map


def run_tiled_inference(
    tif_path: str | Path,
    model,
    device: str = "cpu",
    batch_size: int = 4,
) -> dict[str, np.ndarray]:
    """
    Run multi-task ResUNet-a inference over a full orthomosaic GeoTIFF.

    Returns:
        dict with 'extent', 'boundary', 'distance' as (H, W) float32 arrays
    """
    import torch

    tiler = OrthomosaicTiler(tif_path)
    tiles = list(tiler.tiles())

    extent_preds   = []
    boundary_preds = []
    distance_preds = []

    model.eval()
    model.to(device)

    # Process in batches
    for i in range(0, len(tiles), batch_size):
        batch_tiles = tiles[i:i + batch_size]
        batch_tensor = torch.cat([t.tensor for t in batch_tiles], dim=0).to(device)

        with torch.no_grad():
            out = model.predict(batch_tensor)

        for j, tile in enumerate(batch_tiles):
            e = out["extent"][j, 0].cpu().numpy()
            b = out["boundary"][j, 0].cpu().numpy()
            d = out["distance"][j, 0].cpu().numpy()

            extent_preds.append((tile, e))
            boundary_preds.append((tile, b))
            distance_preds.append((tile, d))

    return {
        "extent":    tiler.stitch_masks(extent_preds),
        "boundary":  tiler.stitch_masks(boundary_preds),
        "distance":  tiler.stitch_masks(distance_preds),
        "tiler":     tiler,
    }
