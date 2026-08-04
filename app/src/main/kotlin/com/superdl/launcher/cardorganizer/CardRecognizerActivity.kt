package com.superdl.launcher.cardorganizer

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.View
import android.widget.Button
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
import com.superdl.launcher.locationwatch.LocationAnnounceDebouncer
import com.superdl.launcher.locationwatch.VisualFingerprint
import com.superdl.launcher.tts.TtsManager
import com.superdl.launcher.util.postWhenAlive
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

@ExperimentalGetImage
class CardRecognizerActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var sounds: SoundFeedback
    private lateinit var tts: TtsManager
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private val mainHandler = Handler(Looper.getMainLooper())
    private val debouncer = LocationAnnounceDebouncer(cooldownMs = 4_500L)

    private val scanning = AtomicBoolean(false)
    private val memoryFailureHandled = AtomicBoolean(false)
    private val lastFrameProcessedAt = AtomicLong(0L)
    private var imageAnalysis: ImageAnalysis? = null
    private var cards: List<CardProfile> = emptyList()
    private var lastBackPressAt = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_card_recognizer)
        title = getString(R.string.card_recognizer_title)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvCardRecognizerStatus)
        CameraStabilityHelper.configurePreviewView(findViewById(R.id.cardRecognizerPreview))
        sounds = SoundFeedback(this)
        tts = TtsManager(this)
        cameraExecutor = Executors.newSingleThreadExecutor()
        cards = CardStore.getAll(this)

        if (cards.isEmpty()) {
            tts.runWhenReady {
                tts.speakThen(getString(R.string.card_recognizer_no_cards)) { finish() }
            }
            return
        }

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { sounds.play(SoundType.SWIPE_UP) },
            onSwipeDown = { sounds.play(SoundType.SWIPE_DOWN) },
            onSwipeRight = { sounds.play(SoundType.SWIPE_RIGHT) },
            onSwipeLeft = { finishRecognizer() }
        )

        findViewById<View>(R.id.cardRecognizerRoot).setOnTouchListener { view, event ->
            gestureListener.detector.onTouchEvent(event)
            if (event.action == android.view.MotionEvent.ACTION_UP) view.performClick()
            true
        }
        findViewById<Button>(R.id.btnCardRecognizerExit).setOnClickListener { finishRecognizer() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val now = System.currentTimeMillis()
                if (now - lastBackPressAt < 2000L) finishRecognizer()
                else {
                    lastBackPressAt = now
                    tts.speak(getString(R.string.card_recognizer_back_hint))
                }
            }
        })

        if (hasCameraPermission()) initializeRecognizer()
        else ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
    }

    private fun initializeRecognizer() {
        setStatusText(getString(R.string.card_recognizer_status_scanning))
        tts.runWhenReady {
            tts.speak(getString(R.string.card_recognizer_intro, cards.size))
        }
        scanning.set(true)
        startCamera()
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val preview = CameraStabilityHelper.buildLightPreview(
                findViewById<PreviewView>(R.id.cardRecognizerPreview).surfaceProvider
            )
            imageAnalysis = CameraStabilityHelper.buildLightImageAnalysis()
                .build()
                .also { it.setAnalyzer(cameraExecutor, FrameAnalyzer()) }
            try {
                provider.unbindAll()
                provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageAnalysis)
            } catch (_: Exception) {
                sounds.play(SoundType.ACTION_ERROR)
                tts.runWhenReady { tts.speak(getString(R.string.card_recognizer_camera_error)) }
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun onFrameAnalyzed(bitmap: Bitmap) {
        if (!scanning.get() || bitmap.isRecycled) return
        val hash = runCatching { VisualFingerprint.compute(bitmap) }.getOrDefault("")
        if (hash.isBlank()) return
        val matched = CardStore.matchCard(cards, hash) ?: return
        if (!debouncer.shouldAnnounce("card:${matched.id}")) return
        val message = getString(R.string.card_recognizer_match, matched.name)
        postWhenAlive {
            sounds.play(SoundType.ACTION_OK)
            setStatusText(message)
            tts.speak(message)
        }
    }

    private fun finishRecognizer() {
        scanning.set(false)
        debouncer.reset()
        sounds.play(SoundType.SWIPE_LEFT)
        tts.speakThen(getString(R.string.card_recognizer_exit)) { finish() }
    }

    private fun setStatusText(text: String) {
        postWhenAlive { tvStatus.text = text }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            onBackPressedDispatcher.onBackPressed()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_CAMERA) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                initializeRecognizer()
            } else {
                sounds.play(SoundType.ACTION_ERROR)
                tts.runWhenReady { tts.speak(getString(R.string.card_recognizer_permission_denied)) }
                finish()
            }
        }
    }

    private fun handleMemoryFailure() {
        if (!memoryFailureHandled.compareAndSet(false, true)) return
        scanning.set(false)
        imageAnalysis?.clearAnalyzer()
        sounds.play(SoundType.ACTION_ERROR)
        tts.speak(getString(R.string.camera_memory_error))
    }

    override fun onDestroy() {
        scanning.set(false)
        mainHandler.removeCallbacksAndMessages(null)
        imageAnalysis?.clearAnalyzer()
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    private inner class FrameAnalyzer : ImageAnalysis.Analyzer {
        override fun analyze(imageProxy: ImageProxy) {
            if (!scanning.get()) {
                imageProxy.close()
                return
            }
            val now = System.currentTimeMillis()
            if (now - lastFrameProcessedAt.get() < FRAME_INTERVAL_MS) {
                imageProxy.close()
                return
            }
            lastFrameProcessedAt.set(now)
            try {
                val bitmap = imageProxy.toBitmap()
                val frameCopy = try {
                    bitmap.copy(Bitmap.Config.ARGB_8888, false)
                } catch (_: OutOfMemoryError) {
                    bitmap.recycle()
                    postWhenAlive { handleMemoryFailure() }
                    return
                } ?: return
                bitmap.recycle()
                onFrameAnalyzed(frameCopy)
                if (!frameCopy.isRecycled) frameCopy.recycle()
            } catch (oom: OutOfMemoryError) {
                postWhenAlive { handleMemoryFailure() }
            } catch (_: Exception) {
            } finally {
                imageProxy.close()
            }
        }
    }

    companion object {
        private const val REQ_CAMERA = 7121
        private const val FRAME_INTERVAL_MS = 1_800L

        fun intent(context: Context): Intent =
            Intent(context, CardRecognizerActivity::class.java)
    }
}