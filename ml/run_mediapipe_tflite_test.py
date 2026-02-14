#!/usr/bin/env python3
"""
Run the MediaPipe-style TFLite model (3 inputs) on example texts and print all 3 scores.
Use this to verify the model is not always predicting green before deploying to Android.

Usage: python ml/run_mediapipe_tflite_test.py
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TFLITE_DIR = REPO_ROOT / "ml" / "tflite"
MODEL_PATH = TFLITE_DIR / "model.tflite"
MAX_LEN = 64
RISK_LABELS = ["green", "yellow", "red"]

EXAMPLES = [
    ("green", "HR average 65 bpm HR max 85 SpO2 98 percent steps 2000 active 5 minutes sleep 7h"),
    ("yellow", "HR average 88 bpm HR max 105 SpO2 95 percent steps 5000 active 25 minutes sleep 4h"),
    ("red", "HR average 108 bpm HR max 125 SpO2 87 percent steps 8000 active 50 minutes sleep 0h"),
]


def main():
    if not MODEL_PATH.exists():
        print(f"Model not found: {MODEL_PATH}")
        print("Run: python ml/export_to_tflite.py --for_mediapipe")
        return 1
    try:
        import numpy as np
        from transformers import AutoTokenizer
        import tensorflow as tf
    except ImportError as e:
        print("Install: pip install tensorflow transformers numpy", e)
        return 1

    interp = tf.lite.Interpreter(model_path=str(MODEL_PATH))
    interp.allocate_tensors()
    input_details = interp.get_input_details()
    output_details = interp.get_output_details()

    tokenizer = AutoTokenizer.from_pretrained(str(TFLITE_DIR))
    print("Model output shape (expect probabilities, sum=1):")
    print()
    for expected, text in EXAMPLES:
        enc = tokenizer(
            text,
            return_tensors="np",
            padding="max_length",
            truncation=True,
            max_length=MAX_LEN,
        )
        ids = enc["input_ids"].astype(np.int32)
        mask = enc["attention_mask"].astype(np.int32)
        seg = enc.get("token_type_ids", np.zeros_like(ids)).astype(np.int32)
        # Order in model: ids, segment_ids, mask (from get_input_details())
        for i, det in enumerate(input_details):
            name = det.get("name", "")
            if "ids" in name and "segment" not in name:
                interp.set_tensor(det["index"], ids)
            elif "segment" in name:
                interp.set_tensor(det["index"], seg)
            elif "mask" in name:
                interp.set_tensor(det["index"], mask)
        interp.invoke()
        out = interp.get_tensor(output_details[0]["index"])[0]
        pred_id = int(np.argmax(out))
        pred_label = RISK_LABELS[pred_id]
        ok = "OK" if pred_label == expected else "MISMATCH"
        scores = " ".join(f"{RISK_LABELS[i]}={out[i]:.3f}" for i in range(3))
        print(f"  Expected {expected} -> {pred_label} ({ok})  [{scores}] sum={out.sum():.3f}")
    print()
    return 0


if __name__ == "__main__":
    exit(main())
