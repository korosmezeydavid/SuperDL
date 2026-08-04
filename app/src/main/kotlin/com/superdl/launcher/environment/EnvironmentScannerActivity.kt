package com.superdl.launcher.environment

import android.Manifest
import android.content.pm.PackageManager
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
import com.superdl.launcher.camera.CameraAnalysisConfig
import com.superdl.launcher.camera.CameraStabilityHelper
import com.superdl.launcher.util.postWhenAlive
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager
import org.tensorflow.lite.support.image.TensorImage
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

@ExperimentalGetImage
class EnvironmentScannerActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var tvLastDetection: TextView
    private lateinit var btnScanToggle: Button
    private lateinit var categoryButtons: Map<ObjectCategory, Button>
    private lateinit var sounds: SoundFeedback
    private lateinit var tts: TtsManager
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private val mainHandler = Handler(Looper.getMainLooper())

    private var detectionEngine: ObjectDetectionEngine? = null
    private val debouncer = AnnouncementDebouncer()
    private val mutedCategories = mutableSetOf<ObjectCategory>()
    private val scanning = AtomicBoolean(false)
    private val memoryFailureHandled = AtomicBoolean(false)
    private val lastFrameProcessedAt = AtomicLong(0L)
    private val latestDetections = AtomicReference<List<DetectionResult>>(emptyList())
    private var imageAnalysis: ImageAnalysis? = null
    private var lastBackPressAt = 0L

    // Egyesített mód: megnyitáskor pillanatkép ("Mi van előttem?"), a
    // folyamatos figyelés (régi Kitekintő) le söpréssel kapcsolható be-ki.
    private var snapshotMode = true
    private var continuousEnabled = false
    private val snapshotActive = AtomicBoolean(false)
    private val snapshotDeadline = AtomicLong(0L)
    private val snapshotBest = AtomicReference<List<DetectionResult>>(emptyList())
    private var lastSummary: String? = null
    private var snapshotHintGiven = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_environment_scanner)
        title = getString(R.string.env_scanner_title)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        bindViews()
        sounds = SoundFeedback(this)
        tts = TtsManager(this)
        cameraExecutor = Executors.newSingleThreadExecutor()

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                repeatSnapshotSummary()
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                toggleContinuousWatch()
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                startSnapshot()
            },
            onSwipeLeft = { finishScanner() }
        )

        findViewById<View>(R.id.envScannerRoot).setOnTouchListener { view, event ->
            gestureListener.detector.onTouchEvent(event)
            if (event.action == android.view.MotionEvent.ACTION_UP) {
                view.performClick()
            }
            true
        }

        findViewById<Button>(R.id.btnEnvExit).setOnClickListener { finishScanner() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val now = System.currentTimeMillis()
                if (now - lastBackPressAt < 2000L) {
                    finishScanner()
                } else {
                    lastBackPressAt = now
                    tts.speak("Kilépéshez nyomd meg újra a vissza gombot, vagy balra söpörj.")
                }
            }
        })

        btnScanToggle.setOnClickListener { toggleScanning() }
        setupCategoryButtons()

        if (hasCameraPermission()) {
            initializeScanner()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
        }
    }

    private fun bindViews() {
        tvStatus = findViewById(R.id.tvEnvScannerStatus)
        tvLastDetection = findViewById(R.id.tvEnvLastDetection)
        btnScanToggle = findViewById(R.id.btnEnvScanToggle)
        categoryButtons = mapOf(
            ObjectCategory.DOOR to findViewById(R.id.btnMuteDoor),
            ObjectCategory.CHAIR to findViewById(R.id.btnMuteChair),
            ObjectCategory.TABLE to findViewById(R.id.btnMuteTable),
            ObjectCategory.PERSON to findViewById(R.id.btnMutePerson),
            ObjectCategory.FLOOR_OBJECT to findViewById(R.id.btnMuteFloor),
            ObjectCategory.PHONE to findViewById(R.id.btnMutePhone)
        )
    }

    private fun setupCategoryButtons() {
        categoryButtons.forEach { (category, button) ->
            updateCategoryButton(category, button)
            button.setOnClickListener {
                sounds.play(SoundType.SWIPE_RIGHT)
                if (category in mutedCategories) {
                    mutedCategories.remove(category)
                } else {
                    mutedCategories.add(category)
                }
                updateCategoryButton(category, button)
                val state = if (category in mutedCategories) "némítva" else "bekapcsolva"
                tts.speak("${category.hungarianName} kategória $state.")
            }
        }
    }

    private fun updateCategoryButton(category: ObjectCategory, button: Button) {
        val muted = category in mutedCategories
        button.text = if (muted) {
            getString(R.string.env_scanner_category_muted, category.hungarianName)
        } else {
            getString(R.string.env_scanner_category_active, category.hungarianName)
        }
        button.isSelected = !muted
    }

    private fun initializeScanner() {
        try {
            detectionEngine = ObjectDetectionEngine(this)
        } catch (_: Exception) {
            sounds.play(SoundType.ACTION_ERROR)
            setStatusText(getString(R.string.env_scanner_model_error))
            tts.runWhenReady { tts.speak(getString(R.string.env_scanner_model_error)) }
            return
        }

        if (snapshotMode) {
            tts.runWhenReady {
                tts.speak("Mi van előttem. Tartsd a telefont magad elé, egy pillanat.")
            }
            setStatusText("Mi van előttem?")
            startCamera()
            setScanningEnabled(true)
            startSnapshot(announce = false)
            return
        }

        tts.runWhenReady { tts.speak(getString(R.string.env_scanner_intro)) }
        setStatusText(getString(R.string.env_scanner_status_ready))
        startCamera()
        setScanningEnabled(true)
    }

    /** Folyamatos figyelés (a régi Kitekintő-mód) be-ki kapcsolása le söpréssel. */
    private fun toggleContinuousWatch() {
        continuousEnabled = !continuousEnabled
        debouncer.clear()
        if (continuousEnabled) {
            setStatusText("Folyamatos figyelés")
            tts.speak(
                "Folyamatos figyelés bekapcsolva. Mozgasd lassan a kamerát, " +
                    "és bemondom amit látok. Le söprés: kikapcsolás."
            )
        } else {
            setStatusText("Mi van előttem?")
            tts.speak("Folyamatos figyelés kikapcsolva. Jobbra söprés: új pillanatkép.")
        }
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val previewView = findViewById<PreviewView>(R.id.envPreview)
            CameraStabilityHelper.configurePreviewView(previewView)
            val preview = CameraStabilityHelper.buildLightPreview(previewView.surfaceProvider)
            imageAnalysis = CameraAnalysisConfig.imageAnalysisBuilder()
                .build()
                .also { analysis ->
                    analysis.setAnalyzer(cameraExecutor, FrameAnalyzer())
                }
            try {
                provider.unbindAll()
                provider.bindToLifecycle(
                    this,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    imageAnalysis
                )
            } catch (_: Exception) {
                sounds.play(SoundType.ACTION_ERROR)
                setStatusText(getString(R.string.env_scanner_camera_error))
                tts.runWhenReady { tts.speak(getString(R.string.env_scanner_camera_error)) }
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun toggleScanning() {
        sounds.play(SoundType.SWIPE_RIGHT)
        setScanningEnabled(!scanning.get())
    }

    private fun setScanningEnabled(enabled: Boolean) {
        scanning.set(enabled)
        debouncer.clear()
        if (enabled) {
            btnScanToggle.text = getString(R.string.env_scanner_stop)
            btnScanToggle.contentDescription = getString(R.string.env_scanner_stop_desc)
            if (!snapshotMode) {
                setStatusText(getString(R.string.env_scanner_status_scanning))
                tts.speak(getString(R.string.env_scanner_status_scanning))
            }
        } else {
            btnScanToggle.text = getString(R.string.env_scanner_start)
            btnScanToggle.contentDescription = getString(R.string.env_scanner_start_desc)
            if (!snapshotMode) {
                setStatusText(getString(R.string.env_scanner_status_paused))
                tts.speak(getString(R.string.env_scanner_status_paused))
            }
        }
    }

    private fun setStatusText(text: String) {
        postWhenAlive { tvStatus.text = text }
    }

    private fun onDetections(detections: List<DetectionResult>) {
        latestDetections.set(detections)
        // Aktív pillanatkép elsőbbséget kap; utána a folyamatos figyelés,
        // ha be van kapcsolva; különben csendben maradunk.
        if (snapshotActive.get()) {
            handleSnapshotDetections(detections)
            return
        }
        if (!continuousEnabled) return
        val visible = detections.filter { it.category !in mutedCategories }
        if (visible.isEmpty()) {
            postWhenAlive {
                tvLastDetection.text = getString(R.string.env_scanner_no_objects)
            }
            return
        }

        val primary = visible.maxByOrNull { it.confidence } ?: return
        val announcement = SpatialDescriber.formatAnnouncement(primary.category, primary.boundingBox)
        postWhenAlive {
            tvLastDetection.text = announcement
        }

        val debounceKey = "${primary.category.id}_${SpatialDescriber.describe(primary.boundingBox)}"
        if (!debouncer.shouldAnnounce(
                debounceKey,
                primary.centerX,
                primary.centerY,
                primary.area
            )
        ) {
            return
        }

        postWhenAlive {
            tts.speakAdd(announcement)
        }
    }

    // ==================== "MI VAN ELŐTTEM?" PILLANATKÉP ====================

    /** Új pillanatkép indítása: rövid ideig figyel, majd egyben elmondja a jelenetet. */
    private fun startSnapshot(announce: Boolean = true) {
        snapshotBest.set(emptyList())
        snapshotDeadline.set(0L) // az első feldolgozott képkockától számoljuk az ablakot
        snapshotActive.set(true)
        if (announce) {
            tts.speak("Pillanatkép. Egy másodperc.")
        }
        setStatusText("Figyelek…")
    }

    /**
     * A pillanatkép-ablak alatt a "leggazdagabb" képkockát tartjuk meg
     * (legtöbb találat; egyenlőségnél a magasabb össz-bizonyosság), mert
     * egyetlen kimerevített kockából a legpontosabb az összkép – a képkockák
     * összefésülése duplázná ugyanazt a tárgyat.
     */
    private fun handleSnapshotDetections(detections: List<DetectionResult>) {
        if (!snapshotActive.get()) return
        val now = System.currentTimeMillis()
        if (snapshotDeadline.get() == 0L) {
            snapshotDeadline.set(now + SNAPSHOT_WINDOW_MS)
        }

        val currentBest = snapshotBest.get()
        val better = when {
            detections.size > currentBest.size -> true
            detections.size == currentBest.size && detections.isNotEmpty() ->
                detections.sumOf { it.confidence.toDouble() } >
                    currentBest.sumOf { it.confidence.toDouble() }
            else -> false
        }
        if (better) snapshotBest.set(detections)

        if (now >= snapshotDeadline.get()) {
            finishSnapshot()
        }
    }

    private fun finishSnapshot() {
        if (!snapshotActive.compareAndSet(true, false)) return
        val best = snapshotBest.get()
        val summary = SceneSummarizer.summarize(best)
        lastSummary = summary
        val hint = if (!snapshotHintGiven) {
            snapshotHintGiven = true
            " Jobbra söprés vagy hangerőgomb: új pillanatkép. " +
                "Le söprés: folyamatos figyelés. Fel: ismétlés. Balra: kilépés."
        } else {
            ""
        }
        postWhenAlive {
            tvLastDetection.text = summary
            setStatusText("Mi van előttem?")
            tts.speak(summary + hint)
        }
    }

    private fun repeatSnapshotSummary() {
        val summary = lastSummary
        if (summary.isNullOrBlank()) {
            tts.speak("Még nincs pillanatkép. Söpörj jobbra egy újhoz.")
            return
        }
        tts.speak(summary)
    }

    private fun announceCenteredObject(flush: Boolean) {
        val detections = latestDetections.get()
            .filter { it.category !in mutedCategories }
        val centered = detections
            .filter { SpatialDescriber.isCentered(it.boundingBox) }
            .minByOrNull { SpatialDescriber.centerDistance(it.boundingBox) }
            ?: detections.minByOrNull { SpatialDescriber.centerDistance(it.boundingBox) }

        if (centered == null) {
            val message = getString(R.string.env_scanner_center_empty)
            if (flush) {
                tts.speak(message)
            } else {
                tts.speakAdd(message)
            }
            return
        }

        val announcement = SpatialDescriber.formatAnnouncement(centered.category, centered.boundingBox)
        postWhenAlive {
            tvLastDetection.text = announcement
            if (flush) {
                tts.speak(announcement)
            } else {
                tts.speakAdd(announcement)
            }
        }
    }

    private fun repeatLastDetection() {
        val detections = latestDetections.get()
        val visible = detections.filter { it.category !in mutedCategories }
        if (visible.isEmpty()) {
            tts.speak(getString(R.string.env_scanner_no_objects))
            return
        }
        val primary = visible.maxByOrNull { it.confidence } ?: return
        val announcement = SpatialDescriber.formatAnnouncement(primary.category, primary.boundingBox)
        tts.speak(announcement)
    }

    private fun finishScanner() {
        scanning.set(false)
        sounds.play(SoundType.SWIPE_LEFT)
        tts.speakThen(getString(R.string.env_scanner_exit)) { finish() }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.KEYCODE_VOLUME_DOWN -> {
                if (event?.repeatCount == 0) {
                    startSnapshot()
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
                initializeScanner()
            } else {
                sounds.play(SoundType.ACTION_ERROR)
                setStatusText(getString(R.string.env_scanner_permission_denied))
                tts.runWhenReady { tts.speak(getString(R.string.env_scanner_permission_denied)) }
                finish()
            }
        }
    }

    override fun onDestroy() {
        scanning.set(false)
        mainHandler.removeCallbacksAndMessages(null)
        imageAnalysis?.clearAnalyzer()
        imageAnalysis = null
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        detectionEngine?.close()
        detectionEngine = null
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

            val engine = detectionEngine
            if (engine == null) {
                imageProxy.close()
                return
            }

            try {
                val tensorImage = TensorImage.fromBitmap(imageProxy.toBitmap())
                val detections = engine.detect(tensorImage)
                onDetections(detections)
            } catch (oom: OutOfMemoryError) {
                System.gc()
                postWhenAlive { handleFrameMemoryFailure() }
            } catch (_: Exception) {
                // Frame dropped – keep scanning resilient.
            } finally {
                imageProxy.close()
            }
        }
    }

    private fun handleFrameMemoryFailure() {
        if (!memoryFailureHandled.compareAndSet(false, true)) return
        setScanningEnabled(false)
        imageAnalysis?.clearAnalyzer()
        sounds.play(SoundType.ACTION_ERROR)
        setStatusText(getString(R.string.env_scanner_memory_error))
        tts.speak(getString(R.string.env_scanner_memory_error))
    }

    companion object {
        private const val REQ_CAMERA = 7103
        private const val FRAME_INTERVAL_MS = 200L
        private const val SNAPSHOT_WINDOW_MS = 1600L

        /** Ha igaz, az activity "Mi van előttem?" pillanatkép-módban indul. */
        const val EXTRA_SNAPSHOT_MODE = "snapshot_mode"
    }
}