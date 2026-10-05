import onnxruntime.quantization as q
from pathlib import Path
import os

def quantize():
    weights_dir = Path(__file__).parent.parent.parent.parent / "models" / "weights"
    model_fp32 = weights_dir / "v2_real_model.onnx"
    model_int8 = weights_dir / "v2_real_model_quantized.onnx"
    
    if not model_fp32.exists():
        print(f"Error: FP32 model not found at {model_fp32}")
        return
        
    print(f"Quantizing {model_fp32}...")
    
    # Dynamic quantization compresses weights to int8, activations remain float32.
    # It's fast and requires no calibration dataset.
    q.quantize_dynamic(
        model_input=model_fp32,
        model_output=model_int8,
        weight_type=q.QuantType.QInt8
    )
    
    size_fp32 = os.path.getsize(model_fp32) / (1024 * 1024)
    size_int8 = os.path.getsize(model_int8) / (1024 * 1024)
    
    print(f"Quantization complete!")
    print(f"FP32 Size: {size_fp32:.1f} MB")
    print(f"INT8 Size: {size_int8:.1f} MB")
    print(f"Reduction: {(1 - size_int8/size_fp32)*100:.1f}%")

if __name__ == "__main__":
    quantize()
