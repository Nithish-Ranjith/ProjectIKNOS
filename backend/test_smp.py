import torch
import segmentation_models_pytorch as smp
model = smp.Unet(encoder_name="resnet34", encoder_weights=None, in_channels=4, classes=1)
features = model.encoder(torch.randn(1, 4, 256, 256))
try:
    model.decoder(features)
    print("decoder(features) SUCCESS")
except Exception as e:
    print(f"decoder(features) FAILED: {e}")
try:
    model.decoder(*features)
    print("decoder(*features) SUCCESS")
except Exception as e:
    print(f"decoder(*features) FAILED: {e}")
