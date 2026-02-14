#!/usr/bin/env python3
"""
Fine-tune MobileBERT (PyTorch) on wearable health text for risk classification.

Aligns with Edge Soldier Health Monitoring: model consumes vital-sign text (HR, SpO2,
steps, intensity, sleep) and predicts risk level (green/yellow/red) and recommendation
for heat stress / fatigue. Uses PyTorch (TF MobileBERT was removed in recent transformers).
Model can be exported to ONNX/TFLite for on-device inference later.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DEFAULT_DATASET = DATA_DIR / "health_risk_dataset.csv"
DEFAULT_OUTPUT = REPO_ROOT / "ml" / "saved_model"
RISK_LABELS = ["green", "yellow", "red"]
NUM_LABELS = len(RISK_LABELS)
RECOMMENDATIONS = {
    "green": "Continue normal activity. Stay hydrated.",
    "yellow": "Monitor vital signs. Consider rest and hydration soon.",
    "red": "Heat stress or fatigue risk. Rest and rehydrate. Seek shade. Recommend rest in 10 min.",
}


def load_dataset(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {csv_path}. Run: python data/build_health_risk_dataset.py"
        )
    df = pd.read_csv(csv_path)
    if "text" not in df.columns or "risk_level" not in df.columns:
        raise ValueError("Dataset must have columns 'text' and 'risk_level'.")
    return df


def risk_to_id(risk: str) -> int:
    r = str(risk).strip().lower()
    if r not in RISK_LABELS:
        return 0
    return RISK_LABELS.index(r)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune MobileBERT for health risk classification")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to health_risk_dataset.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output model directory")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size")
    parser.add_argument("--max_length", type=int, default=64, help="Max token length")
    parser.add_argument("--lr", type=float, default=1e-5, help="Learning rate (use 1e-5 if loss is very high at start)")
    args = parser.parse_args()

    try:
        from transformers import AutoTokenizer, MobileBertForSequenceClassification
        import torch
    except ImportError as e:
        print("Missing dependency. Install with:")
        print("  pip install -r requirements-ml.txt")
        print("  # or: pip install transformers torch pandas")
        print(f"(ImportError: {e})")
        return 1

    df = load_dataset(args.dataset)
    df["label"] = df["risk_level"].apply(risk_to_id)
    texts = df["text"].astype(str).tolist()
    labels = df["label"].tolist()

    if len(texts) < 30:
        texts = texts * 4
        labels = labels * 4

    print(f"Training on {len(texts)} examples, {NUM_LABELS} classes: {RISK_LABELS}")

    tokenizer = AutoTokenizer.from_pretrained("google/mobilebert-uncased")
    model = MobileBertForSequenceClassification.from_pretrained(
        "google/mobilebert-uncased",
        num_labels=NUM_LABELS,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    # Training loop
    model.train()
    for epoch in range(args.epochs):
        total_loss = 0.0
        for i in range(0, len(texts), args.batch_size):
            batch_texts = texts[i : i + args.batch_size]
            batch_labels = labels[i : i + args.batch_size]
            enc = tokenizer(
                batch_texts,
                padding="max_length",
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            enc = {k: v.to(device) for k, v in enc.items()}
            labels_t = torch.tensor(batch_labels, dtype=torch.long, device=device)
            optimizer.zero_grad()
            out = model(**enc, labels=labels_t)
            loss = out.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            total_loss += loss.item()
        n_batches = max(1, (len(texts) + args.batch_size - 1) // args.batch_size)
        print(f"Epoch {epoch + 1}/{args.epochs} loss: {total_loss / n_batches:.4f}")

    args.output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    print(f"Saved model and tokenizer to {args.output}")

    # Quick inference example
    model.eval()
    sample = "HR average 82 bpm HR max 105 SpO2 96 percent steps 2276 active 17 minutes"
    with torch.no_grad():
        inp = tokenizer(sample, return_tensors="pt", padding="max_length", truncation=True, max_length=args.max_length)
        inp = {k: v.to(device) for k, v in inp.items()}
        logits = model(**inp).logits
        pred_id = int(logits.argmax(dim=-1).item())
    risk = RISK_LABELS[pred_id]
    rec = RECOMMENDATIONS[risk]
    print(f"\nExample inference: '{sample[:50]}...'")
    print(f"  -> Risk: {risk}, Recommendation: {rec}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
