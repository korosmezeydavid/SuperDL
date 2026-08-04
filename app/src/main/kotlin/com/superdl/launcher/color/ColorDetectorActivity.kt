package com.superdl.launcher.color

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.superdl.launcher.R
import com.superdl.launcher.camera.CameraStabilityHelper
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

@ExperimentalGetImage
class ColorDetectorActivity : AppCompatActivity() {

    private lateinit var tvResult: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private var imageAnalysis: ImageAnalysis? = null

    private val lastUiUpdate = AtomicLong(0L)
    private var lastSpokenColor: String? = null
    private var latestResult: ColorClassifier.Result? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_color_detector)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvResult = findViewById(R.id.tvColorResult)
        CameraStabilityHelper.configurePreviewView(findViewById(R.id.colorPreview))
        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        cameraExecutor = Executors.newSingleThreadExecutor()

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                speakLatest("Ismétlés.")
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                tts.speak("Tartsd a telefont a felület felé, kb. 20–30 centire. Lassan mozgasd, ha több pontot szeretnél mérni.")
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                speakLatest("Aktuális szín.")
            },
            onSwipeLeft = { finishDetector() }
        )

        findViewById<View>(R.id.colorRoot).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = finishDetector()
        })

        if (hasCameraPermission()) {
            startDetector()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
        }
    }

    private fun startDetector() {
        tts.speakThen(
            "Színfelismerő bekapcsolva. Mutasd a kamerának a felületet. " +
                "A program felolvassa a domináns színt. Jobbra söprés: ismétlés. Balra: kilépés."
        ) {
            val providerFuture = ProcessCameraProvider.getInstance(this)
            providerFuture.addListener({
                val provider = providerFuture.get()
                val preview = CameraStabilityHelper.buildLightPreview(
                    findViewById<PreviewView>(R.id.colorPreview).surfaceProvider
                )
                val analysis = CameraStabilityHelper.buildLightImageAnalysis()
                    .build()
                    .also { it.setAnalyzer(cameraExecutor, ColorAnalyzer(::onSample)) }
                imageAnalysis = analysis
                try {
                    provider.unbindAll()
                    provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
                } catch (_: Exception) {
                    sounds.play(SoundType.ACTION_ERROR)
                    tts.speakThen("A kamera nem indítható.") { finish() }
                }
            }, ContextCompat.getMainExecutor(this))
        }
    }

    private fun onSample(r: Int, g: Int, b: Int) {
        val result = ColorClassifier.classify(r, g, b)
        latestResult = result
        val now = System.currentTimeMillis()
        if (now - lastUiUpdate.get() < 500L) return
        lastUiUpdate.set(now)
        if (isFinishing || isDestroyed) return
        runOnUiThread {
            if (isFinishing || isDestroyed) return@runOnUiThread
            tvResult.text = getString(R.string.color_detector_result, result.name, result.brightnessPercent)
        }
        if (result.name != lastSpokenColor) {
            lastSpokenColor = result.name
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                tts.speakAdd("${result.name}. Fényerő ${result.brightnessPercent} százalék.")
            }
        }
    }

    private fun speakLatest(prefix: String) {
        val result = latestResult
        if (result == null) {
            tts.speak("$prefix Még nincs mérés, tartsd a kamerát a felület felé.")
        } else {
            tts.speak("$prefix ${result.name}. Fényerő ${result.brightnessPercent} százalék.")
        }
    }

    private fun finishDetector() {
        sounds.play(SoundType.SWIPE_LEFT)
        tts.speak("Színfelismerő leállítva.")
        finish()
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_CAMERA) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                startDetector()
            } else {
                sounds.play(SoundType.ACTION_ERROR)
                tts.speakThen("Kamera engedély szükséges a színfelismerőhöz.") { finish() }
            }
        }
    }

    override fun onDestroy() {
        imageAnalysis?.clearAnalyzer()
        imageAnalysis = null
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    @ExperimentalGetImage
    private class ColorAnalyzer(
        private val onRgb: (Int, Int, Int) -> Unit
    ) : ImageAnalysis.Analyzer {
        override fun analyze(imageProxy: ImageProxy) {
            try {
                val image = imageProxy.image ?: return
                val planes = image.planes
                if (planes.size < 3) return
                val width = image.width
                val height = image.height
                val yBuf = planes[0].buffer
                val uBuf = planes[1].buffer
                val vBuf = planes[2].buffer
                val yRow = planes[0].rowStride
                val uvRow = planes[1].rowStride
                val uvPixel = planes[1].pixelStride

                var sumR = 0L
                var sumG = 0L
                var sumB = 0L
                var count = 0
                val xStart = (width * 0.35f).toInt()
                val xEnd = (width * 0.65f).toInt()
                val yStart = (height * 0.35f).toInt()
                val yEnd = (height * 0.65f).toInt()

                for (y in yStart until yEnd step 4) {
                    for (x in xStart until xEnd step 4) {
                        val yIndex = y * yRow + x
                        val uvIndex = (y / 2) * uvRow + (x / 2) * uvPixel
                        if (yIndex >= yBuf.limit() || uvIndex + 1 >= uBuf.limit()) continue
                        val yVal = yBuf.get(yIndex).toInt() and 0xFF
                        val uVal = uBuf.get(uvIndex).toInt() and 0xFF
                        val vVal = vBuf.get(uvIndex).toInt() and 0xFF
                        val rgb = yuvToRgb(yVal, uVal, vVal)
                        sumR += rgb.first
                        sumG += rgb.second
                        sumB += rgb.third
                        count++
                    }
                }
                if (count > 0) {
                    onRgb(
                        (sumR / count).toInt(),
                        (sumG / count).toInt(),
                        (sumB / count).toInt()
                    )
                }
            } catch (_: OutOfMemoryError) {
                // Frame dropped – keep scanning resilient.
            } finally {
                imageProxy.close()
            }
        }

        private fun yuvToRgb(y: Int, u: Int, v: Int): Triple<Int, Int, Int> {
            val y2 = y - 16
            val u2 = u - 128
            val v2 = v - 128
            var r = (1.164f * y2 + 1.596f * v2).toInt()
            var g = (1.164f * y2 - 0.392f * u2 - 0.813f * v2).toInt()
            var b = (1.164f * y2 + 2.017f * u2).toInt()
            return Triple(
                r.coerceIn(0, 255),
                g.coerceIn(0, 255),
                b.coerceIn(0, 255)
            )
        }
    }

    companion object {
        private const val REQ_CAMERA = 7102
    }
}