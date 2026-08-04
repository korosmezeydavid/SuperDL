package com.superdl.launcher.qr

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.view.MotionEvent
import android.view.View
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
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.superdl.launcher.R
import com.superdl.launcher.camera.CameraStabilityHelper
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class QrScanActivity : AppCompatActivity() {

    private lateinit var previewView: PreviewView
    private lateinit var tvStatus: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var cameraExecutor: ExecutorService
    private var imageAnalysis: ImageAnalysis? = null

    private var vibrator: Vibrator? = null
    private val isHandlingResult = AtomicBoolean(false)
    private var rawValue: String = ""
    private var spokenValue: String = ""
    private var actions: List<QrAction> = emptyList()
    private var actionIndex = 0
    private var actionMode = false

    private val barcodeScanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder()
            .setBarcodeFormats(
                Barcode.FORMAT_QR_CODE,
                Barcode.FORMAT_CODE_128,
                Barcode.FORMAT_CODE_39,
                Barcode.FORMAT_EAN_13,
                Barcode.FORMAT_EAN_8,
                Barcode.FORMAT_UPC_A,
                Barcode.FORMAT_DATA_MATRIX,
                Barcode.FORMAT_PDF417
            )
            .build()
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_qr_scan)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            )

        previewView = findViewById(R.id.previewView)
        CameraStabilityHelper.configurePreviewView(previewView)
        tvStatus = findViewById(R.id.tvQrStatus)
        cameraExecutor = Executors.newSingleThreadExecutor()

        vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(VIBRATOR_SERVICE) as Vibrator
        }

        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { if (actionMode) navigateAction(-1) else hintScan() },
            onSwipeDown = { if (actionMode) navigateAction(+1) else hintScan() },
            onSwipeRight = { if (actionMode) activateAction() else hintScan() },
            onSwipeLeft = { if (actionMode) finishWithAction(null) else finishScan() }
        )

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (actionMode) finishWithAction(null) else finishScan()
            }
        })

        if (hasCameraPermission()) {
            startCamera()
        } else {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.CAMERA),
                CAMERA_PERMISSION_REQUEST
            )
        }

        tts.speak(
            "Beépített Q R és vonalkód olvasó. Tartsd a kamerát a kód elé. " +
                "Sikeres olvasás után választhatsz műveletet. Balra húzás: vissza."
        )
    }

    private fun hintScan() {
        sounds.play(SoundType.SWIPE_UP)
        tts.speak("Tartsd a kamerát a kód elé.")
    }

    override fun onTouchEvent(event: MotionEvent): Boolean =
        gestureListener.detector.onTouchEvent(event) || super.onTouchEvent(event)

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != CAMERA_PERMISSION_REQUEST) return
        if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            tts.speakThen("Kamera engedély szükséges a Q R olvasáshoz.") { finish() }
        }
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            val preview = CameraStabilityHelper.buildLightPreview(previewView.surfaceProvider)
            val analysis = CameraStabilityHelper.buildLightImageAnalysis()
                .build()
                .also {
                    it.setAnalyzer(cameraExecutor, QrAnalyzer { value ->
                        onCodeDetected(value)
                    })
                }
            imageAnalysis = analysis

            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    this,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    analysis
                )
            } catch (_: Exception) {
                tts.speakThen("A kamera nem indítható.") { finish() }
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun onCodeDetected(value: String) {
        if (!isHandlingResult.compareAndSet(false, true)) return
        runOnUiThread {
            if (isFinishing || isDestroyed) return@runOnUiThread
            vibrate(120)
            sounds.play(SoundType.ACTION_OK)
            rawValue = value
            spokenValue = QrResultFormatter.formatForSpeech(value)
            actions = QrActionParser.parse(value)
            actionIndex = 0
            actionMode = true
            previewView.visibility = View.GONE
            tvStatus.text = actions.first().label
            tts.speakThen("Kód beolvasva. $spokenValue. ${actions.size} művelet. Söpörj fel-le választás, jobbra végrehajtás, balra vissza.") {
                speakCurrentAction()
            }
        }
    }

    private fun navigateAction(delta: Int) {
        sounds.play(if (delta < 0) SoundType.SWIPE_UP else SoundType.SWIPE_DOWN)
        actionIndex = (actionIndex + delta + actions.size) % actions.size
        tvStatus.text = actions[actionIndex].label
        speakCurrentAction()
    }

    private fun speakCurrentAction() {
        tts.speak(actions[actionIndex].label)
    }

    private fun activateAction() {
        sounds.play(SoundType.SWIPE_RIGHT)
        when (actions[actionIndex].type) {
            QrActionType.READ_AGAIN -> tts.speak(spokenValue)
            QrActionType.CALL -> finishWithAction(QrActionType.CALL, actions[actionIndex].payload)
            QrActionType.SMS -> finishWithAction(QrActionType.SMS, actions[actionIndex].payload)
            QrActionType.EMAIL -> finishWithAction(QrActionType.EMAIL, actions[actionIndex].payload)
            QrActionType.NAVIGATE -> finishWithAction(QrActionType.NAVIGATE, actions[actionIndex].payload)
            QrActionType.FINISH -> finishWithAction(null)
        }
    }

    private fun finishWithAction(type: QrActionType?, payload: String = "") {
        sounds.play(SoundType.SWIPE_LEFT)
        tts.stop()
        if (type == null) {
            setResult(RESULT_CANCELED)
            finish()
            return
        }
        setResult(
            RESULT_OK,
            Intent().apply {
                putExtra(EXTRA_ACTION, type.name)
                putExtra(EXTRA_PAYLOAD, payload)
                putExtra(EXTRA_RAW, rawValue)
            }
        )
        finish()
    }

    private fun finishScan() {
        isHandlingResult.set(true)
        sounds.play(SoundType.SWIPE_LEFT)
        tts.stop()
        setResult(RESULT_CANCELED)
        finish()
    }

    private fun vibrate(ms: Long) {
        vibrator?.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
    }

    override fun onDestroy() {
        barcodeScanner.close()
        imageAnalysis?.clearAnalyzer()
        imageAnalysis = null
        CameraStabilityHelper.shutdownExecutor(cameraExecutor)
        tts.shutdown()
        if (::sounds.isInitialized) sounds.release()
        super.onDestroy()
    }

    @ExperimentalGetImage
    private inner class QrAnalyzer(
        private val onDetected: (String) -> Unit
    ) : ImageAnalysis.Analyzer {

        @ExperimentalGetImage
        override fun analyze(imageProxy: ImageProxy) {
            if (isHandlingResult.get()) {
                imageProxy.close()
                return
            }
            val mediaImage = imageProxy.image
            if (mediaImage == null) {
                imageProxy.close()
                return
            }
            val image = InputImage.fromMediaImage(
                mediaImage,
                imageProxy.imageInfo.rotationDegrees
            )
            barcodeScanner.process(image)
                .addOnSuccessListener { barcodes ->
                    val value = barcodes.firstOrNull { !it.rawValue.isNullOrBlank() }?.rawValue
                    if (value != null) onDetected(value)
                }
                .addOnCompleteListener { imageProxy.close() }
        }
    }

    companion object {
        const val EXTRA_ACTION = "qr_action"
        const val EXTRA_PAYLOAD = "qr_payload"
        const val EXTRA_RAW = "qr_raw"
        private const val CAMERA_PERMISSION_REQUEST = 2001
    }
}