package com.superdl.launcher.locationwatch

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
import com.superdl.launcher.textreader.TextRecognitionEngine
import com.superdl.launcher.tts.TtsManager
import com.superdl.launcher.util.postWhenAlive
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

@ExperimentalGetImage
class LocationWatchActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var sounds: SoundFeedback
    private lateinit var tts: TtsManager
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private val mainHandler = Handler(Looper.getMainLooper())

    private var recognitionEngine: TextRecognitionEngine? = null
    private val debouncer = LocationAnnounceDebouncer()
    private val scanning = AtomicBoolean(false)
    private val memoryFailureHandled = AtomicBoolean(false)
    private val lastFrameProcessedAt = AtomicLong(0L)
    private val latestFrameBitmap = AtomicReference<Bitmap?>(null)
    private var imageAnalysis: ImageAnalysis? = null
    private var watchTarget: LocationWatchTarget? = null
    private var watchProfile: LocationProfile? = null
    private var allProfiles: List<LocationProfile> = emptyList()
    private var lastBackPressAt = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_location_watch)
        title = getString(R.string.location_watch_title)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvLocationWatchStatus)
        CameraStabilityHelper.configurePreviewView(findViewById(R.id.locationWatchPreview))
        sounds = SoundFeedback(this)
        tts = TtsManager(this)
        cameraExecutor = Executors.newSingleThreadExecutor()

        watchTarget = resolveWatchTarget()
        if (watchTarget == null) {
            sounds.play(SoundType.ACTION_ERROR)
            tts.runWhenReady {
                tts.speakThen(getString(R.string.location_watch_no_target)) { finish() }
            }
            return
        }
        LocationWatchState.setActive(watchTarget)
        watchProfile = (watchTarget as? LocationWatchTarget.ProfileId)?.let {
            LocationProfileStore.getById(this, it.id)
        }
        if (watchTarget is LocationWatchTarget.AllProfiles) {
            allProfiles = LocationProfileStore.getAll(this)
        }

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { sounds.play(SoundType.SWIPE_UP) },
            onSwipeDown = { sounds.play(SoundType.SWIPE_DOWN) },
            onSwipeRight = { sounds.play(SoundType.SWIPE_RIGHT) },
            onSwipeLeft = { stopWatch() }
        )

        findViewById<View>(R.id.locationWatchRoot).setOnTouchListener { view, event ->
            gestureListener.detector.onTouchEvent(event)
            if (event.action == android.view.MotionEvent.ACTION_UP) {
                view.performClick()
            }
            true
        }

        findViewById<Button>(R.id.btnLocationWatchExit).setOnClickListener { stopWatch() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val now = System.currentTimeMillis()
                if (now - lastBackPressAt < 2000L) {
                    stopWatch()
                } else {
                    lastBackPressAt = now
                    tts.speak(getString(R.string.location_watch_back_hint))
                }
            }
        })

        if (hasCameraPermission()) {
            initializeWatch()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
        }
    }

    private fun resolveWatchTarget(): LocationWatchTarget? {
        if (intent.getBooleanExtra(EXTRA_WATCH_ALL, false)) {
            return LocationWatchTarget.AllProfiles
        }
        intent.getStringExtra(EXTRA_TARGET_PROFILE_ID)?.takeIf { it.isNotBlank() }?.let {
            return LocationWatchTarget.ProfileId(it)
        }
        intent.getStringExtra(EXTRA_TARGET_FREE_TEXT)?.takeIf { it.isNotBlank() }?.let {
            return LocationWatchTarget.FreeText(it)
        }
        return LocationWatchState.getActive()
    }

    private fun initializeWatch() {
        recognitionEngine = TextRecognitionEngine()
        val status = statusLabelForTarget()
        setStatusText(status)
        tts.runWhenReady { tts.speak(introTextForTarget()) }
        scanning.set(true)
        startCamera()
    }

    private fun statusLabelForTarget(): String = when (val target = watchTarget) {
        is LocationWatchTarget.ProfileId -> {
            val name = watchProfile?.name ?: target.id
            getString(R.string.location_watch_status_profile, name)
        }
        is LocationWatchTarget.FreeText -> getString(R.string.location_watch_status_text, target.text)
        is LocationWatchTarget.AllProfiles -> getString(R.string.location_watch_status_all_profiles)
        null -> getString(R.string.location_watch_status_scanning)
    }

    private fun introTextForTarget(): String = when (val target = watchTarget) {
        is LocationWatchTarget.ProfileId -> {
            val name = watchProfile?.name ?: getString(R.string.location_watch_unknown_profile)
            getString(R.string.location_watch_intro_profile, name)
        }
        is LocationWatchTarget.FreeText ->
            getString(R.string.location_watch_intro_text, target.text)
        is LocationWatchTarget.AllProfiles ->
            getString(R.string.location_watch_intro_all_profiles)
        null -> getString(R.string.location_watch_status_scanning)
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val preview = CameraStabilityHelper.buildLightPreview(
                findViewById<PreviewView>(R.id.locationWatchPreview).surfaceProvider
            )
            imageAnalysis = CameraStabilityHelper.buildLightImageAnalysis()
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
                setStatusText(getString(R.string.location_watch_camera_error))
                tts.runWhenReady { tts.speak(getString(R.string.location_watch_camera_error)) }
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun onOcrResult(raw: String) {
        val target = watchTarget ?: return
        val frameBitmap = latestFrameBitmap.get()?.takeUnless { it.isRecycled }

        val announcement = when (target) {
            is LocationWatchTarget.ProfileId -> {
                val profile = watchProfile ?: LocationProfileStore.getById(this, target.id)
                watchProfile = profile
                if (profile == null || !LocationMatcher.isProfileMatch(profile, raw, frameBitmap)) return
                if (!debouncer.shouldAnnounce(target.debounceKey())) return
                getString(R.string.location_watch_match_profile, profile.name)
            }
            is LocationWatchTarget.FreeText -> {
                if (raw.isBlank() || !LocationMatcher.matchTargetText(target.text, raw)) return
                if (!debouncer.shouldAnnounce(target.debounceKey())) return
                getString(R.string.location_watch_match_text, target.text)
            }
            is LocationWatchTarget.AllProfiles -> {
                val profiles = allProfiles.ifEmpty { LocationProfileStore.getAll(this) }.also { allProfiles = it }
                val matched = profiles.firstOrNull { LocationMatcher.isProfileMatch(it, raw, frameBitmap) } ?: return
                val debounceKey = LocationWatchTarget.ProfileId(matched.id).debounceKey()
                if (!debouncer.shouldAnnounce(debounceKey)) return
                getString(R.string.location_watch_match_profile, matched.name)
            }
        }

        postWhenAlive {
            sounds.play(SoundType.ACTION_OK)
            setStatusText(announcement)
            tts.speak(announcement)
        }
    }

    private fun stopWatch() {
        scanning.set(false)
        debouncer.reset()
        LocationWatchState.clear()
        sounds.play(SoundType.SWIPE_LEFT)
        tts.speakThen(getString(R.string.location_watch_exit)) { finish() }
    }

    private fun setStatusText(text: String) {
        postWhenAlive { tvStatus.text = text }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
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
                initializeWatch()
            } else {
                sounds.play(SoundType.ACTION_ERROR)
                setStatusText(getString(R.string.location_watch_permission_denied))
                tts.runWhenReady { tts.speak(getString(R.string.location_watch_permission_denied)) }
                LocationWatchState.clear()
                finish()
            }
        }
    }

    override fun onDestroy() {
        scanning.set(false)
        mainHandler.removeCallbacksAndMessages(null)
        if (LocationWatchState.getActive() == watchTarget) {
            LocationWatchState.clear()
        }
        imageAnalysis?.clearAnalyzer()
        imageAnalysis = null
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        recognitionEngine?.close()
        recognitionEngine = null
        latestFrameBitmap.getAndSet(null)?.recycle()
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

            val engine = recognitionEngine
            if (engine == null) {
                imageProxy.close()
                return
            }

            try {
                val bitmap = imageProxy.toBitmap()
                latestFrameBitmap.getAndSet(bitmap)?.recycle()
                val frameCopy = try {
                    bitmap.copy(Bitmap.Config.ARGB_8888, false)
                } catch (_: OutOfMemoryError) {
                    postWhenAlive { handleMemoryFailure() }
                    return
                } ?: return
                engine.recognize(
                    bitmap = frameCopy,
                    onResult = { raw ->
                        postWhenAlive {
                            onOcrResult(raw)
                            if (!frameCopy.isRecycled) frameCopy.recycle()
                        }
                    },
                    onError = {
                        if (!frameCopy.isRecycled) frameCopy.recycle()
                    }
                )
            } catch (oom: OutOfMemoryError) {
                System.gc()
                postWhenAlive { handleMemoryFailure() }
            } catch (_: Exception) {
            } finally {
                imageProxy.close()
            }
        }
    }

    private fun handleMemoryFailure() {
        if (!memoryFailureHandled.compareAndSet(false, true)) return
        scanning.set(false)
        imageAnalysis?.clearAnalyzer()
        sounds.play(SoundType.ACTION_ERROR)
        setStatusText(getString(R.string.camera_memory_error))
        tts.speak(getString(R.string.camera_memory_error))
    }

    companion object {
        private const val REQ_CAMERA = 7111
        private const val FRAME_INTERVAL_MS = 2500L
        const val EXTRA_TARGET_PROFILE_ID = "location_watch_profile_id"
        const val EXTRA_TARGET_FREE_TEXT = "location_watch_free_text"
        const val EXTRA_WATCH_ALL = "location_watch_all"

        fun intentForProfile(context: Context, profileId: String): Intent =
            Intent(context, LocationWatchActivity::class.java)
                .putExtra(EXTRA_TARGET_PROFILE_ID, profileId)

        fun intentForFreeText(context: Context, text: String): Intent =
            Intent(context, LocationWatchActivity::class.java)
                .putExtra(EXTRA_TARGET_FREE_TEXT, text)

        fun intentForAllProfiles(context: Context): Intent =
            Intent(context, LocationWatchActivity::class.java)
                .putExtra(EXTRA_WATCH_ALL, true)
    }
}