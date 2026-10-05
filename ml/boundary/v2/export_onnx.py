import torch
import segmentation_models_pytorch as smp

model = smp.Unet(
    encoder_name="efficientnet-b3",
    encoder_weights=None,
    in_channels=4,
    classes=1,
)

state_dict = torch.load("models/weights/v2_real_best.pth", map_location="cpu")
model.load_state_dict(state_dict)
model.eval()

dummy = torch.randn(1, 4, 512, 512)
torch.onnx.export(
    model, dummy, "models/weights/v2_real_model.onnx",
    input_names=["input"], output_names=["output"],
    opset_version=17
)
print("ONNX export complete.")
