#!/usr/bin/env python3
"""
Run health risk + recommendation from saved MobileBERT model (PyTorch).

Usage:
  python ml/predict_health_risk.py "HR average 88 bpm HR max 105 steps 3000 active 25 minutes"
  python ml/predict_health_risk.py   # reads from stdin, one sentence per line
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "ml" / "saved_model"
RISK_LABELS = ["green", "yellow", "red"]
RECOMMENDATIONS = {
    "green": "Continue normal activity. Stay hydrated.",
    "yellow": "Monitor vital signs. Consider rest and hydration soon.",
    "red": "Heat stress or fatigue risk. Rest and rehydrate. Seek shade. Recommend rest in 10 min.",
}


def load_model_and_tokenizer(model_dir: Path):
    from transformers import AutoTokenizer, MobileBertForSequenceClassification
    import torch
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = MobileBertForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()
    return model, tokenizer


def predict(text: str, model, tokenizer, max_length: int = 64):
    import torch
    device = next(model.parameters()).device
    enc = tokenizer(text, return_tensors="pt", padding="max_length", truncation=True, max_length=max_length)
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        logits = model(**enc).logits
    pred_id = int(logits.argmax(dim=-1).item())
    return RISK_LABELS[pred_id], RECOMMENDATIONS[RISK_LABELS[pred_id]]


def main():
    if not MODEL_DIR.exists():
        print(f"Model not found at {MODEL_DIR}. Run: python ml/finetune_mobilebert_health.py", file=sys.stderr)
        return 1
    model, tokenizer = load_model_and_tokenizer(MODEL_DIR)
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        risk, rec = predict(text, model, tokenizer)
        print(f"Risk: {risk}\nRecommendation: {rec}")
    else:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            risk, rec = predict(line, model, tokenizer)
            print(f"{line[:60]}... -> {risk}: {rec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
