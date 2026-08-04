# SuperDL — Pénzfelismerő (Currency) Teljes Implementációs Állapot

**Generálva:** 2026-07-03  
**Projekt:** `C:\Users\msn\Documents\SuperDL-Android`  
**Belépési pont:** `MainActivity` → `MenuAction.CURRENCY_RECOGNIZER` → `CurrencyRecognizerActivity`  
**Verzió:** 1.54.3 (versionCode 94)

---

## 1. Áttekintés és Fájlok

### 1.1 Architektúra összefoglaló

```
MainActivity (menü)
    └── CurrencyRecognizerActivity (CameraX + Compose host)
            ├── CurrencyRecognizerScreen (Compose UI)
            ├── CurrencyRecognizerViewModel (MVVM állapot + inference orchestration)
            ├── FrameAnalyzer (ImageAnalysis.Analyzer — inner class)
            ├── SwipeGestureListener (gesztusok)
            ├── TtsManager (felhasználói visszajelzés)
            ├── SoundFeedback + ScanBeepPlayer (hangjelzések)
            └── BanknoteClassifierEngine (TFLite inference)
                    ├── BanknoteYoloDetector (Stage 1 — **[HIÁNYZIK asset]**)
                    └── BanknoteDenominationClassifier (Stage 2)
```

### 1.2 `currency` csomag — összes fájl

| # | Teljes elérési út |
|---|-------------------|
| 1 | `app/src/main/kotlin/com/superdl/launcher/currency/CurrencyRecognizerActivity.kt` |
| 2 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteClassifierEngine.kt` |
| 3 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteYoloDetector.kt` |
| 4 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteDenominationClassifier.kt` |
| 5 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteClassificationResult.kt` |
| 6 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteDenomination.kt` |
| 7 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteDetection.kt` |
| 8 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteBitmapCropper.kt` |
| 9 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteColorVerifier.kt` |
| 10 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteConsensusFilter.kt` |
| 11 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteFrameGate.kt` |
| 12 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteScanDebouncer.kt` |
| 13 | `app/src/main/kotlin/com/superdl/launcher/currency/BanknoteTorchController.kt` |
| 14 | `app/src/main/kotlin/com/superdl/launcher/currency/ScanBeepPlayer.kt` |
| 15 | `app/src/main/kotlin/com/superdl/launcher/currency/YoloOutputParser.kt` |

### 1.3 `currency.compose` csomag — összes fájl

| # | Teljes elérési út |
|---|-------------------|
| 1 | `app/src/main/kotlin/com/superdl/launcher/currency/compose/CurrencyRecognizerViewModel.kt` |
| 2 | `app/src/main/kotlin/com/superdl/launcher/currency/compose/CurrencyRecognizerScreen.kt` |
| 3 | `app/src/main/kotlin/com/superdl/launcher/currency/compose/CurrencyRecognizerUiState.kt` |

### 1.4 Külső, currency-hez kötődő fájlok

| Fájl | Szerep |
|------|--------|
| `app/src/main/kotlin/com/superdl/launcher/gestures/SwipeGestureListener.kt` | Swipe detektálás |
| `app/src/main/kotlin/com/superdl/launcher/tts/TtsManager.kt` | TTS motor |
| `app/src/main/kotlin/com/superdl/launcher/camera/CameraAnalysisConfig.kt` | ImageAnalysis 640×480 RGBA |
| `app/src/main/kotlin/com/superdl/launcher/camera/CameraStabilityHelper.kt` | PreviewView + executor shutdown |
| `app/src/main/kotlin/com/superdl/launcher/feedback/SoundFeedback.kt` | Swipe/error hangok |
| `app/src/main/kotlin/com/superdl/launcher/menu/MenuTree.kt` | Menübejegyzés |
| `app/src/main/res/values/strings.xml` | `currency_*` string erőforrások |
| `app/src/main/assets/huf_banknote_classifier.tflite` | Stage 2 modell ✓ |
| `app/src/main/assets/huf_banknote_labels.txt` | Classifier címkék ✓ |
| `app/src/main/assets/huf_banknote_detector_labels.txt` | YOLO címkék ✓ |
| `app/src/main/assets/huf_banknote_detector.tflite` | Stage 1 modell **[HIÁNYZIK]** |

### 1.5 Legacy (nem használt)

`app/src/main/res/layout/activity_currency_recognizer.xml` — XML layout a Compose migráció előtt; **jelenleg nem bindolódik**.

---

## 2. Fő Fájlok Teljes Forráskódja

### 2.1 CurrencyRecognizerActivity.kt

```kotlin
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
                        is CurrencyRecognizerViewModel.FrameEvent.Announce ->
                            tts.speak(event.speech)
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
        tts.speakThen(getString(R.string.currency_exit)) { finish() }
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
                    tts.speak("Kilépéshez nyomd meg újra a vissza gombot, vagy balra swipe-olj.")
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
            } catch (_: Exception) {
            } finally {
                imageProxy.close()
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
```

### 2.2 CurrencyRecognizerViewModel.kt

```kotlin
package com.superdl.launcher.currency.compose

import android.app.Application
import android.content.pm.ApplicationInfo
import android.graphics.Bitmap
import android.graphics.RectF
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.superdl.launcher.R
import com.superdl.launcher.currency.BanknoteClassificationResult
import com.superdl.launcher.currency.BanknoteClassifierEngine
import com.superdl.launcher.currency.BanknoteConsensusFilter
import com.superdl.launcher.currency.BanknoteFrameGate
import com.superdl.launcher.currency.BanknoteScanDebouncer
import com.superdl.launcher.currency.BanknoteTorchController
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.util.ArrayDeque
import java.util.concurrent.atomic.AtomicBoolean

class CurrencyRecognizerViewModel(application: Application) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(CurrencyRecognizerUiState())
    val uiState: StateFlow<CurrencyRecognizerUiState> = _uiState.asStateFlow()

    @Volatile
    private var engine: BanknoteClassifierEngine? = null

    private val debouncer = BanknoteScanDebouncer()
    private val consensusFilter = BanknoteConsensusFilter()
    val torchController = BanknoteTorchController()

    private val scanning = AtomicBoolean(false)
    private val frameMutex = Mutex()
    private val engineMutex = Mutex()
    private var releaseJob: Job? = null
    private val pendingEvents = ArrayDeque<FrameEvent>()

    @Volatile
    private var lastTorchSpeechAt = 0L

    sealed interface FrameEvent {
        data class Announce(val speech: String, val playEntryBeep: Boolean) : FrameEvent
        data class SpeakAdd(val speech: String) : FrameEvent
        object PlayWorkingTick : FrameEvent
        object PlayEntryBeep : FrameEvent
        object PlayError : FrameEvent
    }

    private val _events = MutableStateFlow<FrameEvent?>(null)
    val events: StateFlow<FrameEvent?> = _events.asStateFlow()

    fun initialize(onReady: () -> Unit) {
        viewModelScope.launch {
            try {
                val created = withContext(Dispatchers.IO) {
                    BanknoteClassifierEngine.create(getApplication())
                }
                engine = created
                scanning.set(true)
                _uiState.update {
                    it.copy(
                        statusText = getString(R.string.currency_status_active),
                        hintText = getString(R.string.currency_hint),
                        isScanning = true,
                        isTwoStageEnabled = created.isTwoStageEnabled,
                        fatalError = null
                    )
                }
                onReady()
            } catch (_: Exception) {
                engine = null
                scanning.set(false)
                _uiState.update {
                    it.copy(
                        fatalError = getString(R.string.currency_model_error),
                        isScanning = false
                    )
                }
                emitEvent(FrameEvent.PlayError)
            }
        }
    }

    fun onFrame(bitmap: Bitmap) {
        if (!scanning.get() || engine == null) return

        viewModelScope.launch(Dispatchers.Default) {
            frameMutex.withLock {
                if (!scanning.get() || engine == null) return@withLock
                val frame = copyFrame(bitmap) ?: return@withLock
                try {
                    processFrame(frame)
                } finally {
                    if (!frame.isRecycled) frame.recycle()
                }
            }
        }
    }

    private suspend fun processFrame(bitmap: Bitmap) {
        val activeEngine = engine ?: return

        val frameDecision = BanknoteFrameGate.evaluate(bitmap)
        val torchJustOn = torchController.update(frameDecision.metrics)
        if (torchJustOn) {
            maybeEmitTorchOn()
        }

        if (frameDecision.isEmptySlot) {
            when (debouncer.onAbsentFrame()) {
                BanknoteScanDebouncer.BillPresenceEvent.REMOVED ->
                    updateStatus(getString(R.string.currency_status_scanning))
                else -> Unit
            }
            consensusFilter.reset()
            clearOverlay()
            return
        }

        emitEvent(FrameEvent.PlayWorkingTick)

        val rawResult = engineMutex.withLock { activeEngine.classify(bitmap) }
        val stableResult = consensusFilter.submit(frameDecision, rawResult)
        updateOverlay(rawResult)

        if (stableResult == null) {
            when (debouncer.onAbsentFrame()) {
                BanknoteScanDebouncer.BillPresenceEvent.REMOVED ->
                    updateStatus(getString(R.string.currency_status_scanning))
                else -> Unit
            }
            return
        }

        when (val decision = debouncer.onDetected(stableResult)) {
            is BanknoteScanDebouncer.ScanDecision.Announce -> {
                if (decision.playEntryBeep) {
                    emitEvent(FrameEvent.PlayEntryBeep)
                    updateStatus(getString(R.string.currency_status_detected))
                }
                updateStatus(decision.result.denomination.speechHu)
                emitEvent(
                    FrameEvent.Announce(
                        speech = decision.result.denomination.speechHu,
                        playEntryBeep = false
                    )
                )
                debouncer.markAnnounced(decision.result.denomination)
            }
            BanknoteScanDebouncer.ScanDecision.BillRemoved ->
                updateStatus(getString(R.string.currency_status_scanning))
            BanknoteScanDebouncer.ScanDecision.Ignored -> Unit
        }
    }

    fun manualVerify(bitmap: Bitmap?) {
        val activeEngine = engine ?: return
        if (bitmap == null) {
            emitEvent(FrameEvent.Announce(getString(R.string.currency_no_frame), playEntryBeep = false))
            return
        }

        viewModelScope.launch(Dispatchers.Default) {
            frameMutex.withLock {
                val frame = copyFrame(bitmap) ?: run {
                    emitEvent(FrameEvent.Announce(getString(R.string.currency_no_frame), playEntryBeep = false))
                    return@launch
                }
                try {
                    val frameDecision = BanknoteFrameGate.evaluate(frame)
                    torchController.update(frameDecision.metrics)

                    if (frameDecision.isEmptySlot) {
                        emitEvent(FrameEvent.PlayEntryBeep)
                        emitEvent(FrameEvent.Announce(getString(R.string.currency_no_banknote), playEntryBeep = false))
                        updateStatus(getString(R.string.currency_status_scanning))
                        clearOverlay()
                        return@withLock
                    }

                    if (frameDecision.needsMoreLight) {
                        torchController.forceOn()
                        maybeEmitTorchOn()
                    }

                    val result = engineMutex.withLock { activeEngine.classifyForManualCheck(frame) }
                    updateOverlay(result)

                    if (result == null || !result.isReliableForManualCheck()) {
                        emitEvent(FrameEvent.PlayEntryBeep)
                        emitEvent(FrameEvent.Announce(getString(R.string.currency_not_recognized), playEntryBeep = false))
                        updateStatus(getString(R.string.currency_status_scanning))
                        return@withLock
                    }

                    updateStatus(result.denomination.speechHu)
                    emitEvent(FrameEvent.Announce(result.denomination.speechHu, playEntryBeep = false))
                    debouncer.markAnnounced(result.denomination)
                } catch (_: Exception) {
                    emitEvent(FrameEvent.PlayError)
                    emitEvent(FrameEvent.Announce(getString(R.string.currency_verify_error), playEntryBeep = false))
                } finally {
                    if (!frame.isRecycled) frame.recycle()
                }
            }
        }
    }

    fun stopScanning() {
        scanning.set(false)
        debouncer.reset()
        consensusFilter.reset()
        torchController.release()
        _uiState.update {
            it.copy(isScanning = false, detectionBox = null, pipelineMode = null)
        }
    }

    fun release() {
        stopScanning()
        releaseJob?.cancel()
        releaseJob = viewModelScope.launch(Dispatchers.IO) {
            frameMutex.withLock {
                engineMutex.withLock {
                    engine?.close()
                    engine = null
                }
            }
        }
    }

    fun consumeEvent() {
        synchronized(pendingEvents) {
            _events.value = if (pendingEvents.isEmpty()) null else pendingEvents.removeFirst()
        }
    }

    private fun updateOverlay(result: BanknoteClassificationResult?) {
        _uiState.update {
            it.copy(
                pipelineMode = result?.pipelineMode,
                detectionBox = result?.detectionBox?.let { box -> RectF(box) },
                showDetectionOverlay = result?.detectionBox != null && isDebugBuild()
            )
        }
    }

    private fun clearOverlay() {
        _uiState.update { it.copy(detectionBox = null, pipelineMode = null) }
    }

    private fun updateStatus(text: String) {
        _uiState.update { it.copy(statusText = text) }
    }

    private fun maybeEmitTorchOn() {
        val now = System.currentTimeMillis()
        if (now - lastTorchSpeechAt < 8000L) return
        lastTorchSpeechAt = now
        emitEvent(FrameEvent.SpeakAdd(getString(R.string.currency_torch_on)))
    }

    private fun emitEvent(event: FrameEvent) {
        synchronized(pendingEvents) {
            if (_events.value == null) {
                _events.value = event
            } else {
                pendingEvents.addLast(event)
            }
        }
    }

    private fun copyFrame(bitmap: Bitmap): Bitmap? =
        try {
            bitmap.copy(Bitmap.Config.ARGB_8888, false)
        } catch (_: OutOfMemoryError) {
            null
        } catch (_: Exception) {
            null
        }

    private fun getString(resId: Int): String = getApplication<Application>().getString(resId)

    private fun isDebugBuild(): Boolean {
        val flags = getApplication<Application>().applicationInfo.flags
        return flags and ApplicationInfo.FLAG_DEBUGGABLE != 0
    }
}
```

### 2.3 CurrencyRecognizerScreen.kt

```kotlin
package com.superdl.launcher.currency.compose

import android.graphics.RectF
import android.view.MotionEvent
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.superdl.launcher.camera.CameraStabilityHelper
import com.superdl.launcher.gestures.SwipeGestureListener

@Composable
fun CurrencyRecognizerScreen(
    uiState: CurrencyRecognizerUiState,
    onPreviewViewReady: (PreviewView) -> Unit,
    onTouchEvent: (MotionEvent) -> Boolean,
    onExit: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = Color.Black
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            CurrencyStatusBar(
                statusText = uiState.statusText.ifBlank { uiState.fatalError.orEmpty() },
                onExit = onExit
            )

            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
            ) {
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = { ctx ->
                        PreviewView(ctx).also { previewView ->
                            CameraStabilityHelper.configurePreviewView(previewView)
                            previewView.setOnTouchListener { _, event ->
                                onTouchEvent(event)
                            }
                            onPreviewViewReady(previewView)
                        }
                    },
                    update = { previewView ->
                        previewView.setOnTouchListener { _, event ->
                            onTouchEvent(event)
                        }
                    }
                )

                if (uiState.showDetectionOverlay && uiState.detectionBox != null) {
                    DetectionOverlay(box = uiState.detectionBox)
                }

                if (uiState.hintText.isNotBlank()) {
                    Text(
                        text = uiState.hintText,
                        color = Color.White.copy(alpha = 0.72f),
                        fontSize = 13.sp,
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .padding(12.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun CurrencyStatusBar(
    statusText: String,
    onExit: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.Black)
            .padding(horizontal = 8.dp, vertical = 4.dp)
    ) {
        Text(
            text = statusText,
            color = Color.White,
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier
                .align(Alignment.CenterStart)
                .padding(end = 96.dp)
                .semantics {
                    liveRegion = androidx.compose.ui.semantics.LiveRegionMode.Assertive
                    contentDescription = statusText
                }
        )
        Button(
            onClick = onExit,
            modifier = Modifier
                .align(Alignment.CenterEnd)
                .semantics {
                    contentDescription = "Kilépés a pénzfelismerőből"
                }
        ) {
            Text("Kilépés")
        }
    }
}

@Composable
private fun DetectionOverlay(box: RectF) {
    Canvas(modifier = Modifier.fillMaxSize()) {
        val stroke = Stroke(width = 3.dp.toPx())
        val left = box.left.coerceIn(0f, 1f) * size.width
        val top = box.top.coerceIn(0f, 1f) * size.height
        val width = box.width().coerceIn(0f, 1f) * size.width
        val height = box.height().coerceIn(0f, 1f) * size.height
        drawRect(
            color = Color(0xFF4CAF50),
            topLeft = Offset(left, top),
            size = Size(width, height),
            style = stroke
        )
    }
}

/** Helper kept near UI layer for gesture wiring from Activity. */
fun createCurrencyGestureListener(
    context: android.content.Context,
    onSwipeUp: () -> Unit,
    onSwipeDown: () -> Unit,
    onSwipeRight: () -> Unit,
    onSwipeLeft: () -> Unit
): SwipeGestureListener = SwipeGestureListener(
    context = context,
    onSwipeUp = onSwipeUp,
    onSwipeDown = onSwipeDown,
    onSwipeRight = onSwipeRight,
    onSwipeLeft = onSwipeLeft
)
```

### 2.4 CurrencyRecognizerUiState.kt

```kotlin
package com.superdl.launcher.currency.compose

import android.graphics.RectF
import com.superdl.launcher.currency.BanknotePipelineMode

data class CurrencyRecognizerUiState(
    val statusText: String = "",
    val hintText: String = "",
    val isScanning: Boolean = false,
    val isTwoStageEnabled: Boolean = false,
    val pipelineMode: BanknotePipelineMode? = null,
    val detectionBox: RectF? = null,
    val showDetectionOverlay: Boolean = false,
    val fatalError: String? = null
)
```

### 2.5 TtsManager.kt (teljes — currency és egész app)

```kotlin
package com.superdl.launcher.tts

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import android.util.Log
import java.util.Locale

class TtsManager(context: Context) : TextToSpeech.OnInitListener {

    private val appContext = context.applicationContext
    private val handler = Handler(Looper.getMainLooper())
    private var selectedVoiceName: String? = TtsEngineStore.getSelectedVoiceName(appContext)
    private var tts: TextToSpeech = createEngine(TtsEngineStore.getSelectedPackage(appContext))
    private var isReady = false
    private var initFailed = false
    private var onUtteranceDone: (() -> Unit)? = null
    private var pendingOnReady: (() -> Unit)? = null
    private val readyCallbacks = mutableListOf<() -> Unit>()

    var speechRate: Float = TtsSettingsStore.getSpeechRate(appContext)
        set(value) {
            field = value.coerceIn(0.5f, 2.5f)
            TtsSettingsStore.setSpeechRate(appContext, field)
            if (isReady) tts.setSpeechRate(field)
        }

    private fun createEngine(enginePackage: String?): TextToSpeech =
        if (enginePackage.isNullOrBlank()) {
            TextToSpeech(appContext, this)
        } else {
            TextToSpeech(appContext, this, enginePackage)
        }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            initFailed = false
            val result = tts.setLanguage(Locale("hu", "HU"))
            isReady = result != TextToSpeech.LANG_MISSING_DATA &&
                result != TextToSpeech.LANG_NOT_SUPPORTED
            if (!isReady) {
                Log.w("TTS", "Magyar nyelv nem érhető el, visszaesés angolra")
                tts.setLanguage(Locale.ENGLISH)
                isReady = true
            }
            applySelectedVoice()
            configureAudioRouting()
            tts.setSpeechRate(speechRate)
            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {}
                override fun onDone(utteranceId: String?) {
                    if (utteranceId?.startsWith("SDL_DONE_") == true) {
                        val callback = onUtteranceDone
                        onUtteranceDone = null
                        callback?.let { handler.post(it) }
                    }
                }
                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    if (utteranceId?.startsWith("SDL_DONE_") == true) {
                        val callback = onUtteranceDone
                        onUtteranceDone = null
                        callback?.let { handler.post(it) }
                    }
                }
            })
            pendingOnReady?.let { handler.post(it) }
            pendingOnReady = null
            if (readyCallbacks.isNotEmpty()) {
                val callbacks = readyCallbacks.toList()
                readyCallbacks.clear()
                callbacks.forEach { handler.post(it) }
            }
        } else {
            Log.e("TTS", "TTS motor inicializálás sikertelen: $status")
            isReady = false
            initFailed = true
            val pending = pendingOnReady
            pendingOnReady = null
            val queued = readyCallbacks.toList()
            readyCallbacks.clear()
            handler.post {
                pending?.invoke()
                queued.forEach { it.invoke() }
            }
        }
    }

    fun switchEngine(
        packageName: String?,
        voiceName: String? = selectedVoiceName,
        onReady: (() -> Unit)? = null,
        onFailed: (() -> Unit)? = null
    ) {
        selectedVoiceName = voiceName?.takeIf { it.isNotBlank() }
        TtsEngineStore.setSelection(appContext, packageName, selectedVoiceName)
        pendingOnReady = if (onReady != null || onFailed != null) {
            {
                if (isReady) onReady?.invoke() else onFailed?.invoke()
            }
        } else null
        onUtteranceDone = null
        isReady = false
        initFailed = false
        val rate = speechRate
        tts.stop()
        tts.shutdown()
        speechRate = rate
        tts = createEngine(packageName)
    }

    fun runWhenReady(action: () -> Unit) {
        if (isReady) {
            handler.post(action)
        } else {
            readyCallbacks.add(action)
        }
    }

    fun speak(text: String) {
        if (initFailed) {
            Log.w("TTS", "TTS nem elérhető, kihagyva: $text")
            return
        }
        if (!isReady) {
            runWhenReady { speak(text) }
            return
        }
        onUtteranceDone = null
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, speakParams(), "SDL_${System.currentTimeMillis()}")
    }

    fun speakThen(text: String, onDone: () -> Unit) {
        if (initFailed) {
            Log.w("TTS", "TTS nem elérhető, speakThen kihagyva")
            handler.post(onDone)
            return
        }
        if (!isReady) {
            runWhenReady { speakThen(text, onDone) }
            return
        }
        onUtteranceDone = onDone
        val id = "SDL_DONE_${System.currentTimeMillis()}"
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, speakParams(), id)
    }

    fun speakAdd(text: String) {
        if (initFailed) return
        if (!isReady) {
            runWhenReady { speakAdd(text) }
            return
        }
        tts.speak(text, TextToSpeech.QUEUE_ADD, speakParams(), "SDL_ADD_${System.currentTimeMillis()}")
    }

    fun isSpeaking(): Boolean = isReady && tts.isSpeaking

    fun stop() {
        onUtteranceDone = null
        tts.stop()
    }

    fun speedUp() {
        speechRate += 0.1f
        speak("Sebesség: ${String.format(Locale.getDefault(), "%.1f", speechRate)}")
    }

    fun speedDown() {
        speechRate -= 0.1f
        speak("Sebesség: ${String.format(Locale.getDefault(), "%.1f", speechRate)}")
    }

    private fun configureAudioRouting() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            val attributes = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .setFlags(AudioAttributes.FLAG_AUDIBILITY_ENFORCED)
                .build()
            tts.setAudioAttributes(attributes)
        }
    }

    private fun speakParams(): Bundle = Bundle().apply {
        putInt(TextToSpeech.Engine.KEY_PARAM_STREAM, AudioManager.STREAM_ACCESSIBILITY)
        putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f)
    }

    private fun applySelectedVoice() {
        val voiceName = selectedVoiceName?.takeIf { it.isNotBlank() } ?: return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP) return
        val voices = tts.voices ?: return
        val voice = voices.firstOrNull { it.name == voiceName } ?: return
        tts.voice = voice
    }

    fun shutdown() {
        handler.removeCallbacksAndMessages(null)
        onUtteranceDone = null
        pendingOnReady = null
        readyCallbacks.clear()
        tts.stop()
        tts.shutdown()
    }
}
```

---

## 3. Gesztus- és Interakciókezelés

### 3.1 Gesztus osztályok és helyük

| Interakció | Kezelő osztály / metódus | Callback |
|------------|--------------------------|----------|
| Swipe fel | `SwipeGestureListener` → `CurrencyRecognizerActivity.onCreate` | `triggerManualVerification()` |
| Swipe jobbra | ugyanaz | `triggerManualVerification()` |
| Swipe le | ugyanaz | `tts.speak(currency_help)` |
| Swipe bal | ugyanaz | `finishRecognizer()` |
| Hangerő fel/le | `CurrencyRecognizerActivity.onKeyDown` | `triggerManualVerification()` |
| Vissza gomb | `CurrencyRecognizerActivity.onKeyDown` | 1×: figyelmeztetés TTS; 2× (2s): `finishRecognizer()` |
| Kilépés gomb (UI) | `CurrencyRecognizerScreen` Button → `onExit` | `finishRecognizer()` |
| Érintés a preview-n | `PreviewView.setOnTouchListener` → `gestureListener.detector.onTouchEvent` | Swipe detektálás |

**Gesztus logika központi osztálya:** `com.superdl.launcher.gestures.SwipeGestureListener`

```kotlin
// Küszöbök:
SWIPE_THRESHOLD = 100 px
SWIPE_VELOCITY_THRESHOLD = 100 px/s
// Vízszintes vs függőleges: abs(diffX) > abs(diffY) dönt
```

**Currency-specifikus wiring:** `createCurrencyGestureListener()` a `CurrencyRecognizerScreen.kt` fájlban — thin wrapper a `SwipeGestureListener` köré.

### 3.2 Touch event útvonal

```
PreviewView.onTouchListener
    → CurrencyRecognizerScreen.onTouchEvent lambda
        → gestureListener.detector.onTouchEvent(event)
        → returns event.action == ACTION_UP (Compose click semantics)
```

### 3.3 Hang visszajelzés (nem TTS)

| Esemény | Hang |
|---------|------|
| Swipe fel | `SoundFeedback` → `SWIPE_UP` |
| Swipe le | `SWIPE_DOWN` |
| Swipe jobbra | `SWIPE_RIGHT` |
| Swipe bal / kilépés | `SWIPE_LEFT` |
| Hiba (modell, kamera, OOM) | `ACTION_ERROR` |
| Aktív szkennelés | `ScanBeepPlayer.playWorkingTick()` (max 380ms-enként) |
| Bankjegy bejegyzés | `ScanBeepPlayer.playScanStart()` |

### 3.4 TTS összekötés gesztusokkal

```
Gesztus/Esemény                    TTS metódus              Üzenet forrás
─────────────────────────────────────────────────────────────────────────────
Swipe le                           speak()                  R.string.currency_help
Swipe bal / dupla back / Exit      speakThen() → finish()   R.string.currency_exit
Indítás (initialize callback)      speak()                  R.string.currency_intro
Fatal error (LaunchedEffect)       speak()                  uiState.fatalError
Kamera hiba                        speak()                  R.string.currency_camera_error
Engedély megtagadva                speak()                  R.string.currency_permission_denied
OOM                                speak()                  R.string.currency_memory_error
Dupla back első nyomás             speak()                  hardcoded magyar szöveg
Vaku bekapcsolva                   speakAdd()               R.string.currency_torch_on
ViewModel Announce event           speak()                  denomination.speechHu / error strings
ViewModel SpeakAdd event           speakAdd()               torch üzenet
```

**Event bus:** `ViewModel.events: StateFlow<FrameEvent?>` → `Activity.observeViewModel()` → `repeatOnLifecycle(STARTED)` → `tts.speak()` / `speakAdd()`.

---

## 4. Inference Pipeline és ML Logika

### 4.1 BanknoteClassifierEngine.kt — teljes logika

```kotlin
package com.superdl.launcher.currency

import android.content.Context
import android.graphics.Bitmap
import android.graphics.RectF
import java.io.Closeable

class BanknoteClassifierEngine private constructor(
    private val detector: BanknoteYoloDetector?,
    private val classifier: BanknoteDenominationClassifier
) : Closeable {

    private var cachedDetection: BanknoteDetection? = null
    private var cachedDetectionAtMs: Long = 0L
    private var frameCounter: Int = 0

    val isTwoStageEnabled: Boolean
        get() = detector != null

    fun classify(bitmap: Bitmap): BanknoteClassificationResult? =
        processFrame(bitmap, applyColorCheck = true)

    fun classifyForManualCheck(bitmap: Bitmap): BanknoteClassificationResult? =
        processFrame(bitmap, applyColorCheck = true)

    private fun processFrame(bitmap: Bitmap, applyColorCheck: Boolean): BanknoteClassificationResult? {
        if (bitmap.isRecycled || bitmap.width <= 0 || bitmap.height <= 0) return null

        // Stage 1 + 2
        runTwoStage(bitmap, applyColorCheck)?.let { return it }

        // Fallback: center ROI
        BanknoteBitmapCropper.centerRoi(bitmap)?.let { roi ->
            try {
                classifier.classify(roi, applyColorCheck)?.let { result ->
                    return result.copy(
                        pipelineMode = BanknotePipelineMode.ROI_FALLBACK,
                        detectionBox = null,
                        detectionConfidence = 0f
                    )
                }
            } finally {
                if (roi !== bitmap) roi.recycle()
            }
        }

        // Fallback: full frame
        return classifier.classify(bitmap, applyColorCheck)?.copy(
            pipelineMode = BanknotePipelineMode.FULL_FRAME_FALLBACK,
            detectionBox = null,
            detectionConfidence = 0f
        )
    }

    private fun runTwoStage(bitmap: Bitmap, applyColorCheck: Boolean): BanknoteClassificationResult? {
        val stage1 = detector ?: return null  // ← YOLO hiány → azonnal null
        val detection = resolveDetection(stage1, bitmap) ?: return null

        val crop = BanknoteBitmapCropper.crop(bitmap, detection) ?: return null
        return try {
            val stage2 = classifier.classify(crop, applyColorCheck) ?: return null
            reconcileStages(detection, stage2)
        } finally {
            if (crop !== bitmap) crop.recycle()
        }
    }

    private fun reconcileStages(
        detection: BanknoteDetection,
        classification: BanknoteClassificationResult
    ): BanknoteClassificationResult? {
        val yoloDenomination = detection.denomination
        if (yoloDenomination != null && yoloDenomination != classification.denomination) {
            val yoloStrong = detection.confidence >= STAGE_AGREE_MIN_CONF  // 0.62
            val clsStrong = classification.confidence >= STAGE_AGREE_MIN_CONF
            if (yoloStrong && clsStrong) return null  // abstain
        }

        return classification.copy(
            detectionConfidence = detection.confidence,
            pipelineMode = BanknotePipelineMode.TWO_STAGE,
            detectionBox = RectF(detection.boundingBox)
        )
    }

    private fun resolveDetection(stage1: BanknoteYoloDetector, bitmap: Bitmap): BanknoteDetection? {
        frameCounter++
        val now = System.currentTimeMillis()
        val cacheFresh = cachedDetection != null && now - cachedDetectionAtMs <= DETECTION_CACHE_MS  // 450ms
        if (cacheFresh && frameCounter % DETECTOR_EVERY_N_FRAMES != 0) {  // minden 2. frame
            return cachedDetection
        }
        val fresh = stage1.bestDetection(bitmap)
        if (fresh != null) {
            cachedDetection = fresh
            cachedDetectionAtMs = now
        }
        return fresh ?: cachedDetection
    }

    override fun close() {
        cachedDetection = null
        detector?.close()
        classifier.close()
    }

    companion object {
        private const val STAGE_AGREE_MIN_CONF = 0.62f
        private const val DETECTOR_EVERY_N_FRAMES = 2
        private const val DETECTION_CACHE_MS = 450L

        fun create(context: Context): BanknoteClassifierEngine {
            val appContext = context.applicationContext
            val classifier = BanknoteDenominationClassifier.create(appContext)  // throws if missing
            val detector = BanknoteYoloDetector.tryCreate(appContext)  // null if missing
            return BanknoteClassifierEngine(detector, classifier)
        }
    }
}
```

### 4.2 Hiányzó YOLO detektor kezelése

`BanknoteYoloDetector.tryCreate()` megnyitja `assets/huf_banknote_detector.tflite`-et. Ha **bármilyen exception** (fájl hiányzik):

```kotlin
} catch (_: Exception) {
    null
}
```

→ `detector = null` → `isTwoStageEnabled = false`  
→ `runTwoStage()` első sorában `detector ?: return null`  
→ Pipeline automatikusan a **ROI fallback** → **full-frame fallback** láncra esik.

**Jelenlegi állapot:** `huf_banknote_detector.tflite` **[HIÁNYZIK]** az assets-ből. A labels fájl megvan, a training weights (`tools/runs/banknote/huf_detect-2/weights/best.pt`) megvan, de TFLite nincs deployolva.

### 4.3 Fallback mechanizmusok (prioritási sorrend)

```
1. TWO_STAGE        YOLO bbox → crop (+6% pad) → MobileNet classify → reconcileStages
2. ROI_FALLBACK     centerRoi(72%×58%) → classify
3. FULL_FRAME_FALLBACK  teljes bitmap → classify
```

Minden szinten: `classifier.classify()` → `null` ha `none` osztály győz, alacsony conf, vagy színellenőrzés DISAGREE (strict módban).

### 4.4 BanknoteFrameGate

**Cél:** Üres járat vs. bankjegy-szerű tartalom vs. gyenge fény.

| Metrika | Üres járat küszöb | Tartalom jel |
|---------|-------------------|--------------|
| luminanceVariance | < 0.00025 | ≥ 0.0004 |
| colorSpread | < 0.012 | ≥ 0.015 |
| edgeEnergy | < 0.004 | ≥ 0.005 |
| meanSaturation | < 0.018 | ≥ 0.02 |

- `isEmptySlot` = mind a 4 üres-küszöb alatt
- `needsMoreLight` = meanLuminance < 0.24 && nem üres
- Mintavétel: középső ROI (18–82% szélesség, 20–80% magasság), 16×16 grid

**Hatás ViewModel-ben:** üres járat → consensus reset, overlay clear, debouncer absent frame; nem fut inference announce.

### 4.5 BanknoteConsensusFilter

**Cél:** Temporal stability — ne szóljon egyetlen frame alapján.

| Paraméter | Érték |
|-----------|-------|
| windowSize | 4 frame |
| requiredAgreements | 3 egyező címlet |

Logika:
1. Üres járat vagy `!result.isReliable(strictColor=false)` → `null` a ablakba
2. Ha ablak tele → groupBy denomination → winner ≥ 3 → max confidence result visszaadása
3. Egyébként `null` (nem announce-ol)

### 4.6 BanknoteScanDebouncer

**Cél:** Bill presence + announce cooldown.

| Paraméter | Érték |
|-----------|-------|
| cooldownMs | 3200 ms |
| absenceFramesRequired | 6 frame |

Állapotgép:
- `onAbsentFrame()` → ha volt bankjegy, 6 hiányzó frame után `REMOVED`
- `onDetected(result)`:
  - `!isReliable` → absent logika
  - első belépés (`entered`) → `Announce(playEntryBeep=true)`
  - ugyanaz a címlet + cooldown → `Ignored`
  - új címlet vagy cooldown lejárt → `Announce(playEntryBeep=false)`

### 4.7 BanknoteTorchController

| Küszöb | Akció |
|--------|-------|
| meanLuminance < 0.26 | vaku BE |
| meanLuminance > 0.40 | vaku KI |
| toggle cooldown | 900 ms |

`forceOn()` — manuális verify gyenge fényben.

### 4.8 Megbízhatósági küszöbök (`BanknoteClassificationResult`)

| Paraméter | Automatikus | Manuális |
|-----------|-------------|----------|
| confidence threshold | 0.52 | 0.45 |
| top margin (1. vs 2.) | 0.10 | 0.08 |
| detection conf (two-stage) | 0.55 | — |
| none compete margin | 0.06 | — |
| strictColor | true | false (manual) |

`fusedConfidence` (two-stage): `confidence * 0.72 + detectionConfidence * 0.28`

### 4.9 Címletek (`BanknoteDenomination`)

| Enum | speechHu |
|------|----------|
| HUF_500 | Ötszáz forint |
| HUF_1000 | Ezer forint |
| HUF_2000 | Kétezer forint |
| HUF_5000 | Ötezer forint |
| HUF_10000 | Tízezer forint |
| HUF_20000 | Húszezer forint |

---

## 5. TTS Használat a Currency Modulban

### 5.1 Összes TTS üzenet

| String resource | Szöveg | Mikor |
|-----------------|--------|-------|
| `currency_intro` | Pénzfelismerő mód aktív. Mutasd a kamerának… | `initialize()` callback |
| `currency_help` | Tartsd a bankjegyet… | Swipe le |
| `currency_status_active` | Pénzfelismerő mód aktív | UI status (nem mindig TTS) |
| `currency_status_scanning` | Bankjegy keresése… | Üres/eltávolított |
| `currency_status_detected` | Bankjegy észlelve | Első announce |
| `currency_exit` | Pénzfelismerő leállítva | Kilépéskor `speakThen` |
| `currency_permission_denied` | Kamera engedély szükséges… | Permission denied |
| `currency_camera_error` | A kamera nem indítható | bindCamera exception |
| `currency_model_error` | A bankjegy-felismerő modell nem tölthető be | Engine create fail |
| `currency_not_recognized` | Bankjegy nem felismerhető… | manualVerify fail |
| `currency_no_banknote` | Nem látok bankjegyet… | manualVerify empty slot |
| `currency_torch_on` | Gyenge fény, vaku bekapcsolva. | `speakAdd`, 8s throttle |
| `currency_no_frame` | Még nincs kamera kép… | manualVerify null bitmap |
| `currency_verify_error` | Az ellenőrzés sikertelen | manualVerify exception |
| `currency_memory_error` | Memória elfogyott… | OOM handler |
| *(hardcoded)* | Kilépéshez nyomd meg újra… | Első back press |
| `denomination.speechHu` | pl. „Ezer forint" | Sikeres felismerés |

**MainActivity belépéskor** (nem a currency modulban, de releváns):
`tts.speak("Super DL Pénzfelismerő indítása. Mutasd a kamerának a bankjegyet.")`

### 5.2 TTS integrációs diagram

```
┌─────────────────────┐     FrameEvent      ┌──────────────────────┐
│ ViewModel           │ ──────────────────► │ Activity             │
│ emitEvent()         │   Announce/SpeakAdd │ observeViewModel()   │
│ maybeEmitTorchOn()  │   PlayWorkingTick   │                      │
│ fatalError → uiState│   PlayEntryBeep     │ tts.speak()          │
└─────────────────────┘   PlayError         │ tts.speakAdd()       │
         ▲                                  │ scanBeepPlayer       │
         │ onFrame / manualVerify            │ sounds.play()        │
┌────────┴────────────┐                     └──────────────────────┘
│ BanknoteClassifier  │
│ Engine + filters    │
└─────────────────────┘

Gesztusok ──► Activity közvetlenül ──► tts.speak() / speakThen()
LaunchedEffect(fatalError) ──► tts.runWhenReady { speak() }
```

### 5.3 TTS audio routing (accessibility-first)

- `USAGE_ASSISTANCE_ACCESSIBILITY`
- `CONTENT_TYPE_SPEECH`
- `FLAG_AUDIBILITY_ENFORCED`
- Stream: `STREAM_ACCESSIBILITY`
- `speak()` = `QUEUE_FLUSH` (felülírja az előzőt)
- `speakAdd()` = `QUEUE_ADD` (vaku üzenet nem szakítja meg a címlet bemondást)

---

## 6. Compose UI + State Management

### 6.1 Activity ↔ ViewModel ↔ Screen összekötés

```
CurrencyRecognizerActivity
├── by viewModels() → CurrencyRecognizerViewModel
├── setContent { CurrencyRecognizerScreen(uiState, callbacks) }
├── collectAsStateWithLifecycle(uiState) → Compose recomposition
├── observeViewModel() → events StateFlow → TTS (side effect, nem Compose)
└── FrameAnalyzer → viewModel.onFrame(bitmap)
```

**PreviewView lifecycle:**
1. `AndroidView factory` létrehozza a `PreviewView`-t
2. `onPreviewViewReady(preview)` → Activity eltárolja → `bindCamera()` ha scanning
3. `initialize()` callback → `scanning=true` → `bindCamera(previewView)`

### 6.2 CurrencyRecognizerUiState mezők

| Mező | Típus | Jelentés |
|------|-------|----------|
| `statusText` | String | Felső státuszsor (scanning/detected/címlet) |
| `hintText` | String | Alsó gesztus hint |
| `isScanning` | Boolean | Aktív szkennelés |
| `isTwoStageEnabled` | Boolean | YOLO detektor betöltve-e |
| `pipelineMode` | BanknotePipelineMode? | TWO_STAGE / ROI_FALLBACK / FULL_FRAME_FALLBACK |
| `detectionBox` | RectF? | Normalizált bbox (0–1) |
| `showDetectionOverlay` | Boolean | Debug build + bbox → zöld keret |
| `fatalError` | String? | Modell betöltési hiba → LaunchedEffect TTS |

### 6.3 ViewModel belső állapot (nem UI StateFlow)

| Állapot | Típus | Szerep |
|---------|-------|--------|
| `engine` | BanknoteClassifierEngine? | TFLite interpreters |
| `scanning` | AtomicBoolean | Frame feldolgozás gate |
| `frameMutex` | Mutex | Egyszerre 1 frame |
| `engineMutex` | Mutex | Interpreter thread safety |
| `debouncer` | BanknoteScanDebouncer | Announce cooldown |
| `consensusFilter` | BanknoteConsensusFilter | 3/4 frame egyezés |
| `torchController` | BanknoteTorchController | Vaku |
| `pendingEvents` | ArrayDeque | Event queue |
| `lastTorchSpeechAt` | Long | 8s TTS throttle |

### 6.4 Frame feldolgozási flow (ViewModel)

```
onFrame(bitmap)
  → copyFrame (ARGB_8888 másolat)
  → BanknoteFrameGate.evaluate
  → torchController.update
  → [empty?] reset filters, return
  → PlayWorkingTick event
  → engine.classify(bitmap)
  → consensusFilter.submit → stableResult?
  → [null?] absent handling, return
  → debouncer.onDetected → Announce/Ignored/Removed
  → updateStatus + FrameEvent.Announce
```

---

## 7. Kritikus Metódusok és Osztályok

### 7.1 BanknoteYoloDetector.kt — lényegi részek

```kotlin
internal class BanknoteYoloDetector private constructor(...) : Closeable {

    fun detect(bitmap: Bitmap): List<BanknoteDetection> {
        // TensorImage FLOAT32 → Resize 640×640 BILINEAR → interpreter.run
        return YoloOutputParser.parse(
            output = outputBuffer,
            confThreshold = 0.55f,
            iouThreshold = 0.45f,
            maxDetections = 3
        )
    }

    fun bestDetection(bitmap: Bitmap): BanknoteDetection? =
        detect(bitmap)
            .filter { it.areaFraction >= 0.06f }
            .maxByOrNull { it.confidence * (0.75f + it.areaFraction.coerceAtMost(0.5f)) }

    companion object {
        private const val MODEL_FILE = "huf_banknote_detector.tflite"  // [HIÁNYZIK]
        // tryCreate → null on any failure
        // NNAPI enabled, numThreads = 2
    }
}
```

### 7.2 BanknoteDenominationClassifier.kt — lényegi részek

```kotlin
internal class BanknoteDenominationClassifier private constructor(...) : Closeable {

    fun classify(bitmap: Bitmap, applyColorCheck: Boolean = true): BanknoteClassificationResult? {
        // 1. runInference → 7 class softmax
        // 2. none class compete check: noneConfidence > best + 0.08 → null
        // 3. BanknoteDenomination.fromLabel(label)
        // 4. BanknoteColorVerifier.verify (optional)
        // 5. return BanknoteClassificationResult
    }

    companion object {
        MODEL_FILE = "huf_banknote_classifier.tflite"  // ✓ megvan
        LABEL_FILE = "huf_banknote_labels.txt"          // none + 6 címlet
        INPUT_SIZE = 224
        NUM_CLASSES = 7
        // create() throws IllegalStateException if labels empty
    }
}
```

### 7.3 BanknoteClassificationResult.kt — teljes

```kotlin
enum class BanknotePipelineMode {
    TWO_STAGE, ROI_FALLBACK, FULL_FRAME_FALLBACK
}

data class BanknoteClassificationResult(
    val denomination: BanknoteDenomination,
    val confidence: Float,
    val secondBestConfidence: Float = 0f,
    val noneConfidence: Float = 0f,
    val colorVerdict: BanknoteColorVerifier.Verdict = BanknoteColorVerifier.Verdict.NEUTRAL,
    val detectionConfidence: Float = 0f,
    val pipelineMode: BanknotePipelineMode = BanknotePipelineMode.FULL_FRAME_FALLBACK,
    val detectionBox: RectF? = null
) {
    val fusedConfidence: Float
        get() = when (pipelineMode) {
            BanknotePipelineMode.TWO_STAGE ->
                (confidence * 0.72f) + (detectionConfidence.coerceAtLeast(0f) * 0.28f)
            else -> confidence
        }

    fun isReliable(threshold=0.52f, margin=0.10f, strictColor=true): Boolean { ... }
    fun isReliableForManualCheck(): Boolean { ... }  // relaxed thresholds
}
```

### 7.4 BanknoteDetection.kt — teljes

```kotlin
data class BanknoteDetection(
    val label: String,
    val classIndex: Int,
    val confidence: Float,
    val boundingBox: RectF
) {
    val denomination: BanknoteDenomination? = BanknoteDenomination.fromLabel(label)
    val areaFraction: Float get() = boundingBox.width() * boundingBox.height()
}
```

### 7.5 BanknoteBitmapCropper.kt — teljes

```kotlin
internal object BanknoteBitmapCropper {
    fun crop(bitmap, detection, paddingFraction=0.06f): Bitmap?
    fun centerRoi(bitmap, widthFraction=0.72f, heightFraction=0.58f): Bitmap?
    // MIN_CROP_PX = 48
}
```

### 7.6 BanknoteColorVerifier.kt — teljes

Lásd 2. szekció fenti fájlok között — `verify()` → AGREE / NEUTRAL / DISAGREE a domináns hue alapján, címlet-specifikus `expectedHueRange`.

### 7.7 BanknoteConsensusFilter.kt — teljes

```kotlin
class BanknoteConsensusFilter(windowSize=4, requiredAgreements=3) {
    fun submit(frameDecision, result): BanknoteClassificationResult?
    fun reset()
}
```

### 7.8 BanknoteScanDebouncer.kt — teljes

```kotlin
class BanknoteScanDebouncer(cooldownMs=3200L, absenceFramesRequired=6) {
    fun onAbsentFrame(): BillPresenceEvent
    fun onDetected(result): ScanDecision  // Announce / Ignored / BillRemoved
    fun markAnnounced(denomination)
    fun reset()
}
```

### 7.9 BanknoteFrameGate.kt — teljes

Lásd 4.4 szekció — `evaluate(bitmap): Decision`.

### 7.10 BanknoteTorchController.kt — teljes

Lásd 4.7 szekció.

### 7.11 ScanBeepPlayer.kt — teljes

```kotlin
class ScanBeepPlayer : Closeable {
    fun playWorkingTick()  // TONE_PROP_ACK, 35ms, vol 28
    fun playScanStart()    // TONE_PROP_BEEP2, 130ms
}
```

### 7.12 YoloOutputParser.kt — **[TÖREDÉKES összefoglaló]**

265 soros fájl. Fő belépési pont:

```kotlin
internal object YoloOutputParser {
    fun parse(output, outputShape, labels, confThreshold, iouThreshold, maxDetections): List<BanknoteDetection>
    // Támogatott layoutok:
    //   3D tensor: raw channels-first, anchors-first, end-to-end [1, max_det, 6]
    //   2D tensor: end-to-end rows
    // NMS: nonMaxSuppression(iouThreshold)
    // Box normalizálás: 0–1 ha x2,y2 <= 1.5
}
```

### 7.13 SwipeGestureListener.kt — teljes (külső, de kritikus)

```kotlin
class SwipeGestureListener(context, onSwipeUp, onSwipeDown, onSwipeRight, onSwipeLeft)
    : GestureDetector.SimpleOnGestureListener() {
    val detector = GestureDetector(context, this)
    override fun onDown(e): Boolean = true
    override fun onFling(...): Boolean  // 100px + 100px/s küszöb
}
```

### 7.14 CameraAnalysisConfig.kt — teljes

```kotlin
object CameraAnalysisConfig {
    private val analysisSize = Size(640, 480)
    fun imageAnalysisBuilder(): ImageAnalysis.Builder =
        ImageAnalysis.Builder()
            .setResolutionSelector(640×480, FALLBACK_RULE_CLOSEST_LOWER)
            .setBackpressureStrategy(STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(OUTPUT_IMAGE_FORMAT_RGBA_8888)
}
```

---

## Függelék: Teljes frame-idővonal (egy sikeres felismerés)

```
t=0    MainActivity → startActivity(CurrencyRecognizerActivity)
t=1    onCreate → setContent, gestureListener, observeViewModel
t=2    initialize() IO thread → BanknoteClassifierEngine.create()
       → detector=null (YOLO hiány), classifier OK
       → isTwoStageEnabled=false
t=3    onReady → TTS intro, scanning=true, bindCamera
t=4    FrameAnalyzer: imageProxy.toBitmap() (260ms throttle)
t=5    viewModel.onFrame → copyFrame → FrameGate (not empty)
t=6    engine.classify → ROI_FALLBACK vagy FULL_FRAME_FALLBACK
t=7    consensusFilter: 4 frame, 3 egyezés → stableResult
t=8    debouncer.onDetected → Announce(playEntryBeep=true)
t=9    events → PlayEntryBeep + Announce("Ezer forint")
t=10   Activity → scanBeep + tts.speak("Ezer forint")
```

---

*Dokumentum készítve kódbázis statikus analízisből, 2026-07-03. Minden forráskód a generálás időpontjában aktuális verzió.*