package com.superdl.launcher.textreader

import android.Manifest
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
import com.superdl.launcher.tts.TtsManager
import com.superdl.launcher.util.postWhenAlive
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

@ExperimentalGetImage
class TextReaderActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var sounds: SoundFeedback
    private lateinit var tts: TtsManager
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private val mainHandler = Handler(Looper.getMainLooper())

    private lateinit var mode: TextReaderMode
    private var recognitionEngine: TextRecognitionEngine? = null
    private val debouncer = TextAnnounceDebouncer()
    private val changeDetector = TextChangeDetector()
    private val memoryFailureHandled = AtomicBoolean(false)
    private val scanning = AtomicBoolean(false)
    private val scanPaused = AtomicBoolean(false)
    private val lastFrameProcessedAt = AtomicLong(0L)
    private val latestBitmap = AtomicReference<Bitmap?>(null)
    private val latestSpeechText = AtomicReference("")
    private val pendingSpeechText = AtomicReference<String?>(null)
    private var imageAnalysis: ImageAnalysis? = null
    private var lastBackPressAt = 0L
    private var chunks: List<String> = emptyList()
    private var chunkIndex = 0
    private var consecutiveOcrFailures = 0

    private val isContinuousMode: Boolean
        get() = mode == TextReaderMode.CONTINUOUS

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_text_reader)
        mode = TextReaderMode.fromExtra(intent.getStringExtra(TextReaderMode.EXTRA_MODE))
        title = mode.menuLabel
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvTextReaderStatus)
        CameraStabilityHelper.configurePreviewView(findViewById(R.id.textReaderPreview))
        sounds = SoundFeedback(this)
        tts = TtsManager(this)
        cameraExecutor = Executors.newSingleThreadExecutor()

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                onSwipeUpAction()
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                onSwipeDownAction()
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                onSwipeRightAction()
            },
            onSwipeLeft = { finishReader() }
        )

        findViewById<View>(R.id.textReaderRoot).setOnTouchListener { view, event ->
            gestureListener.detector.onTouchEvent(event)
            if (event.action == android.view.MotionEvent.ACTION_UP) {
                view.performClick()
            }
            true
        }

        findViewById<Button>(R.id.btnTextReaderExit).setOnClickListener { finishReader() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val now = System.currentTimeMillis()
                if (now - lastBackPressAt < 2000L) {
                    finishReader()
                } else {
                    lastBackPressAt = now
                    tts.speak("Kilépéshez nyomd meg újra a vissza gombot, vagy balra söpörj.")
                }
            }
        })

        if (hasCameraPermission()) {
            initializeReader()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
        }
    }

    private fun initializeReader() {
        recognitionEngine = TextRecognitionEngine()
        setStatusText(getString(R.string.text_reader_status_active, mode.menuLabel))
        tts.runWhenReady { tts.speak(introTextForMode()) }
        scanning.set(true)
        scanPaused.set(false)
        startCamera()
    }

    private fun introTextForMode(): String = when (mode) {
        TextReaderMode.MEDICATION_BOX -> getString(R.string.text_reader_intro_medication)
        TextReaderMode.PRODUCT_LABEL -> getString(R.string.text_reader_intro_label)
        TextReaderMode.GENERAL_TEXT -> getString(R.string.text_reader_intro_general)
        TextReaderMode.CONTINUOUS -> getString(R.string.text_reader_intro_continuous)
    }

    private fun helpTextForMode(): String = when (mode) {
        TextReaderMode.MEDICATION_BOX -> getString(R.string.text_reader_help_medication)
        TextReaderMode.PRODUCT_LABEL -> getString(R.string.text_reader_help_label)
        TextReaderMode.GENERAL_TEXT -> getString(R.string.text_reader_help_general)
        TextReaderMode.CONTINUOUS -> getString(R.string.text_reader_help_continuous)
    }

    private fun onSwipeUpAction() {
        if (isContinuousMode && chunks.isNotEmpty()) {
            speakChunkAt(chunkIndex, announceProgress = false)
        } else {
            repeatLastText()
        }
    }

    private fun onSwipeDownAction() {
        if (isContinuousMode && chunks.isNotEmpty()) {
            if (chunkIndex < chunks.lastIndex) {
                chunkIndex++
                speakChunkAt(chunkIndex, announceProgress = true)
            } else {
                tts.speak(getString(R.string.text_reader_chunk_end))
            }
        } else {
            tts.speak(helpTextForMode())
        }
    }

    private fun onSwipeRightAction() {
        if (isContinuousMode) {
            toggleContinuousPause()
        } else {
            triggerManualRead()
        }
    }

    private fun toggleContinuousPause() {
        val paused = scanPaused.get()
        scanPaused.set(!paused)
        if (!paused) {
            pendingSpeechText.set(null)
            tts.speak(getString(R.string.text_reader_continuous_paused))
            setStatusText(getString(R.string.text_reader_continuous_paused))
        } else {
            changeDetector.reset()
            consecutiveOcrFailures = 0
            tts.speak(getString(R.string.text_reader_continuous_resumed))
            setStatusText(getString(R.string.text_reader_status_scanning))
        }
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            try {
                val provider = providerFuture.get()
                val preview = CameraStabilityHelper.buildLightPreview(
                    findViewById<PreviewView>(R.id.textReaderPreview).surfaceProvider
                )
                imageAnalysis = CameraStabilityHelper.buildLightImageAnalysis()
                    .build()
                    .also { analysis ->
                        analysis.setAnalyzer(cameraExecutor, FrameAnalyzer())
                    }
                provider.unbindAll()
                provider.bindToLifecycle(
                    this,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    imageAnalysis
                )
            } catch (_: Exception) {
                sounds.play(SoundType.ACTION_ERROR)
                setStatusText(getString(R.string.text_reader_camera_error))
                tts.runWhenReady { tts.speak(getString(R.string.text_reader_camera_error)) }
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun setStatusText(text: String) {
        postWhenAlive { tvStatus.text = text }
    }

    private fun onRecognizedText(raw: String, forceAnnounce: Boolean) {
        try {
            consecutiveOcrFailures = 0
            val speech = TextFormatter.formatForMode(raw, mode)
            if (speech.isBlank()) {
                if (forceAnnounce) {
                    tts.speak(getString(R.string.text_reader_no_text))
                    setStatusText(getString(R.string.text_reader_status_scanning))
                }
                return
            }

            latestSpeechText.set(speech)

            if (isContinuousMode) {
                handleContinuousRecognition(speech, forceAnnounce)
                return
            }

            if (!forceAnnounce && !debouncer.shouldAutoAnnounce(speech)) {
                return
            }
            if (forceAnnounce) {
                debouncer.markAnnounced(speech)
            }
            announceText(speech)
        } catch (oom: OutOfMemoryError) {
            latestBitmap.getAndSet(null)?.recycle()
            System.gc()
            handleMemoryFailure()
        } catch (_: Exception) {
            registerOcrFailure()
        }
    }

    private fun registerOcrFailure() {
        consecutiveOcrFailures++
        if (!isContinuousMode || consecutiveOcrFailures < MAX_CONSECUTIVE_OCR_FAILURES) return
        scanPaused.set(true)
        consecutiveOcrFailures = 0
        pendingSpeechText.set(null)
        tts.speak(getString(R.string.text_reader_continuous_error_pause))
        setStatusText(getString(R.string.text_reader_continuous_error_pause))
    }

    private fun handleContinuousRecognition(speech: String, forceAnnounce: Boolean) {
        if (scanPaused.get() && !forceAnnounce) return

        if (forceAnnounce) {
            applyChunks(speech)
            announceText(buildContinuousSpeech())
            changeDetector.markAsAnnounced(speech)
            debouncer.markAnnounced(speech)
            return
        }

        if (!changeDetector.isMeaningfulChange(speech) &&
            !debouncer.shouldAutoAnnounce(speech)
        ) {
            return
        }
        debouncer.markAnnounced(speech)
        applyChunks(speech)
        queueOrAnnounce(buildContinuousSpeech())
    }

    private fun applyChunks(speech: String) {
        chunks = TextOcrChunker.split(speech)
        chunkIndex = 0
    }

    private fun buildContinuousSpeech(): String {
        if (chunks.isEmpty()) return latestSpeechText.get()
        val chunk = chunks[chunkIndex]
        return if (chunks.size > 1) {
            getString(R.string.text_reader_chunk_progress, chunkIndex + 1, chunks.size) + ". " + chunk
        } else {
            chunk
        }
    }

    private fun speakChunkAt(index: Int, announceProgress: Boolean) {
        if (chunks.isEmpty()) {
            repeatLastText()
            return
        }
        chunkIndex = index.coerceIn(0, chunks.lastIndex)
        val chunk = chunks[chunkIndex]
        val speech = if (announceProgress && chunks.size > 1) {
            getString(R.string.text_reader_chunk_progress, chunkIndex + 1, chunks.size) + ". " + chunk
        } else {
            chunk
        }
        announceText(speech)
    }

    private fun queueOrAnnounce(speech: String) {
        if (tts.isSpeaking()) {
            pendingSpeechText.set(speech)
        } else {
            announceText(speech)
        }
    }

    private fun announceText(speech: String) {
        postWhenAlive {
            setStatusText(speech)
            tts.speakThen(speech) {
                val pending = pendingSpeechText.getAndSet(null)
                if (!pending.isNullOrBlank() && !scanPaused.get()) {
                    postWhenAlive { announceText(pending) }
                }
            }
        }
    }

    private fun repeatLastText() {
        if (isContinuousMode && chunks.isNotEmpty()) {
            speakChunkAt(chunkIndex, announceProgress = chunks.size > 1)
            return
        }
        val text = latestSpeechText.get()
        if (text.isBlank()) {
            tts.speak(getString(R.string.text_reader_no_text))
        } else {
            tts.speak(text)
        }
    }

    private fun triggerManualRead() {
        val engine = recognitionEngine ?: return
        val bitmap = latestBitmap.get()
        if (bitmap == null) {
            tts.speak(getString(R.string.text_reader_no_frame))
            return
        }

        val frameCopy = bitmap.copy(Bitmap.Config.ARGB_8888, false)
        engine.recognize(
            bitmap = frameCopy,
            onResult = { raw ->
                frameCopy.recycle()
                onRecognizedText(raw, forceAnnounce = true)
            },
            onError = {
                frameCopy.recycle()
                sounds.play(SoundType.ACTION_ERROR)
                tts.speak(getString(R.string.text_reader_recognition_error))
            }
        )
    }

    private fun finishReader() {
        scanning.set(false)
        debouncer.reset()
        changeDetector.reset()
        pendingSpeechText.set(null)
        chunks = emptyList()
        chunkIndex = 0
        sounds.play(SoundType.SWIPE_LEFT)
        val exitMessage = when (mode) {
            TextReaderMode.MEDICATION_BOX -> getString(R.string.text_reader_exit_medication)
            TextReaderMode.PRODUCT_LABEL -> getString(R.string.text_reader_exit_label)
            TextReaderMode.GENERAL_TEXT -> getString(R.string.text_reader_exit_general)
            TextReaderMode.CONTINUOUS -> getString(R.string.text_reader_exit_continuous)
        }
        tts.speak(exitMessage)
        finish()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.KEYCODE_VOLUME_DOWN -> {
                if (event?.repeatCount == 0) {
                    triggerManualRead()
                }
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
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_CAMERA) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                initializeReader()
            } else {
                sounds.play(SoundType.ACTION_ERROR)
                setStatusText(getString(R.string.text_reader_permission_denied))
                tts.runWhenReady { tts.speak(getString(R.string.text_reader_permission_denied)) }
                finish()
            }
        }
    }

    private fun handleMemoryFailure() {
        if (!memoryFailureHandled.compareAndSet(false, true)) return
        scanning.set(false)
        scanPaused.set(true)
        pendingSpeechText.set(null)
        imageAnalysis?.clearAnalyzer()
        sounds.play(SoundType.ACTION_ERROR)
        setStatusText(getString(R.string.camera_memory_error))
        if (isContinuousMode) {
            tts.speakThen(getString(R.string.text_reader_continuous_memory_exit)) { finishReader() }
        } else {
            tts.speak(getString(R.string.camera_memory_error))
        }
    }

    override fun onDestroy() {
        scanning.set(false)
        mainHandler.removeCallbacksAndMessages(null)
        imageAnalysis?.clearAnalyzer()
        imageAnalysis = null
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        recognitionEngine?.close()
        recognitionEngine = null
        latestBitmap.getAndSet(null)?.recycle()
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    @ExperimentalGetImage
    private inner class FrameAnalyzer : ImageAnalysis.Analyzer {
        override fun analyze(imageProxy: ImageProxy) {
            if (!scanning.get()) {
                imageProxy.close()
                return
            }
            if (isContinuousMode && scanPaused.get()) {
                imageProxy.close()
                return
            }

            val now = System.currentTimeMillis()
            val interval = if (isContinuousMode) CONTINUOUS_FRAME_INTERVAL_MS else FRAME_INTERVAL_MS
            if (now - lastFrameProcessedAt.get() < interval) {
                imageProxy.close()
                return
            }
            lastFrameProcessedAt.set(now)

            val engine = recognitionEngine
            if (engine == null) {
                imageProxy.close()
                return
            }

            try {
                val bitmap = imageProxy.toBitmap()
                latestBitmap.getAndSet(bitmap)?.recycle()
                val frameCopy = try {
                    bitmap.copy(Bitmap.Config.ARGB_8888, false)
                } catch (oom: OutOfMemoryError) {
                    latestBitmap.getAndSet(null)?.recycle()
                    System.gc()
                    postWhenAlive { handleMemoryFailure() }
                    return
                }
                bitmap.recycle()
                engine.recognize(
                    bitmap = frameCopy,
                    onResult = { raw ->
                        frameCopy.recycle()
                        postWhenAlive { onRecognizedText(raw, forceAnnounce = false) }
                    },
                    onError = {
                        frameCopy.recycle()
                        postWhenAlive { registerOcrFailure() }
                    }
                )
            } catch (oom: OutOfMemoryError) {
                latestBitmap.getAndSet(null)?.recycle()
                System.gc()
                postWhenAlive { handleMemoryFailure() }
            } catch (_: Exception) {
            } finally {
                imageProxy.close()
            }
        }
    }

    companion object {
        private const val REQ_CAMERA = 7105
        private const val FRAME_INTERVAL_MS = 900L
        private const val CONTINUOUS_FRAME_INTERVAL_MS = 1400L
        private const val MAX_CONSECUTIVE_OCR_FAILURES = 4
    }
}