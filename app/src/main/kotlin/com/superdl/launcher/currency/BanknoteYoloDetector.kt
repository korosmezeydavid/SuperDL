package com.superdl.launcher.currency

import android.content.Context
import android.graphics.Bitmap
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.support.common.FileUtil
import org.tensorflow.lite.support.image.ImageProcessor
import org.tensorflow.lite.support.image.TensorImage
import org.tensorflow.lite.support.image.ops.ResizeOp
import org.tensorflow.lite.support.common.ops.NormalizeOp
import java.io.Closeable
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Stage 1 – YOLO banknote localization (Ultralytics TFLite, typically 640×640). */
internal class BanknoteYoloDetector private constructor(
    private val interpreter: Interpreter,
    private val labels: List<String>,
    private val inputWidth: Int,
    private val inputHeight: Int,
    private val outputShape: IntArray,
    /** Reused every frame to avoid multi-MB allocation on the hot path. */
    private val output3d: Array<Array<FloatArray>>,
    private val flatOutput: FloatArray,
    private val channels: Int,
    private val anchors: Int
) : Closeable {

    private val imageProcessor: ImageProcessor = ImageProcessor.Builder()
        .add(ResizeOp(inputHeight, inputWidth, ResizeOp.ResizeMethod.BILINEAR))
        // KRITIKUS: az Ultralytics YOLO FP32 TFLite a bemenetet 0-1 tartományban
        // várja (pixel / 255). NormalizeOp(0, 255) = (pixel - 0) / 255. Enélkül a
        // modell 0-255 nyers pixeleket kap, teljesen más eloszlást lát, mint amin
        // tanult, és FUT, DE ROSSZAT MOND.
        .add(NormalizeOp(0f, 255f))
        .build()

    // TensorImage + direct buffer: reuse to cut GC pressure on low-end devices.
    private val tensorImage = TensorImage(DataType.FLOAT32)

    fun detect(bitmap: Bitmap): List<BanknoteDetection> {
        if (bitmap.isRecycled || bitmap.width <= 0 || bitmap.height <= 0) return emptyList()

        return try {
            tensorImage.load(bitmap)
            val processed = imageProcessor.process(tensorImage)

            // A modell kimenete tipikusan [1, 10, 8400] (3D). A TFLite szigorúan
            // alak-egyeztet, ezért a kimeneti buffernek is pontosan ilyen alakúnak
            // kell lennie. A buffer ÚJRAHASZNÁLT (nem allokálunk frame-enként).
            interpreter.run(processed.buffer, output3d)

            // Lapítás: [channels][anchors] -> egyetlen FloatArray, csatorna-folytonosan.
            for (c in 0 until channels) {
                System.arraycopy(output3d[0][c], 0, flatOutput, c * anchors, anchors)
            }

            YoloOutputParser.parse(
                output = arrayOf(flatOutput),
                outputShape = outputShape,
                labels = labels,
                confThreshold = CONFIDENCE_THRESHOLD,
                iouThreshold = IOU_THRESHOLD,
                maxDetections = MAX_DETECTIONS,
                modelInputWidth = inputWidth,
                modelInputHeight = inputHeight
            )
        } catch (e: Exception) {
            android.util.Log.e(
                "SDL_CASH",
                "YOLO inference hiba: ${e.javaClass.simpleName}: ${e.message}"
            )
            emptyList()
        } catch (e: OutOfMemoryError) {
            android.util.Log.e("SDL_CASH", "YOLO OOM: ${e.message}")
            System.gc()
            emptyList()
        }
    }

    fun bestDetection(bitmap: Bitmap): BanknoteDetection? =
        detect(bitmap)
            .asSequence()
            .filter { it.areaFraction >= MIN_AREA_FRACTION }
            .maxByOrNull { it.confidence * (0.75f + it.areaFraction.coerceAtMost(0.5f)) }

    override fun close() {
        interpreter.close()
    }

    companion object {
        private const val MODEL_FILE = "huf_banknote_detector.tflite"
        private const val LABEL_FILE = "huf_banknote_detector_labels.txt"
        private const val CONFIDENCE_THRESHOLD = 0.55f
        private const val IOU_THRESHOLD = 0.45f
        private const val MAX_DETECTIONS = 3
        private const val MIN_AREA_FRACTION = 0.06f
        private const val DEFAULT_INPUT = 640

        fun tryCreate(context: Context): BanknoteYoloDetector? {
            return try {
                val assetManager = context.assets
                assetManager.open(MODEL_FILE).close()
                val model = FileUtil.loadMappedFile(context, MODEL_FILE)
                val interpreter = Interpreter(
                    model,
                    Interpreter.Options().apply {
                        numThreads = 2
                        // NNAPI KIKAPCSOLVA. Az Ulefone Armor 24 NNAPI-gyorsítója
                        // nem tudja lefordítani ezt a YOLO-modellt (a 378. rétegnél
                        // ANEURALNETWORKS_BAD_DATA hibával elhasal), ezért a teljes
                        // detektor-betöltés elbukott, és a régi classifier futott
                        // helyette -> ez okozta a rossz/hallucinált címleteket.
                        // CPU-n (XNNPACK) a modell stabilan fut, ~20 fps bőven elég.
                        setUseNNAPI(false)
                    }
                )
                val labels = FileUtil.loadLabels(context, LABEL_FILE)
                if (labels.isEmpty()) {
                    interpreter.close()
                    return null
                }

                val inputTensor = interpreter.getInputTensor(0)
                val inputShape = inputTensor.shape()
                val inputHeight = if (inputShape.size >= 3) inputShape[1] else DEFAULT_INPUT
                val inputWidth = if (inputShape.size >= 3) inputShape[2] else DEFAULT_INPUT

                val outputTensor = interpreter.getOutputTensor(0)
                val outputShape = outputTensor.shape()
                // Tipikus Ultralytics raw head: [1, 4+nc, anchors]
                val channels = if (outputShape.size == 3) outputShape[1] else (4 + labels.size)
                val anchors = if (outputShape.size == 3) outputShape[2] else {
                    val total = outputShape.fold(1) { acc, dim -> acc * dim }
                    (total / channels).coerceAtLeast(1)
                }
                val output3d = Array(1) { Array(channels) { FloatArray(anchors) } }
                val flatOutput = FloatArray(channels * anchors)

                BanknoteYoloDetector(
                    interpreter = interpreter,
                    labels = labels,
                    inputWidth = inputWidth,
                    inputHeight = inputHeight,
                    outputShape = outputShape,
                    output3d = output3d,
                    flatOutput = flatOutput,
                    channels = channels,
                    anchors = anchors
                )
            } catch (e: Exception) {
                android.util.Log.e(
                    "SDL_CASH",
                    "Detektor betoltes SIKERTELEN: ${e.javaClass.simpleName}: ${e.message}",
                    e
                )
                null
            }
        }
    }
}
