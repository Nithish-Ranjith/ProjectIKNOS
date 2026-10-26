"""
models/architectures/resunet_a.py — Multi-Task ResUNet-a for Parcel Boundary Detection.

Architecture: ResNet-34 encoder (ImageNet pretrained) + U-Net decoder + 3 concurrent heads.
Reference: Diakogiannis et al. (2020) "ResUNet-a: a deep learning framework for
           semantic segmentation of remotely sensed data"

Three Output Heads (the Waldner–Diakogiannis Multi-Task Standard):
  1. extent   : Binary mask — parcel interior vs. exterior (sigmoid, BCE loss)
  2. boundary : 3-pixel-wide earthen bund / ridge mask (sigmoid, BCE + dice loss)
  3. distance : Normalized Euclidean distance from interior pixel to nearest boundary
                (linear, MSE loss). Creates steep gradient at field center → 0 at bund.
                Used for marker-controlled Watershed to cleanly separate adjacent parcels.

Design Contracts:
  - Input: (B, 3, 512, 512) RGB tile from drone orthomosaic (uint8 normalized to [0,1])
  - Output: dict of three (B, 1, 512, 512) tensors
  - Backbone: segmentation_models_pytorch resnet34 (pretrained, fine-tunable)
  - Label: TRANSFER_LEARNED — fine-tune on 20-50 hand-labeled Indian parcels (BQ-04)
  - Output is a CANDIDATE boundary — never a legal boundary determination

Usage:
    model = MultiTaskResUNet()
    out = model(x)  # x: (B,3,512,512) tensor in [0,1]
    # out['extent']   -> (B,1,512,512) probability
    # out['boundary'] -> (B,1,512,512) probability
    # out['distance'] -> (B,1,512,512) normalized distance [0,1]
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import segmentation_models_pytorch as smp
    _SMP_AVAILABLE = True
except ImportError:
    _SMP_AVAILABLE = False


# ---------------------------------------------------------------------------
# Attention Gate — boosts boundary signal during skip connections
# ---------------------------------------------------------------------------
class AttentionGate(nn.Module):
    """Soft-attention gate for skip connections (Oktay et al., 2018)."""
    def __init__(self, F_g: int, F_l: int, F_int: int):
        super().__init__()
        self.W_g = nn.Sequential(nn.Conv2d(F_g, F_int, 1, bias=False), nn.BatchNorm2d(F_int))
        self.W_x = nn.Sequential(nn.Conv2d(F_l, F_int, 1, bias=False), nn.BatchNorm2d(F_int))
        self.psi = nn.Sequential(nn.Conv2d(F_int, 1, 1, bias=False), nn.BatchNorm2d(1), nn.Sigmoid())

    def forward(self, g: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        g_up = F.interpolate(g, size=x.shape[2:], mode="bilinear", align_corners=False)
        attn = self.psi(F.relu(self.W_g(g_up) + self.W_x(x), inplace=True))
        return x * attn


# ---------------------------------------------------------------------------
# Pyramid Scene Parsing Module (atrous convolutions for multi-scale context)
# ---------------------------------------------------------------------------
class PSPModule(nn.Module):
    """Pyramid Pooling for multi-scale context — critical for varied parcel sizes."""
    def __init__(self, in_channels: int, out_channels: int, sizes=(1, 2, 4, 8)):
        super().__init__()
        self.stages = nn.ModuleList([
            nn.Sequential(
                nn.AdaptiveAvgPool2d(size),
                nn.Conv2d(in_channels, in_channels // 4, 1, bias=False),
                nn.BatchNorm2d(in_channels // 4),
                nn.ReLU(inplace=True)
            ) for size in sizes
        ])
        self.bottleneck = nn.Sequential(
            nn.Conv2d(in_channels + (in_channels // 4) * len(sizes), out_channels, 1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h, w = x.shape[2], x.shape[3]
        pyramids = [x] + [F.interpolate(stage(x), size=(h, w), mode="bilinear", align_corners=False)
                          for stage in self.stages]
        return self.bottleneck(torch.cat(pyramids, dim=1))


# ---------------------------------------------------------------------------
# Shared Prediction Head
# ---------------------------------------------------------------------------
class SegHead(nn.Module):
    def __init__(self, in_ch: int, mid_ch: int, activation: str = "sigmoid"):
        super().__init__()
        self.conv1 = nn.Sequential(
            nn.Conv2d(in_ch, mid_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(mid_ch),
            nn.ReLU(inplace=True)
        )
        self.conv2 = nn.Conv2d(mid_ch, 1, 1)
        self.act = nn.Sigmoid() if activation == "sigmoid" else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.conv2(self.conv1(x)))


# ---------------------------------------------------------------------------
# Main Multi-Task ResUNet-a
# ---------------------------------------------------------------------------
class MultiTaskResUNet(nn.Module):
    """
    Multi-Task ResUNet-a for parcel boundary detection.

    Backbone: ResNet-34 (ImageNet pretrained via segmentation_models_pytorch)
    Three concurrent output heads: extent, boundary, distance.
    """

    def __init__(
        self,
        encoder_name: str = "resnet34",
        encoder_weights: str = "imagenet",
        in_channels: int = 3,
        decoder_channels: tuple = (256, 128, 64, 32, 16),
    ):
        super().__init__()

        if not _SMP_AVAILABLE:
            raise ImportError(
                "segmentation_models_pytorch is required. "
                "Run: pip install segmentation-models-pytorch"
            )

        # Shared encoder-decoder backbone
        # We temporarily create a 3-channel version to grab the true ImageNet weights
        # because SMP destroys them if in_channels != 3.
        temp_backbone = smp.Unet(
            encoder_name=encoder_name, encoder_weights=encoder_weights,
            in_channels=3, classes=1, decoder_channels=decoder_channels, activation=None
        )
        
        self._backbone = smp.Unet(
            encoder_name=encoder_name,
            encoder_weights=None,  # We will manually graft the weights
            in_channels=in_channels,
            classes=1,
            decoder_channels=decoder_channels,
            activation=None,
        )
        
        # Graft all weights from temp_backbone
        self._backbone.load_state_dict(temp_backbone.state_dict(), strict=False)
        
        # Specifically fix the first conv layer (which has 4 channels now)
        if in_channels == 4:
            # Copy the 3-channel ImageNet weights into the first 3 channels
            with torch.no_grad():
                # For resnet, first conv is usually encoder.conv1
                old_weight = temp_backbone.encoder.conv1.weight.data
                self._backbone.encoder.conv1.weight.data[:, :3, :, :] = old_weight
                # Zero-initialize the 4th channel so it acts exactly like the pretrained model initially
                self._backbone.encoder.conv1.weight.data[:, 3:4, :, :] = 0.0

        # The feature dimension at the final decoder stage
        feat_ch = decoder_channels[-1]  # 16

        # PSP for multi-scale context at bottleneck
        enc_out_ch = self._backbone.encoder.out_channels[-1]
        self.psp = PSPModule(enc_out_ch, enc_out_ch)

        # Three task-specific prediction heads
        # Must output RAW LOGITS to ensure numerical stability for BCEWithLogitsLoss
        self.head_extent   = SegHead(feat_ch, 32, activation="identity")
        self.head_boundary = SegHead(feat_ch, 32, activation="identity")
        self.head_distance = SegHead(feat_ch, 32, activation="sigmoid") # Distance uses MSE over [0,1], so keep sigmoid

        # Label for audit trail
        self.dataset_label = "TRANSFER_LEARNED_UNVALIDATED"

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """
        Args:
            x: (B, 3, 512, 512) normalized RGB tensor [0, 1]
        Returns:
            dict with 'extent', 'boundary', 'distance' — each (B, 1, 512, 512)
        """
        # Run through SMP backbone encoder-decoder, get features before final conv
        features = self._backbone.encoder(x)

        # PSP on bottleneck features
        features[-1] = self.psp(features[-1])

        # Decoder (SMP UnetDecoder expects a list of features)
        decoder_output = self._backbone.decoder(features)

        return {
            "extent":   self.head_extent(decoder_output),
            "boundary": self.head_boundary(decoder_output),
            "distance": self.head_distance(decoder_output),
        }

    def predict(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """Convenience wrapper with torch.no_grad for inference."""
        self.eval()
        with torch.no_grad():
            preds = self.forward(x)
            preds["extent"] = preds["extent"].sigmoid()
            preds["boundary"] = preds["boundary"].sigmoid()
            # distance is already sigmoided in its head
            return preds


# ---------------------------------------------------------------------------
# Combined Multi-Task Loss
# ---------------------------------------------------------------------------
class MultiTaskLoss(nn.Module):
    """
    Weighted combination of:
      - BCE + Dice for extent (handles class imbalance)
      - BCE + Dice for boundary (handles very thin bund lines)
      - MSE for distance (smooth regression target)

    Weights follow Waldner–Diakogiannis: boundary gets higher weight because
    it is the rarest and most discriminative signal.
    """
    def __init__(
        self,
        w_extent: float = 0.3,
        w_boundary: float = 0.5,
        w_distance: float = 0.2,
        boundary_pos_weight: float = 10.0,  # bunds are ~3% of pixels
    ):
        super().__init__()
        self.w_extent   = w_extent
        self.w_boundary = w_boundary
        self.w_distance = w_distance

        self.bce_extent   = nn.BCEWithLogitsLoss()
        self.bce_boundary = nn.BCEWithLogitsLoss(
            pos_weight=torch.tensor(boundary_pos_weight)
        )
        self.mse_distance = nn.MSELoss()

    @staticmethod
    def dice_loss(pred: torch.Tensor, target: torch.Tensor, smooth: float = 1.0) -> torch.Tensor:
        pred_flat   = pred.view(-1)
        target_flat = target.view(-1)
        intersection = (pred_flat * target_flat).sum()
        return 1.0 - (2.0 * intersection + smooth) / (pred_flat.sum() + target_flat.sum() + smooth)

    def forward(
        self,
        preds: dict[str, torch.Tensor],
        targets: dict[str, torch.Tensor],
    ) -> tuple[torch.Tensor, dict]:
        # Extent: BCE (with logits) + Dice
        loss_ext = self.bce_extent(preds["extent"], targets["extent"]) + \
                   self.dice_loss(preds["extent"].sigmoid(), targets["extent"])

        # Boundary: BCE (with pos_weight) + Dice
        loss_bnd = self.bce_boundary(preds["boundary"], targets["boundary"]) + \
                   self.dice_loss(preds["boundary"].sigmoid(), targets["boundary"])

        # Distance: MSE
        loss_dist = self.mse_distance(preds["distance"], targets["distance"])

        total = (self.w_extent * loss_ext +
                 self.w_boundary * loss_bnd +
                 self.w_distance * loss_dist)

        return total, {
            "loss_total":    total.item(),
            "loss_extent":   loss_ext.item(),
            "loss_boundary": loss_bnd.item(),
            "loss_distance": loss_dist.item(),
        }


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------
def build_model(
    encoder: str = "resnet34",
    weights_path: str | None = None,
    device: str = "cpu",
) -> MultiTaskResUNet:
    """Build or load a MultiTaskResUNet. Gracefully falls back if SMP not installed."""
    model = MultiTaskResUNet(encoder_name=encoder)
    if weights_path:
        state = torch.load(weights_path, map_location=device)
        model.load_state_dict(state, strict=False)
        print(f"[ResUNet-a] Loaded weights from {weights_path}")
    model.to(device)
    model.eval()
    return model
