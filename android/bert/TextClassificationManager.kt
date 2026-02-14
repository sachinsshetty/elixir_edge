package com.slabstech.health.elixir_t_echo

import android.content.Context
import android.util.Log
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.text.textclassifier.TextClassifier
import com.google.mediapipe.tasks.text.textclassifier.TextClassifier.TextClassifierOptions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.IOException

class TextClassifierManager(private val context: Context) {

    private var classifier: TextClassifier? = null
    // Use fine-tuned health-risk model: run `python ml/export_to_tflite.py --for_mediapipe` and copy
    // ml/tflite/model.tflite to app src/main/assets/model.tflite (replaces reference bert_classifier.tflite)
    private val modelName = "model.tflite"

    suspend fun loadModel(): Boolean = withContext(Dispatchers.IO) {
        try {
            // MobileBERT is small (~25MB), so we can theoretically load from assets directly
            // depending on API, but copying is safer for alignment issues.
            val modelFile = File(context.filesDir, modelName)
            if (!modelFile.exists()) {
                Log.d("BERTManager", "Copying MobileBERT model...")
                context.assets.open(modelName).use { input ->
                    FileOutputStream(modelFile).use { output ->
                        input.copyTo(output)
                    }
                }
            }

            Log.d("BERTManager", "Initializing TextClassifier...")
            val baseOptions = BaseOptions.builder()
                .setModelAssetPath(modelFile.absolutePath)
                .build()

            val options = TextClassifierOptions.builder()
                .setBaseOptions(baseOptions)
                .build()

            classifier = TextClassifier.createFromOptions(context, options)
            Log.d("BERTManager", "TextClassifier ready.")
            true
        } catch (e: Exception) {
            Log.e("BERTManager", "Init Failed", e)
            false
        }
    }

    fun classify(text: String): Flow<String> = flow {
        if (classifier == null) {
            emit("Error: Model not loaded.")
            return@flow
        }
        try {
            val results = withContext(Dispatchers.IO) {
                classifier?.classify(text)
            }

            // Format results
            val topResult = results?.classificationResult()?.classifications()?.firstOrNull()?.categories()?.firstOrNull()
            val category = topResult?.categoryName() ?: "Unknown"
            val score = topResult?.score() ?: 0f

            emit("Analysis: $category\nConfidence: ${"%.2f".format(score)}")
        } catch (e: Exception) {
            emit("Error: ${e.message}")
        }
    }

    fun cleanup() {
        classifier?.close()
        classifier = null
    }
}
