#!/usr/bin/env python3
"""
Run inference using the exported TFLite model (for testing before mobile deployment).

Requires: tensorflow or tflite_runtime, transformers (for tokenizer).
Usage: python ml/run_tflite_inference.py "HR average 88 bpm HR max 105 steps 5000"
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TFLITE_DIR = REPO_ROOT / "ml" / "tflite"
MODEL_PATH = TFLITE_DIR / "health_risk_classifier.tflite"
MAX_LEN = 64
RISK_LABELS = ["green", "yellow", "red"]
RECOMMENDATIONS = {
    "green": "Continue normal activity. Stay hydrated.",
    "yellow": "Monitor vital signs. Consider rest and hydration soon.",
    "red": "Heat stress or fatigue risk. Rest and rehydrate. Seek shade. Recommend rest in 10 min.",
}


def main():
    if not MODEL_PATH.exists():
        print(f"TFLite model not found: {MODEL_PATH}")
        print("Run: python ml/export_to_tflite.py")
        return 1
    try:
        import numpy as np
        from transformers import AutoTokenizer
    except ImportError:
        print("Install: pip install transformers numpy")
        return 1
    try:
        import tensorflow as tf
        interp = tf.lite.Interpreter(model_path=str(MODEL_PATH))
    except Exception:
        try:
            import tflite_runtime.interpreter as tflite
            interp = tflite.Interpreter(model_path=str(MODEL_PATH))
        except ImportError:
            print("Install tensorflow or tflite_runtime")
            return 1

    interp.allocate_tensors()
    input_details = interp.get_input_details()
    output_details = interp.get_output_details()

    tokenizer = AutoTokenizer.from_pretrained(str(TFLITE_DIR))
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "HR average 82 bpm HR max 105 steps 2276 active 17 minutes"
    enc = tokenizer(text, return_tensors="np", padding="max_length", truncation=True, max_length=MAX_LEN)
    input_ids = enc["input_ids"].astype(np.int32)

    interp.set_tensor(input_details[0]["index"], input_ids)
    interp.invoke()
    logits = interp.get_tensor(output_details[0]["index"])
    pred_id = int(np.argmax(logits[0]))
    risk = RISK_LABELS[pred_id]
    rec = RECOMMENDATIONS[risk]
    print(f"Risk: {risk}\nRecommendation: {rec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
