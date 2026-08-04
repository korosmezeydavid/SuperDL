package com.superdl.launcher.light

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.MotionEvent
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
class LightDetectorActivity : AppCompatActivity() {

    private lateinit var previewView: PreviewView
    private lateinit var tvLevel: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private var imageAnalysis: ImageAnalysis? = null

    private val tonePlayer = LightTonePlayer()
    private val lastUiUpdate = AtomicLong(0L)
    private var lastSpokenBand = -1

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_light_detector)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        previewView = findViewById(R.id.lightPreview)
        CameraStabilityHelper.configurePreviewView(previewView)
        tvLevel = findViewById(R.id.tvLightLevel)
        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        cameraExecutor = Executors.newSingleThreadExecutor()

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                tts.speak("Minél magasabb a síp, annál erősebb a fény. A legmagasabb hang a legvilágosabb pontot jelzi.")
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                tts.speak("Forgasd lassan a telefont. A hang magassága mutatja a fény erősségét.")
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                tts.speak("Fénydetektor aktív. A kamera a környező fényt méri.")
            },
            onSwipeLeft = { finishDetector() }
        )

        findViewById<View>(R.id.lightRoot).setOnTouchListener { _, event ->
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
        tonePlayer.start()
        tts.speakThen(
            "Fénydetektor bekapcsolva. A síp magassága a fény erősségét jelzi. " +
                "Alacsony hang gyenge fény, magas hang erős fény. Balra húzás: kilépés."
        ) {
            val providerFuture = ProcessCameraProvider.getInstance(this)
            providerFuture.addListener({
                val provider = providerFuture.get()
                val preview = CameraStabilityHelper.buildLightPreview(previewView.surfaceProvider)
                val analysis = CameraStabilityHelper.buildLightImageAnalysis()
                    .build()
                    .also { it.setAnalyzer(cameraExecutor, LightAnalyzer(::onLuminance)) }
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

    private fun onLuminance(value: Int) {
        tonePlayer.update(value)
        val now = System.currentTimeMillis()
        if (now - lastUiUpdate.get() < 120L) return
        lastUiUpdate.set(now)
        val freq = tonePlayer.luminanceToFrequency(value)
        if (isFinishing || isDestroyed) return
        runOnUiThread {
            if (isFinishing || isDestroyed) return@runOnUiThread
            tvLevel.text = getString(R.string.light_detector_level, value, freq)
        }
        val band = when {
            value < 40 -> 0
            value < 90 -> 1
            value < 150 -> 2
            value < 210 -> 3
            else -> 4
        }
        if (band != lastSpokenBand && value > 25) {
            lastSpokenBand = band
            val label = when (band) {
                0 -> "Nagyon gyenge fény"
                1 -> "Gyenge fény"
                2 -> "Közepes fény"
                3 -> "Erős fény"
                else -> "Nagyon erős fény"
            }
            tts.speakAdd("$label. $value százalék.")
        }
    }

    private fun finishDetector() {
        sounds.play(SoundType.SWIPE_LEFT)
        tts.speak("Fénydetektor leállítva.")
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
                tts.speakThen("Kamera engedély szükséges a fénydetektorhoz.") { finish() }
            }
        }
    }

    override fun onDestroy() {
        tonePlayer.stop()
        imageAnalysis?.clearAnalyzer()
        imageAnalysis = null
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    @ExperimentalGetImage
    private class LightAnalyzer(
        private val onLuminance: (Int) -> Unit
    ) : ImageAnalysis.Analyzer {
        override fun analyze(imageProxy: ImageProxy) {
            try {
                val plane = imageProxy.planes.firstOrNull()
                if (plane != null) {
                    val buffer = plane.buffer
                    val data = ByteArray(buffer.remaining())
                    buffer.get(data)
                    var sum = 0L
                    for (b in data) {
                        sum += b.toInt() and 0xFF
                    }
                    val avg = if (data.isNotEmpty()) (sum / data.size).toInt() else 0
                    onLuminance(avg)
                }
            } catch (_: OutOfMemoryError) {
                // Frame dropped – keep scanning resilient.
            } finally {
                imageProxy.close()
            }
        }
    }

    companion object {
        private const val REQ_CAMERA = 7101
    }
}