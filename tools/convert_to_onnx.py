"""
Convert Keras HDF5 model to ONNX format.

Requirements:
    uv sync --group convert

Usage:
    uv run --group convert python tools/convert_to_onnx.py
    uv run --group convert python tools/convert_to_onnx.py resources/model/default_model.hdf5
"""

import sys
import os


def convert(hdf5_path, output_path=None):
    try:
        import tensorflow as tf
        import tf2onnx
    except ImportError:
        print("Error: Run this script with: uv run --group dev python tools/convert_to_onnx.py")
        sys.exit(1)

    if output_path is None:
        output_path = os.path.splitext(hdf5_path)[0] + ".onnx"

    print(f"Loading: {hdf5_path}")
    # Use tf_keras for Keras 2.x model format compatibility
    try:
        import tf_keras
        model = tf_keras.models.load_model(hdf5_path)
    except ImportError:
        model = tf.keras.models.load_model(hdf5_path)

    input_signature = [
        tf.TensorSpec(model.inputs[0].shape, tf.float32, name="input")
    ]

    print(f"Converting to ONNX...")
    _, _ = tf2onnx.convert.from_keras(model, input_signature, output_path=output_path)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    hdf5 = sys.argv[1] if len(sys.argv) > 1 else "resources/model/default_model.hdf5"
    convert(hdf5)
