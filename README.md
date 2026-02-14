# Elixir Edge

- [Challenge Docs](challange.md)
- **Healthcare / Soldier Health**: Wearable vitals → health insights → risk classification (green/yellow/red) and recommendations.

---

## Setup

```bash
python3.10 -m venv venv
source venv/bin/activate   # Linux/macOS
pip install pandas
```

For ML (MobileBERT fine-tuning and inference):

```bash
pip install -r requirements-ml.txt   # torch, transformers, pandas
```

---

## 1. Health data analysis (wearable → daily summary)

Uses Redmi Watch 5 Lite (or similar) CSVs in `data/` to produce a daily health summary and optional report.

**Input:** Place these in `data/`:

- `hlth_center_aggregated_fitness_data.csv`
- `hlth_center_fitness_data.csv`
- `hlth_center_sport_record.csv`

**Run:**

```bash
source venv/bin/activate
python data/health_insights.py
```

**Output:**

- Console report: steps, calories, heart rate, sleep, SpO2, sport sessions, stand breaks.
- `data/health_daily_summary.csv` — one row per day (steps, calories, HR, sleep, SpO2, etc.).

---

## 2. Build ML training dataset (vitals → risk labels)

Turns the daily summary (and soldier-relevant synthetic vitals) into a text + risk-level dataset for the classifier.

**Run:**

```bash
python data/build_health_risk_dataset.py
```

**Output:** `data/health_risk_dataset.csv` with columns `text`, `risk_level` (green/yellow/red), `recommendation`.

Requires `data/health_daily_summary.csv` (from step 1). Synthetic examples are added so all three risk levels appear.

---

## 3. Fine-tune MobileBERT (train risk classifier)

Trains a small BERT model to classify vital-sign text into green / yellow / red and fixed recommendations.

**Run:**

```bash
source venv/bin/activate
pip install -r requirements-ml.txt
python ml/finetune_mobilebert_health.py --epochs 5 --batch_size 8
```

**Options:** `--dataset`, `--output`, `--epochs`, `--batch_size`, `--max_length`, `--lr`.

**Output:** `ml/saved_model/` (model + tokenizer).

---

## 4. Run inference (risk + recommendation)

**Single sentence:**

```bash
python ml/predict_health_risk.py "HR average 88 bpm HR max 105 steps 5000 active 25 minutes sleep 4h"
```

**Examples for all three levels:**

```bash
python ml/run_inference_examples.py
```

**Example inputs by level:**

| Level  | Example input |
|--------|----------------|
| Green  | `"HR average 65 bpm HR max 85 SpO2 98 percent steps 2000 active 5 minutes sleep 7h"` |
| Yellow | `"HR average 88 bpm HR max 105 SpO2 95 percent steps 5000 active 25 minutes sleep 4h"` |
| Red    | `"HR average 108 bpm HR max 125 SpO2 87 percent steps 8000 active 50 minutes sleep 0h"` |

---

## 5. Export to TFLite (for mobile/edge)

Exports the classifier to TFLite so it can run on Android/iOS or other edge devices.

**Run:**

```bash
pip install tensorflow transformers   # for Keras fallback
python ml/export_to_tflite.py
```

Optional: `pip install optimum[exporters-tf]` to try exporting the PyTorch MobileBERT via Optimum first. If that fails (e.g. TF MobileBERT not available), the script automatically trains a small Keras model on the same dataset and exports it to TFLite.

**Output:** `ml/tflite/`

- `health_risk_classifier.tflite` — model (input: `(1, 64)` int32 token IDs; output: `(1, 3)` float32 logits).
- Tokenizer files (vocab, config) — use the same preprocessing on device.
- `labels.txt` — green, yellow, red (indices 0, 1, 2).
- `README.txt` — input/output shapes and usage notes.

**Test TFLite locally:**

```bash
python ml/run_tflite_inference.py "HR average 88 bpm HR max 105 steps 5000"
```

**On mobile:** Load the `.tflite` file and tokenizer (or replicate tokenization with the same vocab and max length 64). Run the interpreter; argmax of the 3 output logits gives the risk level index.

---

## Quick reference

| Step | Command | Output |
|------|--------|--------|
| 1. Health insights | `python data/health_insights.py` | Report + `data/health_daily_summary.csv` |
| 2. Build dataset   | `python data/build_health_risk_dataset.py` | `data/health_risk_dataset.csv` |
| 3. Train model    | `python ml/finetune_mobilebert_health.py --epochs 5` | `ml/saved_model/` |
| 4. Predict        | `python ml/predict_health_risk.py "vital text..."` | Risk + recommendation |
| 5. Export TFLite  | `python ml/export_to_tflite.py` | `ml/tflite/*.tflite` + tokenizer |

---

## References

- BertClassifier (TFLite): https://storage.googleapis.com/mediapipe-models/text_classifier/bert_classifier/float32/1/bert_classifier.tflite
- Plex: https://www.perplexity.ai/search/plugins-alias-libs-plugins-and-4AiGhM7pRUW1_QT3FGndRA#0
