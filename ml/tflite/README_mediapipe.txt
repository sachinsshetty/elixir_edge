model.tflite: 3 inputs (ids, mask, segment_ids) shape (1, 64) int32; output (logits) (1, 3) float32.
For Android: put model.tflite in app/src/main/assets/ (as model.tflite).
Labels: green, yellow, red. If metadata was attached, MediaPipe TextClassifier uses it as-is.