import torch
import segmentation_models_pytorch as smp

model3 = smp.Unet(encoder_name="resnet34", encoder_weights="imagenet", in_channels=3)
model4 = smp.Unet(encoder_name="resnet34", encoder_weights="imagenet", in_channels=4)

w3 = model3.encoder.conv1.weight.data
w4 = model4.encoder.conv1.weight.data

print("w3 sum:", w3.sum().item())
print("w4 (first 3) sum:", w4[:, :3, :, :].sum().item())
print("Equal?", torch.allclose(w3, w4[:, :3, :, :]))
