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
import com.superdl.launcher.currency.cascade.BanknoteCascadeConfig
import com.superdl.launcher.currency.cascade.BanknoteCascadeUseCase
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

/**
 * UI ViewModel: a kaszkád UseCase-t hívja, a UI csak a végeredményt kapja.
 *
 * Prioritás (kódolt a UseCase-ben, nem itt):
 *   1. Szín + geometria
 *   2. OCR
 *   3. YOLO fallback (alapból off)
 */
class CurrencyRecognizerViewModel(application: Application) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(CurrencyRecognizerUiState())
    val uiState: StateFlow<CurrencyRecognizerUiState> = _uiState.asStateFlow()

    /** Opcionális YOLO engine — csak ha a fallback engedélyezett. */
    @Volatile
    private var yoloEngine: BanknoteClassifierEngine? = null

    private var cascade: BanknoteCascadeUseCase? = null

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

    /** Utolsó bemondott speech — dupla emit védelem (TTS flicker). */
    @Volatile
    private var lastSpokenText: String? = null
    @Volatile
    private var lastSpokenAt: Long = 0L

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
                val useCase = BanknoteCascadeUseCase(
                    yoloFallbackEnabled = BanknoteCascadeConfig.YOLO_FALLBACK_ENABLED
                )
                cascade = useCase

                // YOLO csak ha explicit fallback — ne töltsünk 37 MB modellt feleslegesen.
                val engine = if (BanknoteCascadeConfig.YOLO_FALLBACK_ENABLED) {
                    withContext(Dispatchers.IO) {
                        try {
                            BanknoteClassifierEngine.create(getApplication())
                        } catch (e: Exception) {
                            android.util.Log.w("SDL_CASH", "YOLO engine nem töltődött: ${e.message}")
                            null
                        }
                    }
                } else {
                    android.util.Log.i(
                        "SDL_CASH",
                        "Kaszkád aktív: szín→OCR, YOLO fallback KIKAPCSOLVA"
                    )
                    null
                }
                yoloEngine = engine

                scanning.set(true)
                _uiState.update {
                    it.copy(
                        statusText = getString(R.string.currency_status_active),
                        hintText = getString(R.string.currency_hint),
                        isScanning = true,
                        isTwoStageEnabled = false, // fő útvonal nem YOLO
                        cascadeMode = true,
                        yoloFallbackEnabled = BanknoteCascadeConfig.YOLO_FALLBACK_ENABLED && engine != null,
                        fatalError = null
                    )
                }
                onReady()
            } catch (e: Exception) {
                android.util.Log.e("SDL_CASH", "Init hiba: ${e.message}", e)
                cascade = null
                yoloEngine = null
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
        if (!scanning.get() || cascade == null) return

        viewModelScope.launch(Dispatchers.Default) {
            frameMutex.withLock {
                if (!scanning.get() || cascade == null) return@withLock
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
        val useCase = cascade ?: return

        val frameDecision = BanknoteFrameGate.evaluate(bitmap)
        val torchJustOn = torchController.update(frameDecision.metrics)
        if (torchJustOn) {
            maybeEmitTorchOn()
        }

        if (frameDecision.isEmptySlot) {
            when (debouncer.onAbsentFrame()) {
                BanknoteScanDebouncer.BillPresenceEvent.REMOVED -> {
                    updateStatus(getString(R.string.currency_status_scanning))
                    cascade?.resetSession()
                    lastSpokenText = null
                }
                else -> Unit
            }
            consensusFilter.reset()
            clearOverlay()
            return
        }

        emitEvent(FrameEvent.PlayWorkingTick)

        // ── Prioritásos kaszkád (szín → OCR → opcionális YOLO) ────────────
        val rawResult = try {
            if (BanknoteCascadeConfig.YOLO_FALLBACK_ENABLED && yoloEngine != null) {
                engineMutex.withLock {
                    useCase.recognizeFrame(bitmap, yoloEngine)
                }
            } else {
                useCase.recognizeFrame(bitmap, yoloEngine = null)
            }
        } catch (e: Exception) {
            android.util.Log.w("SDL_CASH", "Kaszkád hiba: ${e.message}")
            null
        }

        val stableResult = consensusFilter.submit(frameDecision, rawResult)
        updateOverlay(rawResult)

        if (stableResult == null) {
            when (debouncer.onAbsentFrame()) {
                BanknoteScanDebouncer.BillPresenceEvent.REMOVED -> {
                    updateStatus(getString(R.string.currency_status_scanning))
                    cascade?.resetSession()
                    lastSpokenText = null
                }
                else -> Unit
            }
            return
        }

        when (val decision = debouncer.onDetected(stableResult)) {
            is BanknoteScanDebouncer.ScanDecision.Announce -> {
                val speech = decision.result.denomination.speechHu
                // Dupla TTS védelem: ugyanaz a szöveg 2 s-en belül ne menjen újra.
                if (shouldSpeak(speech)) {
                    if (decision.playEntryBeep) {
                        emitEvent(FrameEvent.PlayEntryBeep)
                        updateStatus(getString(R.string.currency_status_detected))
                    }
                    updateStatus(speech)
                    emitEvent(
                        FrameEvent.Announce(
                            speech = speech,
                            playEntryBeep = false
                        )
                    )
                    markSpoken(speech)
                    debouncer.markAnnounced(decision.result.denomination)
                }
            }
            BanknoteScanDebouncer.ScanDecision.BillRemoved -> {
                updateStatus(getString(R.string.currency_status_scanning))
                cascade?.resetSession()
                lastSpokenText = null
            }
            BanknoteScanDebouncer.ScanDecision.Ignored -> Unit
        }
    }

    fun manualVerify(bitmap: Bitmap?) {
        val useCase = cascade
        if (useCase == null) {
            emitEvent(FrameEvent.Announce(getString(R.string.currency_model_error), playEntryBeep = false))
            return
        }
        if (bitmap == null) {
            emitEvent(FrameEvent.Announce(getString(R.string.currency_no_frame), playEntryBeep = false))
            return
        }

        viewModelScope.launch(Dispatchers.Default) {
            frameMutex.withLock {
                val frame = copyFrame(bitmap) ?: run {
                    emitEvent(FrameEvent.Announce(getString(R.string.currency_no_frame), playEntryBeep = false))
                    return@withLock
                }
                try {
                    val frameDecision = BanknoteFrameGate.evaluate(frame)
                    torchController.update(frameDecision.metrics)

                    if (frameDecision.isEmptySlot) {
                        emitEvent(FrameEvent.PlayEntryBeep)
                        emitEvent(
                            FrameEvent.Announce(
                                getString(R.string.currency_no_banknote),
                                playEntryBeep = false
                            )
                        )
                        updateStatus(getString(R.string.currency_status_scanning))
                        clearOverlay()
                        return@withLock
                    }

                    if (frameDecision.needsMoreLight) {
                        torchController.forceOn()
                        maybeEmitTorchOn()
                    }

                    val result = try {
                        useCase.recognizeManual(frame, yoloEngine)
                    } catch (e: Exception) {
                        android.util.Log.w("SDL_CASH", "Manuális kaszkád hiba: ${e.message}")
                        null
                    }
                    updateOverlay(result)

                    if (result == null || !result.isReliableForManualCheck()) {
                        emitEvent(FrameEvent.PlayEntryBeep)
                        emitEvent(
                            FrameEvent.Announce(
                                getString(R.string.currency_not_recognized),
                                playEntryBeep = false
                            )
                        )
                        updateStatus(getString(R.string.currency_status_scanning))
                        return@withLock
                    }

                    val speech = result.denomination.speechHu
                    updateStatus(speech)
                    if (shouldSpeak(speech, minIntervalMs = 800L)) {
                        emitEvent(FrameEvent.Announce(speech, playEntryBeep = false))
                        markSpoken(speech)
                    }
                    debouncer.markAnnounced(result.denomination)
                } catch (_: Exception) {
                    emitEvent(FrameEvent.PlayError)
                    emitEvent(
                        FrameEvent.Announce(
                            getString(R.string.currency_verify_error),
                            playEntryBeep = false
                        )
                    )
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
        cascade?.resetSession()
        torchController.release()
        lastSpokenText = null
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
                    cascade?.close()
                    cascade = null
                    yoloEngine?.close()
                    yoloEngine = null
                }
            }
        }
    }

    fun consumeEvent() {
        synchronized(pendingEvents) {
            _events.value = if (pendingEvents.isEmpty()) null else pendingEvents.removeFirst()
        }
    }

    private fun shouldSpeak(text: String, minIntervalMs: Long = 2000L): Boolean {
        val now = System.currentTimeMillis()
        if (text == lastSpokenText && now - lastSpokenAt < minIntervalMs) return false
        return true
    }

    private fun markSpoken(text: String) {
        lastSpokenText = text
        lastSpokenAt = System.currentTimeMillis()
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
            // TTS Announce: ne soroljunk több ugyanolyan speech-et.
            if (event is FrameEvent.Announce) {
                val pendingSame = pendingEvents.any {
                    it is FrameEvent.Announce && it.speech == event.speech
                }
                val currentSame = (_events.value as? FrameEvent.Announce)?.speech == event.speech
                if (pendingSame || currentSame) return
            }
            if (_events.value == null) {
                _events.value = event
            } else {
                pendingEvents.addLast(event)
            }
        }
    }

    private fun copyFrame(bitmap: Bitmap): Bitmap? =
        try {
            if (bitmap.isRecycled) null
            else bitmap.copy(Bitmap.Config.ARGB_8888, false)
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
