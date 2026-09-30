"""
ml/boundary/model.py — U-Net boundary detection model.

Architecture:
  - Transfer-learned from AI4Boundaries / Eurocrops pre-trained weights.
  - Fine-tuned on Indian pilot parcel dataset (hand-labeled GeoJSON).
  - BQ-04 BLOCKER: requires 20-50 hand-labeled Indian parcel images for fine-tuning.

Design contracts:
  - Output is a CANDIDATE physical boundary.
  - Model output is NEVER called a legal boundary.
  - dataset_label on BoundaryCandidate rows must remain 'TRANSFER_LEARNED_UNVALIDATED'
    until fine-tuned on validated Indian data.
"""
try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

if _TORCH_AVAILABLE:
    import torch
    import torch.nn as nn

    class DoubleConv(nn.Module):
        def __init__(self, in_channels, out_channels):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_channels),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_channels),
                nn.ReLU(inplace=True)
            )
        def forward(self, x):
            return self.conv(x)

    class UNet(nn.Module):
        """
        Lightweight U-Net for aerial parcel boundary segmentation.
        Input: (B, 3, H, W) RGB aerial tile (256x256 px)
        Output: (B, 1, H, W) boundary probability mask
        """
        def __init__(self, in_channels=3, out_channels=1, features=(32, 64, 128, 256)):
            super().__init__()
            self.downs = nn.ModuleList()
            self.ups = nn.ModuleList()
            self.pool = nn.MaxPool2d(2, 2)

            in_ch = in_channels
            for f in features:
                self.downs.append(DoubleConv(in_ch, f))
                in_ch = f

            self.bottleneck = DoubleConv(features[-1], features[-1] * 2)

            for f in reversed(features):
                self.ups.append(nn.ConvTranspose2d(f * 2, f, 2, 2))
                self.ups.append(DoubleConv(f * 2, f))

            self.final_conv = nn.Conv2d(features[0], out_channels, 1)
            self.sigmoid = nn.Sigmoid()

        def forward(self, x):
            skip_connections = []
            for down in self.downs:
                x = down(x)
                skip_connections.append(x)
                x = self.pool(x)

            x = self.bottleneck(x)
            skip_connections = skip_connections[::-1]

            for i in range(0, len(self.ups), 2):
                x = self.ups[i](x)
                skip = skip_connections[i // 2]
                if x.shape != skip.shape:
                    x = torch.nn.functional.interpolate(x, size=skip.shape[2:])
                x = torch.cat([skip, x], dim=1)
                x = self.ups[i + 1](x)

            return self.sigmoid(self.final_conv(x))

    def load_model(weights_path: str = None) -> "UNet":
        model = UNet()
        if weights_path:
            model.load_state_dict(torch.load(weights_path, map_location="cpu"))
        model.eval()
        return model

else:
    class UNet:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch not installed. Run: pip install torch torchvision")

    def load_model(weights_path=None):
        raise ImportError("PyTorch not installed.")


# BQ-04 note embedded in module docstring — available at runtime
BLOCKER_NOTE = (
    "BQ-04 BLOCKER: Fine-tuning U-Net requires 20-50 hand-labeled Indian parcel "
    "images annotated as GeoJSON polygons. The current model uses transfer-learned "
    "weights from AI4Boundaries/Eurocrops — these are European agricultural parcels. "
    "Output label is TRANSFER_LEARNED_UNVALIDATED until Indian fine-tuning is completed."
)
