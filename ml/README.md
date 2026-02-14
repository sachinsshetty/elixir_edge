# Health risk model (MobileBERT)

Fine-tunes **MobileBERT** (PyTorch) on wearable health text to predict **risk level** (green / yellow / red) and **recommendation** for edge soldier-style monitoring (heat stress, fatigue, dehydration).

## Steps

1. **Build training data** from daily vitals (run from repo root):
   ```bash
   python data/build_health_risk_dataset.py
   ```
   Produces `data/health_risk_dataset.csv` (text, risk_level, recommendation).

2. **Fine-tune MobileBERT** (requires `pip install -r requirements-ml.txt`):
   ```bash
   source venv/bin/activate
   pip install -r requirements-ml.txt
   python ml/finetune_mobilebert_health.py --epochs 3 --batch_size 4
   ```
   Saves model and tokenizer under `ml/saved_model/`.

3. **Use in code**: load with `transformers` and map predicted class to recommendation (see script’s example inference at the end).

## Challenge alignment

- **Input**: Text summary of vitals (HR, SpO2, steps, intensity, sleep) as produced from wearable/smartwatch.
- **Output**: Risk level (green/yellow/red) and a short recommendation (e.g. “Rest and rehydrate in 10 min”).
- **Deployment**: Model can be exported to ONNX or TFLite for on-device inference (phone-class or edge hub).
