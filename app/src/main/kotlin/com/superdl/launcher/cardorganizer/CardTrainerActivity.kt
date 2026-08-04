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
import com.superdl.launcher.locationwatch.VisualFingerprint
import com.superdl.launcher.tts.TtsManager
import com.superdl.launcher.util.postWhenAlive
import com.superdl.launcher.voice.VoiceInput
import java.util.UUID
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

@ExperimentalGetImage
class CardTrainerActivity : AppCompatActivity() {

    private enum class CaptureStep { FRONT, BACK, NAMING }

    private lateinit var tvStatus: TextView
    private lateinit var sounds: SoundFeedback
    private lateinit var tts: TtsManager
    private lateinit var voiceInput: VoiceInput
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private val mainHandler = Handler(Looper.getMainLooper())

    private val capturing = AtomicBoolean(false)
    private val memoryFailureHandled = AtomicBoolean(false)
    private val lastBufferFrameAt = AtomicLong(0L)
    private val latestBitmap = AtomicReference<Bitmap?>(null)
    private var imageAnalysis: ImageAnalysis? = null
    private var lastBackPressAt = 0L
    private var step = CaptureStep.FRONT
    private var cardId = ""
    private var frontHash = ""
    private var backHash = ""
    private var frontThumbPath: String? = null
    private var backThumbPath: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_card_trainer)
        title = getString(R.string.card_trainer_title)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvCardTrainerStatus)
        CameraStabilityHelper.configurePreviewView(findViewById(R.id.cardTrainerPreview))
        sounds = SoundFeedback(this)
        tts = TtsManager(this)
        voiceInput = VoiceInput(this)
        cameraExecutor = Executors.newSingleThreadExecutor()

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                if (step == CaptureStep.BACK && frontHash.isNotBlank()) {
                    promptForCardName()
                }
            },
            onSwipeDown = { sounds.play(SoundType.SWIPE_DOWN) },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                captureCurrentSide()
            },
            onSwipeLeft = { finishTrainer() }
        )

        findViewById<View>(R.id.cardTrainerRoot).setOnTouchListener { view, event ->
            gestureListener.detector.onTouchEvent(event)
            if (event.action == android.view.MotionEvent.ACTION_UP) view.performClick()
            true
        }
        findViewById<Button>(R.id.btnCardTrainerExit).setOnClickListener { finishTrainer() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val now = System.currentTimeMillis()
                if (now - lastBackPressAt < 2000L) finishTrainer()
                else {
                    lastBackPressAt = now
                    tts.speak(getString(R.string.card_trainer_back_hint))
                }
            }
        })

        if (hasCameraPermission()) {
            initializeTrainer()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
        }
    }

    private fun initializeTrainer() {
        cardId = UUID.randomUUID().toString()
        step = CaptureStep.FRONT
        setStatusText(getString(R.string.card_trainer_status_front))
        tts.runWhenReady { tts.speak(getString(R.string.card_trainer_intro_front)) }
        startCamera()
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val preview = CameraStabilityHelper.buildLightPreview(
                findViewById<PreviewView>(R.id.cardTrainerPreview).surfaceProvider
            )
            imageAnalysis = CameraStabilityHelper.buildLightImageAnalysis()
                .build()
                .also { it.setAnalyzer(cameraExecutor, FrameBufferAnalyzer()) }
            try {
                provider.unbindAll()
                provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageAnalysis)
            } catch (_: Exception) {
                sounds.play(SoundType.ACTION_ERROR)
                setStatusText(getString(R.string.card_trainer_camera_error))
                tts.runWhenReady { tts.speak(getString(R.string.card_trainer_camera_error)) }
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun captureCurrentSide() {
        if (capturing.get()) return
        val bitmap = latestBitmap.get()
        if (bitmap == null || bitmap.isRecycled) {
            tts.speak(getString(R.string.card_trainer_no_frame))
            return
        }
        capturing.set(true)
        val captureBitmap = try {
            bitmap.copy(Bitmap.Config.ARGB_8888, false)
        } catch (_: OutOfMemoryError) {
            capturing.set(false)
            handleMemoryFailure()
            return
        } ?: run {
            capturing.set(false)
            tts.speak(getString(R.string.card_trainer_capture_error))
            return
        }
        postWhenAlive {
            onSideCaptured(captureBitmap)
            if (!captureBitmap.isRecycled) captureBitmap.recycle()
            capturing.set(false)
        }
    }

    private fun onSideCaptured(bitmap: Bitmap) {
        if (bitmap.isRecycled) {
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.card_trainer_capture_error))
            return
        }
        val hash = runCatching { VisualFingerprint.compute(bitmap) }.getOrDefault("")
        if (hash.isBlank()) {
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.card_trainer_capture_error))
            return
        }
        when (step) {
            CaptureStep.FRONT -> {
                frontHash = hash
                frontThumbPath = CardStore.saveThumbnail(this, cardId, "front", bitmap)
                step = CaptureStep.BACK
                sounds.play(SoundType.ACTION_OK)
                val message = getString(R.string.card_trainer_front_saved)
                setStatusText(message)
                tts.speak(message)
            }
            CaptureStep.BACK -> {
                backHash = hash
                backThumbPath = CardStore.saveThumbnail(this, cardId, "back", bitmap)
                step = CaptureStep.NAMING
                sounds.play(SoundType.ACTION_OK)
                val message = getString(R.string.card_trainer_back_saved)
                setStatusText(message)
                tts.speak(message)
                promptForCardName()
            }
            CaptureStep.NAMING -> Unit
        }
    }

    private fun promptForCardName() {
        if (!voiceInput.isAvailable()) {
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.card_trainer_voice_unavailable))
            return
        }
        setStatusText(getString(R.string.card_trainer_status_naming))
        voiceInput.listen(
            prompt = getString(R.string.card_trainer_name_prompt),
            speakFirst = { prompt, onDone -> tts.speakThen(prompt) { onDone() } },
            onResult = { spoken -> saveCard(spoken) },
            onError = {
                sounds.play(SoundType.ACTION_ERROR)
                tts.speak(getString(R.string.card_trainer_name_error))
            }
        )
    }

    private fun saveCard(name: String) {
        val profile = CardProfile(
            id = cardId,
            name = name.trim(),
            createdAt = System.currentTimeMillis(),
            frontVisualHash = frontHash,
            backVisualHash = backHash,
            frontThumbnailPath = frontThumbPath,
            backThumbnailPath = backThumbPath
        )
        val saved = CardStore.add(this, profile)
        if (saved == null) {
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.card_trainer_save_error))
            return
        }
        sounds.play(SoundType.ACTION_OK)
        val message = getString(R.string.card_trainer_saved, saved.name)
        setStatusText(message)
        tts.speak(message)
        finish()
    }

    private fun finishTrainer() {
        voiceInput.cancel()
        sounds.play(SoundType.SWIPE_LEFT)
        tts.speak(getString(R.string.card_trainer_exit))
        finish()
    }

    private fun setStatusText(text: String) {
        postWhenAlive { tvStatus.text = text }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.KEYCODE_VOLUME_DOWN -> {
                if (event?.repeatCount == 0) captureCurrentSide()
                return true
            }
            KeyEvent.KEYCODE_BACK -> {
                onBackPressedDispatcher.onBackPressed()
                return true
            }
        }
        return super.onKeyDown(keyCode, event)
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_CAMERA) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                initializeTrainer()
            } else {
                sounds.play(SoundType.ACTION_ERROR)
                tts.runWhenReady { tts.speak(getString(R.string.card_trainer_permission_denied)) }
                finish()
            }
        }
    }

    private fun handleMemoryFailure() {
        if (!memoryFailureHandled.compareAndSet(false, true)) return
        imageAnalysis?.clearAnalyzer()
        sounds.play(SoundType.ACTION_ERROR)
        tts.speak(getString(R.string.camera_memory_error))
    }

    override fun onDestroy() {
        voiceInput.destroy()
        mainHandler.removeCallbacksAndMessages(null)
        imageAnalysis?.clearAnalyzer()
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        latestBitmap.getAndSet(null)?.recycle()
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    private inner class FrameBufferAnalyzer : ImageAnalysis.Analyzer {
        override fun analyze(imageProxy: ImageProxy) {
            val now = System.currentTimeMillis()
            if (now - lastBufferFrameAt.get() < BUFFER_FRAME_INTERVAL_MS) {
                imageProxy.close()
                return
            }
            lastBufferFrameAt.set(now)
            try {
                val bitmap = imageProxy.toBitmap()
                latestBitmap.getAndSet(bitmap)?.recycle()
            } catch (oom: OutOfMemoryError) {
                latestBitmap.getAndSet(null)?.recycle()
                postWhenAlive { handleMemoryFailure() }
            } catch (_: Exception) {
            } finally {
                imageProxy.close()
            }
        }
    }

    companion object {
        private const val REQ_CAMERA = 7120
        private const val BUFFER_FRAME_INTERVAL_MS = 450L

        fun intent(context: Context): Intent =
            Intent(context, CardTrainerActivity::class.java)
    }
}