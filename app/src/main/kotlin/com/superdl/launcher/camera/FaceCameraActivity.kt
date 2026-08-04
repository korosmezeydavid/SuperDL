package com.superdl.launcher.camera

import android.Manifest
import android.content.ContentValues
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.util.Size
import android.view.KeyEvent
import android.view.View
import android.widget.Button
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.MediaStoreOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetector
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.superdl.launcher.R
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager
import com.superdl.launcher.util.postWhenAlive
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

@ExperimentalGetImage
class FaceCameraActivity : AppCompatActivity() {

    private enum class CameraBindMode {
        DETECT,
        PHOTO,
        VIDEO
    }

    private lateinit var previewView: PreviewView
    private lateinit var tvStatus: TextView
    private lateinit var sounds: SoundFeedback
    private lateinit var tts: TtsManager
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private val mainHandler = Handler(Looper.getMainLooper())

    private val faceDebouncer = FaceAnnounceDebouncer(FACE_DEBOUNCE_MS)
    private val analyzing = AtomicBoolean(false)
    private val isRecording = AtomicBoolean(false)
    private val faceProcessing = AtomicBoolean(false)
    private val rebinding = AtomicBoolean(false)
    private val memoryFailureHandled = AtomicBoolean(false)
    private val lastFrameProcessedAt = AtomicLong(0L)

    private var qualityProfile = CameraQualityProfile.MEDIUM
    private var selfieMode = false
    private var videoSupported = true
    private var bindMode = CameraBindMode.DETECT
    private var cameraProvider: ProcessCameraProvider? = null
    private var imageAnalysis: ImageAnalysis? = null
    private var imageCapture: ImageCapture? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var activeRecording: Recording? = null
    private var faceDetector: FaceDetector? = null
    private var lastBackPressAt = 0L
    private var pendingPhotoAfterBind = false
    private var pendingRebindMode: CameraBindMode? = null
    private var analysisStartRunnable: Runnable? = null
    private var photoDelayRunnable: Runnable? = null
    private var videoDelayRunnable: Runnable? = null
    private var fatalFinishRunnable: Runnable? = null
    private var lastSavedPhotoUri: Uri? = null
    private var lastSavedPhotoName: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_face_camera)
        selfieMode = intent.getBooleanExtra(EXTRA_SELFIE_MODE, false)
        qualityProfile = CameraQualityStore.load(this)
        title = getString(R.string.face_camera_title)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        bindViews()
        sounds = SoundFeedback(this)
        tts = TtsManager(this)
        cameraExecutor = Executors.newSingleThreadExecutor()
        faceDetector = FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
                .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
                .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE)
                .setMinFaceSize(0.15f)
                .build()
        )

        setupGestures()
        setupBackHandler()

        if (hasCameraPermission()) {
            requestAudioIfNeededThenStart()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
        }
    }

    private fun bindViews() {
        previewView = findViewById(R.id.faceCameraPreview)
        previewView.implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        previewView.scaleType = PreviewView.ScaleType.FIT_CENTER
        tvStatus = findViewById(R.id.tvFaceCameraStatus)
        findViewById<Button>(R.id.btnFaceCameraExit).setOnClickListener { finishCamera() }
    }

    private fun setupGestures() {
        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                if (isRecording.get()) {
                    tts.speak(getString(R.string.face_camera_switch_blocked_recording))
                } else {
                    switchCameraFacing()
                }
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                if (isRecording.get()) {
                    stopVideoRecording()
                } else if (lastSavedPhotoUri != null) {
                    shareLastPhoto()
                } else {
                    announceCurrentCamera()
                }
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                takePhoto()
            },
            onSwipeLeft = { finishCamera() }
        )

        findViewById<View>(R.id.faceCameraRoot).setOnTouchListener { view, event ->
            gestureListener.detector.onTouchEvent(event)
            if (event.action == android.view.MotionEvent.ACTION_UP) {
                view.performClick()
            }
            true
        }
    }

    private fun setupBackHandler() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val now = System.currentTimeMillis()
                if (now - lastBackPressAt < 2000L) {
                    finishCamera()
                } else {
                    lastBackPressAt = now
                    tts.speak("Kilépéshez nyomd meg újra a vissza gombot, vagy balra söpörj.")
                }
            }
        })
    }

    private fun requestAudioIfNeededThenStart() {
        if (hasAudioPermission()) {
            initializeCamera()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), REQ_AUDIO)
        }
    }

    private fun initializeCamera() {
        setStatusText(getString(R.string.face_camera_status_ready))
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            try {
                cameraProvider = providerFuture.get()
                rebindCamera(CameraBindMode.DETECT)
                tts.runWhenReady { tts.speak(buildIntroSpeech()) }
            } catch (t: Throwable) {
                handleCameraFatal(t)
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun buildIntroSpeech(): String =
        getString(R.string.face_camera_intro)

    private fun announceCurrentCamera() {
        val label = if (selfieMode) {
            getString(R.string.face_camera_mode_selfie)
        } else {
            getString(R.string.face_camera_mode_back)
        }
        tts.speak(label)
    }

    private fun shareLastPhoto() {
        val uri = lastSavedPhotoUri
        val name = lastSavedPhotoName
        if (uri == null || name.isNullOrBlank()) {
            tts.speak(getString(R.string.face_camera_share_none))
            return
        }
        val ok = CameraShareHelper.sharePhoto(this, uri, name)
        if (ok) {
            tts.speak(getString(R.string.face_camera_share_opened, name))
        } else {
            sounds.play(SoundType.ACTION_ERROR)
            tts.speak(getString(R.string.face_camera_share_error))
        }
    }

    private fun switchCameraFacing() {
        if (bindMode != CameraBindMode.DETECT) {
            tts.speak(getString(R.string.face_camera_switch_blocked_mode))
            return
        }
        cancelDelayedAnalysisStart()
        analyzing.set(false)
        faceDebouncer.reset()
        selfieMode = !selfieMode
        announceCurrentCamera()
        rebindCamera(CameraBindMode.DETECT)
    }

    private fun cameraSelector(): CameraSelector =
        if (selfieMode) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA

    private fun buildMinimalPreview(): Preview =
        Preview.Builder()
            .setResolutionSelector(FaceCameraAnalysisConfig.previewResolutionSelector())
            .build()
            .also { it.setSurfaceProvider(previewView.surfaceProvider) }

    private fun buildImageCapture(): ImageCapture =
        ImageCapture.Builder()
            .setResolutionSelector(
                ResolutionSelector.Builder()
                    .setResolutionStrategy(
                        ResolutionStrategy(
                            Size(qualityProfile.photoWidth, qualityProfile.photoHeight),
                            ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER
                        )
                    )
                    .build()
            )
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .build()

    private fun buildVideoCapture(): VideoCapture<Recorder> {
        val videoQuality = when (qualityProfile) {
            CameraQualityProfile.LOW -> Quality.HD
            CameraQualityProfile.MEDIUM -> Quality.FHD
            CameraQualityProfile.HIGH -> Quality.FHD
        }
        val qualitySelector = QualitySelector.from(
            videoQuality,
            FallbackStrategy.lowerQualityOrHigherThan(Quality.SD)
        )
        val recorder = Recorder.Builder()
            .setQualitySelector(qualitySelector)
            .build()
        return VideoCapture.withOutput(recorder)
    }

    private fun rebindCamera(mode: CameraBindMode) {
        if (!rebinding.compareAndSet(false, true)) {
            pendingRebindMode = mode
            return
        }
        postWhenAlive { performRebind(mode) }
    }

    private fun performRebind(mode: CameraBindMode) {
        val provider = cameraProvider
        if (provider == null) {
            finishRebind()
            return
        }

        try {
            cancelDelayedAnalysisStart()
            analyzing.set(false)
            faceProcessing.set(false)
            imageAnalysis?.clearAnalyzer()
            provider.unbindAll()
            imageAnalysis = null
            imageCapture = null
            videoCapture = null

            when (mode) {
                CameraBindMode.DETECT -> {
                    val preview = buildMinimalPreview()
                    imageAnalysis = FaceCameraAnalysisConfig.imageAnalysisBuilder()
                        .build()
                        .also { analysis ->
                            analysis.setAnalyzer(cameraExecutor, FaceFrameAnalyzer())
                        }
                    provider.bindToLifecycle(this, cameraSelector(), preview, imageAnalysis)
                    bindMode = CameraBindMode.DETECT
                    scheduleDelayedAnalysisStart()
                }
                CameraBindMode.PHOTO -> {
                    val preview = buildMinimalPreview()
                    imageCapture = buildImageCapture()
                    provider.bindToLifecycle(this, cameraSelector(), preview, imageCapture)
                    bindMode = CameraBindMode.PHOTO
                }
                CameraBindMode.VIDEO -> {
                    if (selfieMode) {
                        throw IllegalStateException("Selfie video not supported")
                    }
                    val preview = buildMinimalPreview()
                    videoCapture = buildVideoCapture()
                    provider.bindToLifecycle(this, cameraSelector(), preview, videoCapture)
                    bindMode = CameraBindMode.VIDEO
                }
            }
        } catch (t: Throwable) {
            when (mode) {
                CameraBindMode.VIDEO -> {
                    videoSupported = false
                    tts.speak(getString(R.string.face_camera_video_unavailable))
                    if (bindMode != CameraBindMode.DETECT) {
                        pendingRebindMode = CameraBindMode.DETECT
                    }
                }
                CameraBindMode.PHOTO -> {
                    tts.speak(getString(R.string.face_camera_photo_error))
                    pendingPhotoAfterBind = false
                    pendingRebindMode = CameraBindMode.DETECT
                }
                CameraBindMode.DETECT -> handleCameraFatal(t)
            }
        } finally {
            finishRebind()
        }
    }

    private fun finishRebind() {
        rebinding.set(false)
        val pending = pendingRebindMode
        pendingRebindMode = null
        if (pending != null) {
            rebindCamera(pending)
        }
    }

    private fun scheduleDelayedAnalysisStart() {
        cancelDelayedAnalysisStart()
        val runnable = Runnable {
            analysisStartRunnable = null
            if (!isFinishing && bindMode == CameraBindMode.DETECT) {
                analyzing.set(true)
            }
        }
        analysisStartRunnable = runnable
        mainHandler.postDelayed(runnable, ANALYSIS_START_DELAY_MS)
    }

    private fun cancelDelayedAnalysisStart() {
        analysisStartRunnable?.let { mainHandler.removeCallbacks(it) }
        analysisStartRunnable = null
        analyzing.set(false)
    }

    private fun cancelPendingHandlers() {
        cancelDelayedAnalysisStart()
        photoDelayRunnable?.let { mainHandler.removeCallbacks(it) }
        photoDelayRunnable = null
        videoDelayRunnable?.let { mainHandler.removeCallbacks(it) }
        videoDelayRunnable = null
        fatalFinishRunnable?.let { mainHandler.removeCallbacks(it) }
        fatalFinishRunnable = null
    }

    private fun handleCameraFatal(t: Throwable) {
        sounds.play(SoundType.ACTION_ERROR)
        setStatusText(getString(R.string.face_camera_camera_error))
        tts.runWhenReady { tts.speak(getString(R.string.face_camera_camera_error)) }
        fatalFinishRunnable?.let { mainHandler.removeCallbacks(it) }
        val runnable = Runnable { if (!isFinishing && !isDestroyed) finish() }
        fatalFinishRunnable = runnable
        mainHandler.postDelayed(runnable, 1200L)
    }

    private fun handleFrameMemoryFailure() {
        if (!memoryFailureHandled.compareAndSet(false, true)) return
        cancelDelayedAnalysisStart()
        imageAnalysis?.clearAnalyzer()
        sounds.play(SoundType.ACTION_ERROR)
        setStatusText(getString(R.string.face_camera_memory_error))
        tts.speak(getString(R.string.face_camera_memory_error))
    }

    private fun takePhoto() {
        if (bindMode != CameraBindMode.PHOTO) {
            pendingPhotoAfterBind = true
            rebindCamera(CameraBindMode.PHOTO)
            photoDelayRunnable?.let { mainHandler.removeCallbacks(it) }
            val runnable = Runnable {
                photoDelayRunnable = null
                if (isFinishing || isDestroyed) return@Runnable
                if (pendingPhotoAfterBind) {
                    pendingPhotoAfterBind = false
                    takePhotoInternal()
                }
            }
            photoDelayRunnable = runnable
            mainHandler.postDelayed(runnable, 500L)
            return
        }
        takePhotoInternal()
    }

    /** Fotó-készítés hangja: a saját exponáló "katt" (snd_camera_shutter). */
    private fun playCameraShutter() {
        try {
            val mp = android.media.MediaPlayer.create(applicationContext, R.raw.snd_camera_shutter)
            if (mp != null) {
                mp.setOnCompletionListener { it.release() }
                mp.start()
            } else {
                sounds.play(SoundType.SWIPE_RIGHT)
            }
        } catch (_: Exception) {
            sounds.play(SoundType.SWIPE_RIGHT)
        }
    }

    private fun takePhotoInternal() {
        val capture = imageCapture ?: run {
            tts.speak(getString(R.string.face_camera_photo_error))
            rebindCamera(CameraBindMode.DETECT)
            return
        }
        val fileName = "SuperDL_${timestamp()}.jpg"
        val contentValues = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
            put(MediaStore.MediaColumns.MIME_TYPE, "image/jpeg")
            put(MediaStore.MediaColumns.RELATIVE_PATH, MEDIA_RELATIVE_PATH)
        }
        val outputOptions = ImageCapture.OutputFileOptions.Builder(
            contentResolver,
            MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
            contentValues
        ).build()

        capture.takePicture(
            outputOptions,
            ContextCompat.getMainExecutor(this),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                    if (isFinishing || isDestroyed) return
                    lastSavedPhotoUri = outputFileResults.savedUri
                    lastSavedPhotoName = fileName
                    playCameraShutter()
                    val message = getString(R.string.face_camera_photo_saved, fileName)
                    setStatusText(message)
                    tts.speak(message)
                    if (bindMode == CameraBindMode.PHOTO && !isRecording.get()) {
                        rebindCamera(CameraBindMode.DETECT)
                    }
                }

                override fun onError(exception: ImageCaptureException) {
                    if (isFinishing || isDestroyed) return
                    sounds.play(SoundType.ACTION_ERROR)
                    tts.speak(getString(R.string.face_camera_photo_error))
                    rebindCamera(CameraBindMode.DETECT)
                }
            }
        )
    }

    private fun startVideoRecording() {
        if (!videoSupported || selfieMode) {
            tts.speak(getString(R.string.face_camera_video_unavailable))
            return
        }
        if (isRecording.get()) {
            tts.speak(getString(R.string.face_camera_video_already_recording))
            return
        }
        if (bindMode != CameraBindMode.VIDEO) {
            rebindCamera(CameraBindMode.VIDEO)
            videoDelayRunnable?.let { mainHandler.removeCallbacks(it) }
            val runnable = Runnable {
                videoDelayRunnable = null
                if (!isFinishing && !isDestroyed) startVideoRecordingInternal()
            }
            videoDelayRunnable = runnable
            mainHandler.postDelayed(runnable, 500L)
            return
        }
        startVideoRecordingInternal()
    }

    private fun startVideoRecordingInternal() {
        val capture = videoCapture ?: run {
            tts.speak(getString(R.string.face_camera_video_error))
            rebindCamera(CameraBindMode.DETECT)
            return
        }
        val fileName = "SuperDL_${timestamp()}.mp4"
        val contentValues = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
            put(MediaStore.MediaColumns.MIME_TYPE, "video/mp4")
            put(MediaStore.MediaColumns.RELATIVE_PATH, MEDIA_RELATIVE_PATH)
        }
        val mediaStoreOutput = MediaStoreOutputOptions.Builder(
            contentResolver,
            MediaStore.Video.Media.EXTERNAL_CONTENT_URI
        )
            .setContentValues(contentValues)
            .build()

        val pendingRecording = capture.output.prepareRecording(this, mediaStoreOutput)
        val recording = (
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED
            ) {
                try {
                    pendingRecording.withAudioEnabled()
                } catch (_: SecurityException) {
                    pendingRecording
                }
            } else {
                pendingRecording
            }
        ).start(ContextCompat.getMainExecutor(this)) { event ->
            if (isFinishing || isDestroyed) return@start
            when (event) {
                is VideoRecordEvent.Start -> {
                    isRecording.set(true)
                    setStatusText(getString(R.string.face_camera_status_recording))
                    tts.speak(getString(R.string.face_camera_video_started))
                }
                is VideoRecordEvent.Finalize -> {
                    isRecording.set(false)
                    activeRecording = null
                    if (event.hasError()) {
                        sounds.play(SoundType.ACTION_ERROR)
                        setStatusText(getString(R.string.face_camera_video_error))
                        tts.speak(getString(R.string.face_camera_video_error))
                    } else {
                        val message = getString(R.string.face_camera_video_saved, fileName)
                        setStatusText(message)
                        tts.speak(message)
                    }
                    rebindCamera(CameraBindMode.DETECT)
                }
            }
        }
        activeRecording = recording
    }

    private fun stopVideoRecording() {
        if (!isRecording.get()) {
            tts.speak(getString(R.string.face_camera_video_not_recording))
            return
        }
        activeRecording?.stop()
    }

    private fun onFacesDetected(faces: List<com.google.mlkit.vision.face.Face>, imageWidth: Int, imageHeight: Int) {
        val announcement = FacePositionSpeaker.describe(faces, imageWidth, imageHeight, selfieMode) ?: return
        val debounceKey = FacePositionSpeaker.debounceKey(faces, imageWidth, imageHeight, selfieMode)
        if (!faceDebouncer.shouldAnnounce(debounceKey)) return

        postWhenAlive {
            if (!analyzing.get() || bindMode != CameraBindMode.DETECT) return@postWhenAlive
            tvStatus.text = announcement
            tts.speak(announcement)
        }
    }

    private fun setStatusText(text: String) {
        postWhenAlive { tvStatus.text = text }
    }

    private fun finishCamera() {
        cancelDelayedAnalysisStart()
        analyzing.set(false)
        faceProcessing.set(false)
        pendingPhotoAfterBind = false
        if (isRecording.get()) {
            activeRecording?.stop()
        }
        sounds.play(SoundType.SWIPE_LEFT)
        tts.speakThen(getString(R.string.face_camera_exit)) { finish() }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP -> {
                if (event?.repeatCount == 0) startVideoRecording()
                return true
            }
            KeyEvent.KEYCODE_VOLUME_DOWN -> {
                if (event?.repeatCount == 0) stopVideoRecording()
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

    private fun hasAudioPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        when (requestCode) {
            REQ_CAMERA -> {
                if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    requestAudioIfNeededThenStart()
                } else {
                    sounds.play(SoundType.ACTION_ERROR)
                    setStatusText(getString(R.string.face_camera_permission_denied))
                    tts.runWhenReady { tts.speak(getString(R.string.face_camera_permission_denied)) }
                    finish()
                }
            }
            REQ_AUDIO -> initializeCamera()
        }
    }

    override fun onDestroy() {
        cancelPendingHandlers()
        mainHandler.removeCallbacksAndMessages(null)
        analyzing.set(false)
        pendingPhotoAfterBind = false
        pendingRebindMode = null
        try {
            activeRecording?.stop()
        } catch (_: Exception) {
        }
        activeRecording = null
        imageAnalysis?.clearAnalyzer()
        imageAnalysis = null
        imageCapture = null
        videoCapture = null
        try {
            cameraProvider?.unbindAll()
        } catch (_: Exception) {
        }
        cameraProvider = null
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        try {
            faceDetector?.close()
        } catch (_: Exception) {
        }
        faceDetector = null
        faceDebouncer.reset()
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    @ExperimentalGetImage
    private inner class FaceFrameAnalyzer : ImageAnalysis.Analyzer {
        override fun analyze(imageProxy: ImageProxy) {
            if (!analyzing.get() || bindMode != CameraBindMode.DETECT || rebinding.get()) {
                imageProxy.close()
                return
            }

            val now = System.currentTimeMillis()
            if (now - lastFrameProcessedAt.get() < FRAME_INTERVAL_MS) {
                imageProxy.close()
                return
            }
            if (!faceProcessing.compareAndSet(false, true)) {
                imageProxy.close()
                return
            }
            lastFrameProcessedAt.set(now)

            val detector = faceDetector
            val mediaImage = imageProxy.image
            if (detector == null || mediaImage == null) {
                faceProcessing.set(false)
                imageProxy.close()
                return
            }

            try {
                val inputImage = InputImage.fromMediaImage(
                    mediaImage,
                    imageProxy.imageInfo.rotationDegrees
                )
                detector.process(inputImage)
                    .addOnSuccessListener { faces ->
                        if (analyzing.get() && bindMode == CameraBindMode.DETECT) {
                            onFacesDetected(faces, inputImage.width, inputImage.height)
                        }
                    }
                    .addOnFailureListener { /* dropped frame */ }
                    .addOnCompleteListener {
                        faceProcessing.set(false)
                        imageProxy.close()
                    }
            } catch (oom: OutOfMemoryError) {
                faceProcessing.set(false)
                imageProxy.close()
                postWhenAlive { handleFrameMemoryFailure() }
            } catch (_: Exception) {
                faceProcessing.set(false)
                imageProxy.close()
            }
        }
    }

    private fun timestamp(): String =
        SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())

    companion object {
        const val EXTRA_SELFIE_MODE = "selfie_mode"
        private const val MEDIA_RELATIVE_PATH = "DCIM/SuperDL"
        private const val REQ_CAMERA = 7106
        private const val REQ_AUDIO = 7107
        private const val FRAME_INTERVAL_MS = 700L
        private const val FACE_DEBOUNCE_MS = 3000L
        private const val ANALYSIS_START_DELAY_MS = 1800L
    }
}