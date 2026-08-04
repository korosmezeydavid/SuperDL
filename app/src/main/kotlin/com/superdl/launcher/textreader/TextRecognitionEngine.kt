package com.superdl.launcher.textreader

import android.graphics.Bitmap
import android.os.Handler
import android.os.Looper
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.io.Closeable
import java.util.concurrent.atomic.AtomicBoolean

class TextRecognitionEngine : Closeable {

    private val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    private val busy = AtomicBoolean(false)
    private val mainHandler = Handler(Looper.getMainLooper())
    private var timeoutRunnable: Runnable? = null

    fun recognize(
        bitmap: Bitmap,
        onResult: (String) -> Unit,
        onError: () -> Unit
    ) {
        if (!busy.compareAndSet(false, true)) {
            onError()
            return
        }
        clearTimeout()
        val timeout = Runnable {
            if (busy.compareAndSet(true, false)) {
                onError()
            }
        }
        timeoutRunnable = timeout
        mainHandler.postDelayed(timeout, RECOGNITION_TIMEOUT_MS)

        val image = InputImage.fromBitmap(bitmap, 0)
        recognizer.process(image)
            .addOnSuccessListener { visionText ->
                clearTimeout()
                busy.set(false)
                val text = visionText.text.orEmpty()
                mainHandler.post { onResult(text) }
            }
            .addOnFailureListener {
                clearTimeout()
                busy.set(false)
                mainHandler.post { onError() }
            }
    }

    private fun clearTimeout() {
        timeoutRunnable?.let { mainHandler.removeCallbacks(it) }
        timeoutRunnable = null
    }

    override fun close() {
        clearTimeout()
        busy.set(false)
        recognizer.close()
    }

    companion object {
        private const val RECOGNITION_TIMEOUT_MS = 8_000L
    }
}