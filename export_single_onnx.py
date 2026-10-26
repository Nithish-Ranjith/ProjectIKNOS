import torch
from ml.boundary.v2.model import CentroidConditionedUNet
import os

def run():
    print("Exporting ONNX...")
    model = CentroidConditionedUNet(encoder_name="efficientnet-b3", in_channels=4)
    best_path = "models/weights/v2_real_best.pth"
    onnx_path = "models/weights/v2_real_model.onnx"
    model._net.load_state_dict(torch.load(best_path, map_location="cpu", weights_only=False), strict=False)
    model.eval().cpu()
    dummy = torch.randn(1, 4, 512, 512)
    torch.onnx.export(
        model, dummy, onnx_path,
        input_names=["input"], output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=18,
        export_params=True,
    )
    size = os.path.getsize(onnx_path)
    print(f"ONNX exported to {onnx_path}. Size: {size / 1e6:.2f} MB")
    
if __name__ == "__main__":
    run()
