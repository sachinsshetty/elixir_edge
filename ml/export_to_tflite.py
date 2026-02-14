#!/usr/bin/env python3
"""
Export the health risk classifier to TFLite for mobile/edge deployment.

1. Tries Hugging Face Optimum (if available) to export the PyTorch MobileBERT model.
2. Fallback: trains a small Keras model on the same dataset and exports to TFLite.

For Android with MediaPipe TextClassifier (same API as the reference
bert_classifier.tflite): use --for_mediapipe to build a 3-input BERT-style TFLite
(ids, mask, segment_ids) and attach metadata (vocab + labels) so the model can
be used as model.tflite in app assets with no code changes.

Usage:
  python ml/export_to_tflite.py
  python ml/export_to_tflite.py --use_keras_only
  python ml/export_to_tflite.py --for_mediapipe   # output: model.tflite for Android assets
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAVED_MODEL = REPO_ROOT / "ml" / "saved_model"
TFLITE_DIR = REPO_ROOT / "ml" / "tflite"
ANDROID_ASSETS = REPO_ROOT / "android" / "elixirtecho" / "app" / "src" / "main" / "assets"
DATASET_CSV = REPO_ROOT / "data" / "health_risk_dataset.csv"
MAX_LEN = 64
RISK_LABELS = ["green", "yellow", "red"]
NUM_LABELS = len(RISK_LABELS)
# BERT-style input names expected by MediaPipe TextClassifier
INPUT_IDS_NAME = "ids"
INPUT_MASK_NAME = "mask"
INPUT_SEGMENT_IDS_NAME = "segment_ids"
OUTPUT_LOGITS_NAME = "logits"


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


def _write_vocab_txt(tokenizer, out_path: Path) -> None:
    """Write BERT-style vocab (one token per line, line index = token id)."""
    vocab = getattr(tokenizer, "get_vocab", None)
    vocab_dict = vocab() if callable(vocab) else (vocab if isinstance(vocab, dict) else {})
    if not vocab_dict:
        vocab_dict = getattr(tokenizer, "vocab", {}) or {}
    default_size = getattr(tokenizer, "vocab_size", 30522) or 30522
    size = max(default_size, max(vocab_dict.values()) + 1) if vocab_dict else default_size
    id_to_token = {v: k for k, v in vocab_dict.items()}
    lines = [id_to_token.get(i, f"[unused{i}]") for i in range(size)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


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


def export_keras_for_mediapipe() -> bool:
    """
    Build a 3-input BERT-style TFLite (ids, mask, segment_ids) and optional
    metadata so it can be used with MediaPipe TextClassifier on Android as model.tflite.
    """
    try:
        import numpy as np
        import pandas as pd
        import tensorflow as tf
        from transformers import AutoTokenizer
    except ImportError as e:
        print("MediaPipe export needs: pip install tensorflow transformers pandas", e)
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
    attention_mask = np.array(enc["attention_mask"], dtype=np.int32)
    token_type_ids = np.array(enc.get("token_type_ids", np.zeros_like(input_ids)), dtype=np.int32)
    labels_np = np.array(labels, dtype=np.int32)
    if len(texts) < 100:
        input_ids = np.tile(input_ids, (3, 1))
        attention_mask = np.tile(attention_mask, (3, 1))
        token_type_ids = np.tile(token_type_ids, (3, 1))
        labels_np = np.tile(labels_np, 3)

    vocab_size = getattr(tokenizer, "vocab_size", 30522) or 30522

    # BERT-style 3 inputs so MediaPipe TextClassifier (and metadata tokenizer) can feed the model
    print("Building Keras model (3 BERT inputs: ids, mask, segment_ids)...")
    ids_inp = tf.keras.layers.Input(shape=(MAX_LEN,), dtype=tf.int32, name=INPUT_IDS_NAME)
    mask_inp = tf.keras.layers.Input(shape=(MAX_LEN,), dtype=tf.int32, name=INPUT_MASK_NAME)
    seg_inp = tf.keras.layers.Input(shape=(MAX_LEN,), dtype=tf.int32, name=INPUT_SEGMENT_IDS_NAME)
    # Main path uses only ids; mask/segment are for API compatibility (must be in graph)
    x = tf.keras.layers.Embedding(vocab_size, 128)(ids_inp)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    x = tf.keras.layers.Dense(64, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    logits = tf.keras.layers.Dense(NUM_LABELS, name=OUTPUT_LOGITS_NAME)(x)
    # Tie mask/segment into graph so Keras accepts them (zero contribution, same shape as logits)
    def _zero_from_inputs(inputs):
        logits_t, mask_t, seg_t = inputs[0], inputs[1], inputs[2]
        z = 0.0 * (tf.reduce_sum(tf.cast(mask_t, tf.float32)) + tf.reduce_sum(tf.cast(seg_t, tf.float32)))
        return logits_t + z * tf.ones_like(logits_t)
    logits = tf.keras.layers.Lambda(
        _zero_from_inputs, name="logits_out", output_shape=(None, NUM_LABELS)
    )([logits, mask_inp, seg_inp])
    model = tf.keras.Model(inputs=[ids_inp, mask_inp, seg_inp], outputs=logits)
    model.compile(
        optimizer="adam",
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )

    print("Training Keras model...")
    model.fit(
        [input_ids, attention_mask, token_type_ids],
        labels_np,
        epochs=8,
        batch_size=8,
        validation_split=0.15,
        verbose=1,
    )

    TFLITE_DIR.mkdir(parents=True, exist_ok=True)

    print("Converting to TFLite (3 inputs, 1 output)...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()
    base_tflite = TFLITE_DIR / "health_risk_classifier_3input.tflite"
    base_tflite.write_bytes(tflite_model)
    print("Wrote", base_tflite)

    # Vocab in BERT format (one token per line) for metadata tokenizer
    vocab_path = TFLITE_DIR / "vocab.txt"
    _write_vocab_txt(tokenizer, vocab_path)
    print("Wrote", vocab_path)

    labels_path = TFLITE_DIR / "labels.txt"
    labels_path.write_text("\n".join(RISK_LABELS))

    # Attach metadata and pack vocab + labels into model.tflite for Android
    out_model = TFLITE_DIR / "model.tflite"
    if _attach_mediapipe_metadata(base_tflite, vocab_path, labels_path, out_model):
        print("Wrote MediaPipe-ready", out_model)
        _copy_to_android_assets(out_model)
    else:
        # No metadata: still copy 3-input TFLite as model.tflite; app may need custom path or metadata added later
        shutil.copy(base_tflite, out_model)
        print("Wrote", out_model, "(no metadata attached; install tflite-support for full MediaPipe compatibility)")
        _copy_to_android_assets(out_model)

    tokenizer.save_pretrained(str(TFLITE_DIR))
    (TFLITE_DIR / "README_mediapipe.txt").write_text(
        "model.tflite: 3 inputs (ids, mask, segment_ids) shape (1, 64) int32; output (logits) (1, 3) float32.\n"
        "For Android: put model.tflite in app/src/main/assets/ (as model.tflite).\n"
        "Labels: green, yellow, red. If metadata was attached, MediaPipe TextClassifier uses it as-is."
    )
    return True


def _get_tflite_input_names(model_buffer: bytearray) -> tuple:
    """Return (ids_name, mask_name, segment_name) from the TFLite model (order may vary)."""
    try:
        from tensorflow_lite_support.metadata.python.metadata_writers import writer_utils
    except ImportError:
        return (INPUT_IDS_NAME, INPUT_MASK_NAME, INPUT_SEGMENT_IDS_NAME)
    names = writer_utils.get_input_tensor_names(model_buffer)
    # Map by suffix so we find ids, mask, segment_ids regardless of prefix (e.g. serving_default_*:0)
    by_key = {}
    for n in names:
        n_lower = n.lower()
        if "ids" in n_lower and "segment" not in n_lower and "mask" not in n_lower:
            by_key["ids"] = n
        elif "mask" in n_lower:
            by_key["mask"] = n
        elif "segment" in n_lower:
            by_key["segment"] = n
    return (
        by_key.get("ids", names[0] if len(names) > 0 else INPUT_IDS_NAME),
        by_key.get("mask", names[1] if len(names) > 1 else INPUT_MASK_NAME),
        by_key.get("segment", names[2] if len(names) > 2 else INPUT_SEGMENT_IDS_NAME),
    )


def _attach_mediapipe_metadata(
    tflite_path: Path, vocab_path: Path, labels_path: Path, out_path: Path
) -> bool:
    """Attach TFLite metadata (BERT tokenizer + output labels) so MediaPipe TextClassifier accepts the model."""
    try:
        from tensorflow_lite_support.metadata.python.metadata_writers import bert_nl_classifier
        from tensorflow_lite_support.metadata.python.metadata_writers import metadata_info
    except ImportError:
        return False

    model_buffer = bytearray(tflite_path.read_bytes())
    ids_name, mask_name, segment_name = _get_tflite_input_names(model_buffer)
    tokenizer_md = metadata_info.BertTokenizerMd(vocab_file_path="vocab.txt")
    try:
        writer = bert_nl_classifier.MetadataWriter.create_for_inference(
            model_buffer,
            tokenizer_md=tokenizer_md,
            label_file_paths=[str(labels_path)],
            ids_name=ids_name,
            mask_name=mask_name,
            segment_name=segment_name,
        )
    except ValueError as e:
        print("Metadata attachment failed:", e, file=sys.stderr)
        return False

    writer._associated_files = [str(labels_path), str(vocab_path)]
    populated = writer.populate()
    out_path.write_bytes(populated)
    return True


def _copy_to_android_assets(model_path: Path) -> None:
    """Copy model.tflite to Android app assets if the assets dir exists."""
    if not ANDROID_ASSETS.exists():
        return
    dest = ANDROID_ASSETS / "model.tflite"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(model_path, dest)
    print("Copied to", dest)


def main():
    parser = argparse.ArgumentParser(description="Export health risk model to TFLite")
    parser.add_argument("--use_keras_only", action="store_true", help="Skip Optimum, use Keras fallback only")
    parser.add_argument(
        "--for_mediapipe",
        action="store_true",
        help="Build 3-input BERT-style TFLite + metadata for Android MediaPipe TextClassifier (output: model.tflite)",
    )
    args = parser.parse_args()

    TFLITE_DIR.mkdir(parents=True, exist_ok=True)

    if args.for_mediapipe:
        ok = export_keras_for_mediapipe()
        if ok:
            print("\nDone. For Android: use ml/tflite/model.tflite as model.tflite in app assets.")
            print("  Copy to android/.../app/src/main/assets/model.tflite (or run export; it may auto-copy).")
    elif args.use_keras_only:
        ok = export_keras_to_tflite()
        if ok:
            print("\nDone. TFLite output:", TFLITE_DIR)
            print("  - health_risk_classifier.tflite")
            print("  - tokenizer files + labels.txt for mobile preprocessing")
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
