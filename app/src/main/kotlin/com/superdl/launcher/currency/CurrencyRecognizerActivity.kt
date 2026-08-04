package com.superdl.launcher.currency

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.launch
import com.superdl.launcher.R
import com.superdl.launcher.camera.CameraAnalysisConfig
import com.superdl.launcher.camera.CameraStabilityHelper
import com.superdl.launcher.currency.compose.CurrencyRecognizerScreen
import com.superdl.launcher.currency.compose.CurrencyRecognizerViewModel
import com.superdl.launcher.currency.compose.createCurrencyGestureListener
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.tts.TtsManager
import com.superdl.launcher.util.postWhenAlive
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

@ExperimentalGetImage
class CurrencyRecognizerActivity : ComponentActivity() {

    private val viewModel: CurrencyRecognizerViewModel by viewModels()
    private lateinit var sounds: SoundFeedback
    private lateinit var tts: TtsManager
    private lateinit var gestureListener: com.superdl.launcher.gestures.SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private val mainHandler = Handler(Looper.getMainLooper())

    private var scanBeepPlayer: ScanBeepPlayer? = null
    private val scanning = AtomicBoolean(false)
    private val memoryFailureHandled = AtomicBoolean(false)
    private val lastFrameProcessedAt = AtomicLong(0L)
    private val latestBitmap = AtomicReference<Bitmap?>(null)
    private var imageAnalysis: ImageAnalysis? = null
    private var boundCamera: Camera? = null
    private var previewView: PreviewView? = null
    private var lastBackPressAt = 0L
    private var lastWorkingTickAt = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        sounds = SoundFeedback(this)
        tts = TtsManager(this)
        cameraExecutor = Executors.newSingleThreadExecutor()
        scanBeepPlayer = ScanBeepPlayer()

        gestureListener = createCurrencyGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                triggerManualVerification()
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                tts.speak(getString(R.string.currency_help))
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                triggerManualVerification()
            },
            onSwipeLeft = { finishRecognizer() }
        )

        setContent {
            val uiState by viewModel.uiState.collectAsStateWithLifecycle()
            LaunchedEffect(uiState.fatalError) {
                uiState.fatalError?.let { message ->
                    tts.runWhenReady { tts.speak(message) }
                }
            }
            MaterialTheme(colorScheme = darkColorScheme()) {
                CurrencyRecognizerScreen(
                    uiState = uiState,
                    onPreviewViewReady = { preview ->
                        previewView = preview
                        if (hasCameraPermission() && scanning.get()) {
                            bindCamera(preview)
                        }
                    },
                    onTouchEvent = { event ->
                        gestureListener.detector.onTouchEvent(event)
                        event.action == android.view.MotionEvent.ACTION_UP
                    },
                    onExit = { finishRecognizer() }
                )
            }
        }

        observeViewModel()

        if (hasCameraPermission()) {
            initializeRecognizer()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
        }
    }

    private fun observeViewModel() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.events.collect { event ->
                    if (event == null) return@collect
                    when (event) {
                        is CurrencyRecognizerViewModel.FrameEvent.Announce -> {
                            // QUEUE_FLUSH: megszakít mindent, egy stabil final eredmény.
                            // Nincs speakThen, nincs sorba állítás — flicker/hurok ellen.
                            tts.speak(event.speech)
                        }
                        is CurrencyRecognizerViewModel.FrameEvent.SpeakAdd ->
                            tts.speakAdd(event.speech)
                        CurrencyRecognizerViewModel.FrameEvent.PlayWorkingTick -> {
                            val now = System.currentTimeMillis()
                            if (now - lastWorkingTickAt >= WORKING_TICK_INTERVAL_MS) {
                                lastWorkingTickAt = now
                                scanBeepPlayer?.playWorkingTick()
                            }
                        }
                        CurrencyRecognizerViewModel.FrameEvent.PlayEntryBeep ->
                            scanBeepPlayer?.playScanStart()
                        CurrencyRecognizerViewModel.FrameEvent.PlayError ->
                            sounds.play(SoundType.ACTION_ERROR)
                    }
                    viewModel.consumeEvent()
                }
            }
        }
    }

    private fun initializeRecognizer() {
        viewModel.initialize {
            tts.runWhenReady { tts.speak(getString(R.string.currency_intro)) }
            scanning.set(true)
            previewView?.let { bindCamera(it) }
        }
    }

    private fun bindCamera(previewView: PreviewView) {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            try {
                val provider = providerFuture.get()
                val preview = CameraStabilityHelper.buildLightPreview(previewView.surfaceProvider)
                imageAnalysis = CameraAnalysisConfig.imageAnalysisBuilder()
                    .build()
                    .also { analysis ->
                        analysis.setAnalyzer(cameraExecutor, FrameAnalyzer())
                    }
                provider.unbindAll()
                boundCamera = provider.bindToLifecycle(
                    this,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    imageAnalysis
                )
                boundCamera?.let { viewModel.torchController.attach(it) }
            } catch (_: Exception) {
                sounds.play(SoundType.ACTION_ERROR)
                tts.runWhenReady { tts.speak(getString(R.string.currency_camera_error)) }
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun triggerManualVerification() {
        viewModel.manualVerify(latestBitmap.get())
    }

    private fun finishRecognizer() {
        scanning.set(false)
        viewModel.stopScanning()
        sounds.play(SoundType.SWIPE_LEFT)
        // Gesztus-kilépés: speak + azonnali finish — NE speakThen { finish() }.
        // MIÉRT: a speakThen a TTS BEFEJEZÉSE után hív finish-t; ha a user közben
        // újra söpör, a még élő Activity újra lefuttatja, és a mondat 3-4x elhangzik.
        tts.speak(getString(R.string.currency_exit))
        finish()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.KEYCODE_VOLUME_DOWN -> {
                if (event?.repeatCount == 0) triggerManualVerification()
                return true
            }
            KeyEvent.KEYCODE_BACK -> {
                val now = System.currentTimeMillis()
                if (now - lastBackPressAt < 2000L) {
                    finishRecognizer()
                } else {
                    lastBackPressAt = now
                    tts.speak(getString(R.string.currency_back_again))
                }
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
                initializeRecognizer()
            } else {
                sounds.play(SoundType.ACTION_ERROR)
                tts.runWhenReady { tts.speak(getString(R.string.currency_permission_denied)) }
                finish()
            }
        }
    }

    override fun onDestroy() {
        scanning.set(false)
        mainHandler.removeCallbacksAndMessages(null)
        viewModel.release()
        imageAnalysis?.clearAnalyzer()
        imageAnalysis = null
        boundCamera = null
        previewView = null
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        scanBeepPlayer?.close()
        scanBeepPlayer = null
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

            val now = System.currentTimeMillis()
            if (now - lastFrameProcessedAt.get() < FRAME_INTERVAL_MS) {
                imageProxy.close()
                return
            }
            lastFrameProcessedAt.set(now)

            try {
                val bitmap = imageProxy.toBitmap()
                latestBitmap.getAndSet(bitmap)?.recycle()
                if (scanning.get()) {
                    viewModel.onFrame(bitmap)
                }
            } catch (_: OutOfMemoryError) {
                latestBitmap.getAndSet(null)?.recycle()
                System.gc()
                postWhenAlive { handleFrameMemoryFailure() }
            } catch (e: Exception) {
                android.util.Log.w(
                    "SDL_CASH",
                    "Frame analyze hiba: ${e.javaClass.simpleName}: ${e.message}"
                )
            } finally {
                try {
                    imageProxy.close()
                } catch (_: Exception) {
                }
            }
        }
    }

    private fun handleFrameMemoryFailure() {
        if (!memoryFailureHandled.compareAndSet(false, true)) return
        scanning.set(false)
        imageAnalysis?.clearAnalyzer()
        sounds.play(SoundType.ACTION_ERROR)
        tts.speak(getString(R.string.currency_memory_error))
    }

    companion object {
        private const val REQ_CAMERA = 7104
        private const val FRAME_INTERVAL_MS = 260L
        private const val WORKING_TICK_INTERVAL_MS = 380L
    }
}