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

3. **Inference** (PyTorch): `python ml/predict_health_risk.py "vital text..."`

4. **Export to TFLite** (for mobile):
   ```bash
   pip install tensorflow transformers
   python ml/export_to_tflite.py
   ```
   Writes `ml/tflite/health_risk_classifier.tflite` plus tokenizer and `labels.txt`. Optionally install `optimum[exporters-tf]` to try exporting the PyTorch BERT via Optimum; otherwise a small Keras model is trained and exported. Test with `python ml/run_tflite_inference.py "vital text..."`.

## Challenge alignment

- **Input**: Text summary of vitals (HR, SpO2, steps, intensity, sleep) as produced from wearable/smartwatch.
- **Output**: Risk level (green/yellow/red) and a short recommendation (e.g. “Rest and rehydrate in 10 min”).
- **Deployment**: Model can be exported to ONNX or TFLite for on-device inference (phone-class or edge hub).
