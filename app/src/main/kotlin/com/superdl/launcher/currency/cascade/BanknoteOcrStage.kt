package com.superdl.launcher.currency.cascade

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.superdl.launcher.currency.BanknoteDenomination
import com.superdl.launcher.currency.trainer.BanknoteOcrAnalyzer
import java.io.Closeable
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import kotlin.coroutines.resume
import kotlin.math.min
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * Kaszkád 2. szint: lightweight OCR a címlet számjegyére (ML Kit).
 *
 * Nem elsődleges döntéshozó: a Stage1 szín-jelöltek közül választ / erősít.
 * Aszinkron, busy-gate-tel — low-end eszközön nem indít párhuzamos OCR-t.
 *
 * A teljes frame OCR-ezése helyett a középső ROI-t adjuk be (címlet szám
 * jellemzően középen / sarkokban nagy), kisebb bitmap = gyorsabb.
 */
class BanknoteOcrStage : Closeable {

    data class OcrHit(
        val denomination: BanknoteDenomination,
        val confidence: Float,
        val rawText: String,
        val capturedAtMs: Long,
        val constrainedByColor: Boolean
    )

    private val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    private val busy = AtomicBoolean(false)
    private val lastHit = AtomicReference<OcrHit?>(null)
    private var frameCounter = 0

    fun lastFreshHit(now: Long = System.currentTimeMillis()): OcrHit? {
        val hit = lastHit.get() ?: return null
        if (now - hit.capturedAtMs > BanknoteCascadeConfig.OCR_RESULT_MAX_AGE_MS) return null
        return hit
    }

    /**
     * Indítja az OCR-t, ha nem busy és eljött a sor.
     * A hívó nem vár — a következő frame-eken a [lastFreshHit] fuzionál.
     */
    fun maybeStart(
        bitmap: Bitmap,
        colorCandidates: List<BanknoteDenomination>,
        force: Boolean = false
    ) {
        frameCounter++
        if (!force && frameCounter % BanknoteCascadeConfig.OCR_EVERY_N_FRAMES != 0) return
        if (bitmap.isRecycled) return
        if (!busy.compareAndSet(false, true)) return

        val roi = centerRoi(bitmap) ?: bitmap
        val image = try {
            InputImage.fromBitmap(roi, 0)
        } catch (_: Exception) {
            busy.set(false)
            if (roi !== bitmap && !roi.isRecycled) roi.recycle()
            return
        }

        val candidateSet = colorCandidates.toSet()
        recognizer.process(image)
            .addOnSuccessListener { visionText ->
                try {
                    val text = visionText.text.orEmpty()
                    val extracted = BanknoteOcrAnalyzer.extractDenomination(text)
                    val denom = extracted?.let { BanknoteDenomination.fromValue(it) }
                    if (denom != null) {
                        val constrained = candidateSet.isNotEmpty()
                        val inCandidates = !constrained || denom in candidateSet
                        // Ha van erős szín-szűrés és az OCR kívül esik: elvetjük.
                        // MIÉRT: OCR tévesen olvashat évszámot/részletet; a szín a gate.
                        if (inCandidates) {
                            val conf = if (constrained && denom in candidateSet) {
                                BanknoteCascadeConfig.OCR_WITH_COLOR_AGREE_CONFIDENCE
                            } else {
                                BanknoteCascadeConfig.OCR_MIN_CONFIDENCE
                            }
                            lastHit.set(
                                OcrHit(
                                    denomination = denom,
                                    confidence = conf,
                                    rawText = text.take(80),
                                    capturedAtMs = System.currentTimeMillis(),
                                    constrainedByColor = constrained
                                )
                            )
                            android.util.Log.i(
                                "SDL_CASH",
                                "S2 OCR hit=${denom.valueHuf} conf=${"%.2f".format(conf)} " +
                                    "text='${text.take(40).replace("\n", " ")}'"
                            )
                        } else {
                            android.util.Log.i(
                                "SDL_CASH",
                                "S2 OCR elvetve (szín-szűrőn kívül): ${denom.valueHuf} " +
                                    "cands=${candidateSet.map { it.valueHuf }}"
                            )
                        }
                    }
                } finally {
                    busy.set(false)
                    if (roi !== bitmap && !roi.isRecycled) roi.recycle()
                }
            }
            .addOnFailureListener { e ->
                android.util.Log.w("SDL_CASH", "S2 OCR hiba: ${e.message}")
                busy.set(false)
                if (roi !== bitmap && !roi.isRecycled) roi.recycle()
            }
    }

    /**
     * Szinkron várakozásos OCR (manuális ellenőrzéshez). Timeout nélkül:
     * a ML Kit callback-ig suspend.
     */
    suspend fun recognizeBlocking(
        bitmap: Bitmap,
        colorCandidates: List<BanknoteDenomination>
    ): OcrHit? = suspendCancellableCoroutine { cont ->
        if (bitmap.isRecycled) {
            cont.resume(null)
            return@suspendCancellableCoroutine
        }
        if (!busy.compareAndSet(false, true)) {
            cont.resume(lastFreshHit())
            return@suspendCancellableCoroutine
        }

        val roi = centerRoi(bitmap) ?: bitmap
        val image = try {
            InputImage.fromBitmap(roi, 0)
        } catch (_: Exception) {
            busy.set(false)
            if (roi !== bitmap && !roi.isRecycled) roi.recycle()
            cont.resume(null)
            return@suspendCancellableCoroutine
        }

        val candidateSet = colorCandidates.toSet()
        recognizer.process(image)
            .addOnSuccessListener { visionText ->
                val text = visionText.text.orEmpty()
                val extracted = BanknoteOcrAnalyzer.extractDenomination(text)
                val denom = extracted?.let { BanknoteDenomination.fromValue(it) }
                val hit = if (denom != null) {
                    val constrained = candidateSet.isNotEmpty()
                    val inCandidates = !constrained || denom in candidateSet
                    if (inCandidates) {
                        OcrHit(
                            denomination = denom,
                            confidence = if (constrained) {
                                BanknoteCascadeConfig.OCR_WITH_COLOR_AGREE_CONFIDENCE
                            } else {
                                BanknoteCascadeConfig.OCR_MIN_CONFIDENCE
                            },
                            rawText = text.take(80),
                            capturedAtMs = System.currentTimeMillis(),
                            constrainedByColor = constrained
                        ).also { lastHit.set(it) }
                    } else null
                } else null
                busy.set(false)
                if (roi !== bitmap && !roi.isRecycled) roi.recycle()
                if (cont.isActive) cont.resume(hit)
            }
            .addOnFailureListener {
                busy.set(false)
                if (roi !== bitmap && !roi.isRecycled) roi.recycle()
                if (cont.isActive) cont.resume(null)
            }
    }

    private fun centerRoi(bitmap: Bitmap): Bitmap? {
        return try {
            val w = bitmap.width
            val h = bitmap.height
            if (w < 32 || h < 32) return null
            // Címlet szám gyakran a jobb oldalon / sarkokban is — enyhe középre fókusz.
            val left = (w * 0.12f).toInt()
            val top = (h * 0.15f).toInt()
            val rw = (w * 0.76f).toInt().coerceAtLeast(16)
            val rh = (h * 0.70f).toInt().coerceAtLeast(16)
            val safeW = min(rw, w - left)
            val safeH = min(rh, h - top)
            if (safeW < 16 || safeH < 16) null
            else Bitmap.createBitmap(bitmap, left, top, safeW, safeH)
        } catch (_: Exception) {
            null
        }
    }

    fun reset() {
        lastHit.set(null)
        frameCounter = 0
    }

    override fun close() {
        reset()
        busy.set(false)
        try {
            recognizer.close()
        } catch (_: Exception) {
        }
    }
}
