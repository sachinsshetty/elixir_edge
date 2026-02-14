health_risk_classifier.tflite: input shape (1, 64) int32 (input_ids), output shape (1, 3) float32 (logits).
Use tokenizer in this folder to convert text to input_ids (max_length=64, padding=max_length, truncation=True).
labels.txt: green, yellow, red (index 0, 1, 2).