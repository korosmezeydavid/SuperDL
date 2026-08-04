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
import com.superdl.launcher.voice.VoiceInput
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

@ExperimentalGetImage
class LocationTrainerActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var sounds: SoundFeedback
    private lateinit var tts: TtsManager
    private lateinit var voiceInput: VoiceInput
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private val mainHandler = Handler(Looper.getMainLooper())

    private var recognitionEngine: TextRecognitionEngine? = null
    private val capturing = AtomicBoolean(false)
    private val memoryFailureHandled = AtomicBoolean(false)
    private val lastBufferFrameAt = AtomicLong(0L)
    private val latestBitmap = AtomicReference<Bitmap?>(null)
    private var imageAnalysis: ImageAnalysis? = null
    private var lastBackPressAt = 0L
    private var pendingCaptures: MutableList<LocationCaptureDraft> = mutableListOf()
    private var profileId: String = ""
    private var editingProfile: LocationProfile? = null

    private val isEditMode: Boolean get() = editingProfile != null

    private val maxCapturesThisSession: Int
        get() {
            val existingCount = editingProfile?.referenceImagePaths?.size ?: 0
            return (LocationProfileStore.MAX_PHOTOS_PER_PROFILE - existingCount)
                .coerceAtMost(NEW_CAPTURES_PER_SESSION)
                .coerceAtLeast(1)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_location_trainer)
        title = getString(R.string.location_trainer_title)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvLocationTrainerStatus)
        CameraStabilityHelper.configurePreviewView(findViewById(R.id.locationTrainerPreview))
        sounds = SoundFeedback(this)
        tts = TtsManager(this)
        voiceInput = VoiceInput(this)
        cameraExecutor = Executors.newSingleThreadExecutor()

        intent.getStringExtra(EXTRA_EDIT_PROFILE_ID)?.takeIf { it.isNotBlank() }?.let { id ->
            editingProfile = LocationProfileStore.getById(this, id)
            if (editingProfile != null) {
                profileId = id
            }
        }

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                finalizeCapturesAndName()
            },
            onSwipeDown = { sounds.play(SoundType.SWIPE_DOWN) },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                triggerCaptureAndOcr()
            },
            onSwipeLeft = { finishTrainer() }
        )

        findViewById<View>(R.id.locationTrainerRoot).setOnTouchListener { view, event ->
            gestureListener.detector.onTouchEvent(event)
            if (event.action == android.view.MotionEvent.ACTION_UP) {
                view.performClick()
            }
            true
        }

        findViewById<Button>(R.id.btnLocationTrainerExit).setOnClickListener { finishTrainer() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val now = System.currentTimeMillis()
                if (now - lastBackPressAt < 2000L) {
                    finishTrainer()
                } else {
                    lastBackPressAt = now
                    tts.speak(getString(R.string.location_trainer_back_hint))
                }
            }
        })

        if (editingProfile == null && intent.getStringExtra(EXTRA_EDIT_PROFILE_ID).orEmpty().isNotBlank()) {
            sounds.play(SoundType.ACTION_ERROR)
            tts.speakThen(getString(R.string.location_trainer_edit_not_found)) { finish() }
            return
        }

        if (hasCameraPermission()) {
            initializeTrainer()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
        }
    }

    private fun initializeTrainer() {
        recognitionEngine = TextRecognitionEngine()
        setStatusText(getString(R.string.location_trainer_status_ready))
        val intro = if (isEditMode) {
            getString(
                R.string.location_trainer_edit_intro,
                editingProfile!!.name,
                editingProfile!!.referenceImagePaths.size,
                maxCapturesThisSession
            )
        } else {
            getString(R.string.location_trainer_intro)
        }
        tts.runWhenReady { tts.speak(intro) }
        startCamera()
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val preview = CameraStabilityHelper.buildLightPreview(
                findViewById<PreviewView>(R.id.locationTrainerPreview).surfaceProvider
            )
            imageAnalysis = CameraStabilityHelper.buildLightImageAnalysis()
                .build()
                .also { analysis ->
                    analysis.setAnalyzer(cameraExecutor, FrameBufferAnalyzer())
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
                setStatusText(getString(R.string.location_trainer_camera_error))
                tts.runWhenReady { tts.speak(getString(R.string.location_trainer_camera_error)) }
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun triggerCaptureAndOcr() {
        if (capturing.get()) return
        val engine = recognitionEngine ?: return
        val bitmap = latestBitmap.get()
        if (bitmap == null || bitmap.isRecycled) {
            tts.speak(getString(R.string.location_trainer_no_frame))
            return
        }

        capturing.set(true)
        setStatusText(getString(R.string.location_trainer_status_capturing))
        val captureBitmap = try {
            bitmap.copy(Bitmap.Config.ARGB_8888, false)
        } catch (_: OutOfMemoryError) {
            capturing.set(false)
            handleMemoryFailure()
            return
        } ?: run {
            capturing.set(false)
            tts.speak(getString(R.string.location_trainer_recognition_error))
            return
        }
        engine.recognize(
            bitmap = captureBitmap,
            onResult = { raw ->
                postWhenAlive {
                    onCaptureReady(raw, captureBitmap)
                    if (!captureBitmap.isRecycled) captureBitmap.recycle()
                    capturing.set(false)
                }
            },
            onError = {
                postWhenAlive {
                    onCaptureReady("", captureBitmap)
                    if (!captureBitmap.isRecycled) captureBitmap.recycle()
                    capturing.set(false)
                }
            }
        )
    }

    private fun onCaptureReady(raw: String, sourceBitmap: Bitmap) {
        if (sourceBitmap.isRecycled) {
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.location_trainer_recognition_error))
            return
        }
        if (profileId.isBlank()) {
            profileId = java.util.UUID.randomUUID().toString()
        }
        val visualHash = runCatching { VisualFingerprint.compute(sourceBitmap) }.getOrDefault("")
        val existingCount = editingProfile?.referenceImagePaths?.size ?: 0
        val thumbnailPath = saveThumbnail(profileId, existingCount + pendingCaptures.size, sourceBitmap)
        pendingCaptures.add(
            LocationCaptureDraft(
                ocrText = raw,
                visualHash = visualHash,
                thumbnailPath = thumbnailPath
            )
        )

        sounds.play(SoundType.ACTION_OK)
        val count = pendingCaptures.size
        if (count >= maxCapturesThisSession) {
            setStatusText(getString(R.string.location_trainer_status_saving))
            if (isEditMode) saveEditProfile() else promptForProfileName()
            return
        }

        val message = if (isEditMode) {
            getString(R.string.location_trainer_edit_capture_added, count, maxCapturesThisSession)
        } else {
            getString(R.string.location_trainer_capture_added, count, NEW_CAPTURES_PER_SESSION)
        }
        setStatusText(message)
        tts.speak(message)
    }

    private fun finalizeCapturesAndName() {
        if (capturing.get()) return
        if (pendingCaptures.isEmpty()) {
            tts.speak(getString(R.string.location_trainer_no_capture_yet))
            return
        }
        if (isEditMode) {
            saveEditProfile()
        } else {
            setStatusText(getString(R.string.location_trainer_status_naming))
            promptForProfileName()
        }
    }

    private fun promptForProfileName() {
        if (!voiceInput.isAvailable()) {
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.location_trainer_voice_unavailable))
            setStatusText(getString(R.string.location_trainer_status_ready))
            return
        }

        voiceInput.listen(
            prompt = getString(R.string.location_trainer_name_prompt),
            speakFirst = { prompt, onDone -> tts.speakThen(prompt) { onDone() } },
            onResult = { spoken -> saveProfile(spoken) },
            onError = {
                sounds.play(SoundType.ACTION_ERROR)
                tts.speak(getString(R.string.location_trainer_name_error))
                setStatusText(getString(R.string.location_trainer_status_ready))
            }
        )
    }

    private fun saveEditProfile() {
        val profile = editingProfile ?: return
        val captures = pendingCaptures.toList()
        if (captures.isEmpty()) return

        val saved = LocationProfileStore.appendCaptures(this, profile.id, captures)
        if (saved == null) {
            captures.mapNotNull { it.thumbnailPath }.forEach { deleteThumbnailFile(it) }
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.location_trainer_save_error))
            setStatusText(getString(R.string.location_trainer_status_ready))
            return
        }

        pendingCaptures.clear()
        editingProfile = saved
        sounds.play(SoundType.ACTION_OK)
        val message = getString(
            R.string.location_trainer_edit_saved,
            saved.name,
            saved.referenceImagePaths.size
        )
        setStatusText(message)
        tts.speak(message)
    }

    private fun saveProfile(name: String) {
        val captures = pendingCaptures.toList()
        if (captures.isEmpty()) {
            setStatusText(getString(R.string.location_trainer_status_ready))
            return
        }

        val draft = LocationProfileStore.buildProfileFromCaptures(name, captures)
        if (draft == null) {
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.location_trainer_save_error))
            setStatusText(getString(R.string.location_trainer_status_ready))
            return
        }

        val profile = draft.copy(id = profileId.ifBlank { draft.id })
        val saved = LocationProfileStore.add(this, profile)
        if (saved == null) {
            captures.mapNotNull { it.thumbnailPath }.forEach { deleteThumbnailFile(it) }
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.location_trainer_save_error))
            setStatusText(getString(R.string.location_trainer_status_ready))
            return
        }

        pendingCaptures.clear()
        profileId = ""
        sounds.play(SoundType.ACTION_OK)
        val message = getString(R.string.location_trainer_saved, saved.name)
        setStatusText(message)
        tts.speak(message)
    }

    private fun saveThumbnail(profileId: String, index: Int, bitmap: Bitmap): String? {
        return try {
            val dir = File(filesDir, THUMBNAIL_DIR)
            if (!dir.exists()) dir.mkdirs()
            val file = File(dir, "${profileId}_${System.currentTimeMillis()}_$index.jpg")
            FileOutputStream(file).use { out ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, 80, out)
            }
            file.absolutePath
        } catch (_: Exception) {
            null
        }
    }

    private fun deleteThumbnailFile(path: String?) {
        if (path.isNullOrBlank()) return
        try {
            File(path).delete()
        } catch (_: Exception) {
        }
    }

    private fun finishTrainer() {
        voiceInput.cancel()
        pendingCaptures.mapNotNull { it.thumbnailPath }.forEach { deleteThumbnailFile(it) }
        pendingCaptures.clear()
        profileId = ""
        sounds.play(SoundType.SWIPE_LEFT)
        val exitMsg = if (isEditMode) {
            getString(R.string.location_trainer_edit_exit)
        } else {
            getString(R.string.location_trainer_exit)
        }
        tts.speak(exitMsg)
        finish()
    }

    private fun setStatusText(text: String) {
        postWhenAlive { tvStatus.text = text }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.KEYCODE_VOLUME_DOWN -> {
                if (event?.repeatCount == 0) {
                    triggerCaptureAndOcr()
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
                initializeTrainer()
            } else {
                sounds.play(SoundType.ACTION_ERROR)
                setStatusText(getString(R.string.location_trainer_permission_denied))
                tts.runWhenReady { tts.speak(getString(R.string.location_trainer_permission_denied)) }
                finish()
            }
        }
    }

    private fun handleMemoryFailure() {
        if (!memoryFailureHandled.compareAndSet(false, true)) return
        imageAnalysis?.clearAnalyzer()
        sounds.play(SoundType.ACTION_ERROR)
        setStatusText(getString(R.string.camera_memory_error))
        tts.speak(getString(R.string.camera_memory_error))
    }

    override fun onDestroy() {
        voiceInput.destroy()
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
                System.gc()
                postWhenAlive { handleMemoryFailure() }
            } catch (_: Exception) {
            } finally {
                imageProxy.close()
            }
        }
    }

    companion object {
        private const val REQ_CAMERA = 7110
        private const val BUFFER_FRAME_INTERVAL_MS = 450L
        private const val THUMBNAIL_DIR = "location_thumbnails"
        private const val NEW_CAPTURES_PER_SESSION = 10
        const val EXTRA_EDIT_PROFILE_ID = "edit_profile_id"

        fun intent(context: Context): Intent =
            Intent(context, LocationTrainerActivity::class.java)

        fun intentForEdit(context: Context, profileId: String): Intent =
            Intent(context, LocationTrainerActivity::class.java)
                .putExtra(EXTRA_EDIT_PROFILE_ID, profileId)
    }
}