#!/usr/bin/env python3
"""
Run inference for all three risk levels (green, yellow, red) with example vital-sign text.

Usage:
  python ml/run_inference_examples.py

Or run single examples:
  # Green (normal vitals)
  python ml/predict_health_risk.py "HR average 65 bpm HR max 85 resting HR 58 SpO2 98 percent steps 2000 active 5 minutes sleep 7h"

  # Yellow (elevated)
  python ml/predict_health_risk.py "HR average 88 bpm HR max 105 SpO2 95 percent steps 5000 active 25 minutes sleep 4h"

  # Red (high strain)
  python ml/predict_health_risk.py "HR average 108 bpm HR max 125 SpO2 87 percent steps 8000 active 50 minutes sleep 0h"
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "ml" / "saved_model"

# Example inputs chosen to typically map to each risk level (model may vary after training)
EXAMPLES = [
    ("green", "HR average 65 bpm HR max 85 resting HR 58 SpO2 98 percent steps 2000 active 5 minutes sleep 7h"),
    ("yellow", "HR average 88 bpm HR max 105 SpO2 95 percent steps 5000 active 25 minutes sleep 4h"),
    ("red", "HR average 108 bpm HR max 125 SpO2 87 percent steps 8000 active 50 minutes sleep 0h"),
]


def main():
    if not MODEL_DIR.exists():
        print(f"Model not found at {MODEL_DIR}. Run: python ml/finetune_mobilebert_health.py", file=sys.stderr)
        return 1
    from predict_health_risk import load_model_and_tokenizer, predict, RISK_LABELS, RECOMMENDATIONS
    model, tokenizer = load_model_and_tokenizer(MODEL_DIR)
    print("Risk level examples (expected → predicted)\n" + "=" * 60)
    for expected, text in EXAMPLES:
        risk, rec = predict(text, model, tokenizer)
        match = "✓" if risk == expected else "→"
        print(f"\n[{expected.upper()}] {match} predicted: {risk}")
        print(f"  Input: {text[:70]}...")
        print(f"  Recommendation: {rec}")
    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
