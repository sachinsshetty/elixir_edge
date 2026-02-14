#!/usr/bin/env python3
"""
Export the health risk classifier to TFLite for mobile/edge deployment.

1. Tries Hugging Face Optimum (if available) to export the PyTorch MobileBERT model.
2. Fallback: trains a small Keras model on the same dataset and exports to TFLite.
   Mobile apps can use the exported tokenizer (vocab) to preprocess text the same way.

Usage:
  python ml/export_to_tflite.py
  python ml/export_to_tflite.py --use_keras_only   # skip Optimum, use Keras fallback only
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAVED_MODEL = REPO_ROOT / "ml" / "saved_model"
TFLITE_DIR = REPO_ROOT / "ml" / "tflite"
DATASET_CSV = REPO_ROOT / "data" / "health_risk_dataset.csv"
MAX_LEN = 64
RISK_LABELS = ["green", "yellow", "red"]
NUM_LABELS = len(RISK_LABELS)


def risk_to_id(risk: str) -> int:
    r = str(risk).strip().lower()
    return RISK_LABELS.index(r) if r in RISK_LABELS else 0


def try_optimum_export() -> bool:
    """Export via optimum-cli export tflite. Returns True if successful."""
    if not SAVED_MODEL.exists():
        print("No saved PyTorch model at", SAVED_MODEL)
        return False
    for cmd in (
        ["optimum-cli", "export", "tflite", "--model", str(SAVED_MODEL), "--task", "text-classification", "--sequence_length", str(MAX_LEN), str(TFLITE_DIR)],
        [sys.executable, "-m", "optimum_cli", "export", "tflite", "--model", str(SAVED_MODEL), "--task", "text-classification", "--sequence_length", str(MAX_LEN), str(TFLITE_DIR)],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT))
            if result.returncode == 0:
                print("Optimum export succeeded.")
                _copy_tokenizer_and_labels()
                return True
            print("Optimum TFLite export failed (TF MobileBERT may be unavailable):")
            print(result.stderr or result.stdout)
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            print("Optimum export timed out.")
    return False


def _copy_tokenizer_and_labels():
    """Copy tokenizer from SAVED_MODEL to TFLITE_DIR and write labels.txt."""
    if not SAVED_MODEL.exists():
        return
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(str(SAVED_MODEL))
        TFLITE_DIR.mkdir(parents=True, exist_ok=True)
        tokenizer.save_pretrained(str(TFLITE_DIR))
        (TFLITE_DIR / "labels.txt").write_text("\n".join(RISK_LABELS))
    except Exception as e:
        print("Could not copy tokenizer:", e)


def export_keras_to_tflite() -> bool:
    """
    Train a small Keras model (embedding + pooling + dense) on the same dataset,
    then export to TFLite. Copies tokenizer to TFLITE_DIR for mobile use.
    """
    try:
        import numpy as np
        import pandas as pd
        import tensorflow as tf
        from transformers import AutoTokenizer
    except ImportError as e:
        print("Keras fallback needs: pip install tensorflow transformers pandas", e)
        return False

    if not SAVED_MODEL.exists():
        print("No saved model at", SAVED_MODEL, "- run finetune_mobilebert_health.py first.")
        return False
    if not DATASET_CSV.exists():
        print("No dataset at", DATASET_CSV, "- run data/build_health_risk_dataset.py first.")
        return False

    print("Loading tokenizer and dataset...")
    tokenizer = AutoTokenizer.from_pretrained(str(SAVED_MODEL))
    df = pd.read_csv(DATASET_CSV)
    texts = df["text"].astype(str).tolist()
    labels = [risk_to_id(r) for r in df["risk_level"]]

    enc = tokenizer(
        texts,
        padding="max_length",
        truncation=True,
        max_length=MAX_LEN,
        return_tensors="np",
    )
    input_ids = np.array(enc["input_ids"], dtype=np.int32)
    labels_np = np.array(labels, dtype=np.int32)
    # Repeat to get more steps
    if len(texts) < 100:
        input_ids = np.tile(input_ids, (3, 1))
        labels_np = np.tile(labels_np, 3)

    vocab_size = getattr(tokenizer, "vocab_size", 30522) or 30522

    print("Building Keras model (embedding + pool + dense)...")
    inp = tf.keras.layers.Input(shape=(MAX_LEN,), dtype=tf.int32, name="input_ids")
    x = tf.keras.layers.Embedding(vocab_size, 128)(inp)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    x = tf.keras.layers.Dense(64, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    logits = tf.keras.layers.Dense(NUM_LABELS, name="logits")(x)
    model = tf.keras.Model(inputs=inp, outputs=logits)
    model.compile(
        optimizer="adam",
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )

    print("Training Keras model...")
    model.fit(input_ids, labels_np, epochs=8, batch_size=8, validation_split=0.15, verbose=1)

    TFLITE_DIR.mkdir(parents=True, exist_ok=True)

    # Convert from Keras model directly to avoid SavedModel variables that TFLite may not support
    print("Converting to TFLite...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()
    tflite_path = TFLITE_DIR / "health_risk_classifier.tflite"
    tflite_path.write_bytes(tflite_model)
    print("Wrote", tflite_path)

    # Copy tokenizer so mobile can preprocess the same way
    tokenizer.save_pretrained(str(TFLITE_DIR))
    print("Copied tokenizer to", TFLITE_DIR)

    # Write metadata for mobile
    (TFLITE_DIR / "labels.txt").write_text("\n".join(RISK_LABELS))
    (TFLITE_DIR / "README.txt").write_text(
        "health_risk_classifier.tflite: input shape (1, 64) int32 (input_ids), output shape (1, 3) float32 (logits).\n"
        "Use tokenizer in this folder to convert text to input_ids (max_length=64, padding=max_length, truncation=True).\n"
        "labels.txt: green, yellow, red (index 0, 1, 2)."
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Export health risk model to TFLite")
    parser.add_argument("--use_keras_only", action="store_true", help="Skip Optimum, use Keras fallback only")
    args = parser.parse_args()

    TFLITE_DIR.mkdir(parents=True, exist_ok=True)

    if args.use_keras_only:
        ok = export_keras_to_tflite()
    else:
        ok = try_optimum_export()
        if not ok:
            print("Falling back to Keras model + TFLite export...")
            ok = export_keras_to_tflite()

    if ok:
        print("\nDone. TFLite output:", TFLITE_DIR)
        print("  - health_risk_classifier.tflite (or from Optimum)")
        print("  - tokenizer files + labels.txt for mobile preprocessing")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
