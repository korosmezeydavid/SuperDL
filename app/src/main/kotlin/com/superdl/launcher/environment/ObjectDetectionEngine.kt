package com.superdl.launcher.environment

import android.content.Context
import android.graphics.RectF
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.support.common.FileUtil
import org.tensorflow.lite.support.image.ImageProcessor
import org.tensorflow.lite.support.image.TensorImage
import org.tensorflow.lite.support.image.ops.ResizeOp
import java.io.Closeable

class ObjectDetectionEngine(context: Context) : Closeable {

    private val interpreter: Interpreter
    private val labels: List<String>
    private val imageProcessor: ImageProcessor = ImageProcessor.Builder()
        .add(ResizeOp(INPUT_SIZE, INPUT_SIZE, ResizeOp.ResizeMethod.BILINEAR))
        .build()

    private val outputLocations = Array(1) { Array(NUM_DETECTIONS) { FloatArray(4) } }
    private val outputClasses = Array(1) { FloatArray(NUM_DETECTIONS) }
    private val outputScores = Array(1) { FloatArray(NUM_DETECTIONS) }
    private val numDetections = FloatArray(1)

    init {
        val model = FileUtil.loadMappedFile(context, MODEL_FILE)
        interpreter = Interpreter(model, Interpreter.Options().apply { numThreads = 2 })
        labels = FileUtil.loadLabels(context, LABEL_FILE)
    }

    fun detect(tensorImage: TensorImage): List<DetectionResult> {
        val processed = imageProcessor.process(tensorImage)
        val outputs = mapOf(
            0 to outputLocations,
            1 to outputClasses,
            2 to outputScores,
            3 to numDetections
        )
        interpreter.runForMultipleInputsOutputs(arrayOf(processed.buffer), outputs)

        val count = numDetections[0].toInt().coerceIn(0, NUM_DETECTIONS)
        val results = mutableListOf<DetectionResult>()

        for (index in 0 until count) {
            val score = outputScores[0][index]
            if (score < CONFIDENCE_THRESHOLD) continue

            val classIndex = outputClasses[0][index].toInt().coerceIn(0, labels.lastIndex)
            val label = labels[classIndex]
            if (label == "???" || label.isBlank()) continue

            val category = ObjectCategory.fromCocoLabel(label) ?: continue
            val box = outputLocations[0][index]
            val boundingBox = RectF(
                box[1].coerceIn(0f, 1f),
                box[0].coerceIn(0f, 1f),
                box[3].coerceIn(0f, 1f),
                box[2].coerceIn(0f, 1f)
            )
            if (boundingBox.width() <= 0f || boundingBox.height() <= 0f) continue

            results.add(
                DetectionResult(
                    category = category,
                    label = label,
                    confidence = score,
                    boundingBox = boundingBox
                )
            )
        }

        return results.sortedByDescending { it.confidence }
    }

    override fun close() {
        interpreter.close()
    }

    companion object {
        private const val MODEL_FILE = "mobilenet_ssd_v1.tflite"
        private const val LABEL_FILE = "coco_labels.txt"
        private const val INPUT_SIZE = 300
        private const val NUM_DETECTIONS = 10
        private const val CONFIDENCE_THRESHOLD = 0.45f
    }
}