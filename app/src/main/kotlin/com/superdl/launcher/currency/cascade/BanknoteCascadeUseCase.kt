package com.superdl.launcher.currency.cascade

import android.graphics.Bitmap
import com.superdl.launcher.currency.BanknoteClassificationResult
import com.superdl.launcher.currency.BanknoteClassifierEngine
import com.superdl.launcher.currency.BanknoteColorVerifier
import com.superdl.launcher.currency.BanknoteDenomination
import com.superdl.launcher.currency.BanknotePipelineMode
import java.io.Closeable

/**
 * Prioritásos hibrid kaszkád — domain UseCase (Clean Architecture).
 *
 * A UI / ViewModel CSAK a végeredményt kapja; a döntési sorrend itt van:
 *   1. Szín + geometria (BanknoteColorGeometryStage)
 *   2. OCR (BanknoteOcrStage) — szín-szűkített jelöltek
 *   3. YOLO fallback — csak ha [BanknoteCascadeConfig.YOLO_FALLBACK_ENABLED]
 *      és az 1+2 alacsony bizalmú
 *
 * Repository-szerű függőségek: a Stage osztályok + opcionális YOLO engine.
 * Nincs DI keretrendszer (projekt-konvenció); a UseCase példányt a ViewModel tartja.
 */
class BanknoteCascadeUseCase(
    private val ocrStage: BanknoteOcrStage = BanknoteOcrStage(),
    private val yoloFallbackEnabled: Boolean = BanknoteCascadeConfig.YOLO_FALLBACK_ENABLED
) : Closeable {

    /**
     * Egy kamera-frame feldolgozása. Szinkron a Stage1-re; OCR háttérben frissül.
     * @param yoloEngine opcionális; csak ha a fallback engedélyezett ÉS betöltött.
     */
    fun recognizeFrame(
        bitmap: Bitmap,
        yoloEngine: BanknoteClassifierEngine? = null
    ): BanknoteClassificationResult? {
        if (bitmap.isRecycled) return null

        // ── 1. Szín + geometria ────────────────────────────────────────────
        val stage1 = BanknoteColorGeometryStage.analyze(bitmap)
        if (!stage1.passesColorGate || stage1.top == null) {
            // Nincs erős szín-egyezés → NEM engedünk tovább YOLO-ra sem
            // (hamis pozitív elkerülése). Manuális ellenőrzés külön útvonal.
            return null
        }

        val colorCandidates = stage1.candidates.map { it.denomination }
        val topColor = stage1.top
        val secondScore = stage1.second?.score ?: 0f

        // ── 2. OCR indítás (aszinkron) + friss cache ───────────────────────
        ocrStage.maybeStart(bitmap, colorCandidates)
        val ocrHit = ocrStage.lastFreshHit()

        // Fúzió: szín + OCR
        val fused = fuseColorAndOcr(topColor, secondScore, ocrHit, stage1)
        if (fused != null) {
            return fused
        }

        // ── 3. YOLO csak legvégső fallback ─────────────────────────────────
        if (!yoloFallbackEnabled) return null
        if (yoloEngine == null || !yoloEngine.isTwoStageEnabled) return null

        val colorTooWeak = topColor.score < BanknoteCascadeConfig.YOLO_ONLY_IF_COLOR_SCORE_BELOW
        val noOcr = ocrHit == null
        if (!colorTooWeak) return null
        if (BanknoteCascadeConfig.YOLO_ONLY_IF_NO_OCR && !noOcr) return null

        val yolo = try {
            yoloEngine.classify(bitmap)
        } catch (e: Exception) {
            android.util.Log.w("SDL_CASH", "S3 YOLO hiba: ${e.message}")
            null
        } ?: return null

        // YOLO csak akkor fogadható el, ha a szín legalább NEUTRAL/AGREE.
        val colorVerdict = BanknoteColorVerifier.verify(bitmap, yolo.denomination)
        if (colorVerdict == BanknoteColorVerifier.Verdict.DISAGREE) {
            android.util.Log.i(
                "SDL_CASH",
                "S3 YOLO elvetve szín-DISAGREE: yolo=${yolo.denomination.valueHuf}"
            )
            return null
        }

        // Ha a szín tippelt és YOLO más: inkább hallgatunk, mint tévesztünk.
        if (yolo.denomination != topColor.denomination && topColor.score >= 0.45f) {
            android.util.Log.i(
                "SDL_CASH",
                "S3 YOLO≠szín, absztinencia: yolo=${yolo.denomination.valueHuf} " +
                    "color=${topColor.denomination.valueHuf}"
            )
            return null
        }

        return yolo.copy(
            pipelineMode = BanknotePipelineMode.CASCADE_YOLO_FALLBACK,
            colorVerdict = colorVerdict,
            yoloDominant = true
        )
    }

    /**
     * Manuális ellenőrzés (hangerő / swipe): szinkron OCR-rel, szigorúbb fúzió.
     * YOLO csak ha fallback be van kapcsolva.
     */
    suspend fun recognizeManual(
        bitmap: Bitmap,
        yoloEngine: BanknoteClassifierEngine? = null
    ): BanknoteClassificationResult? {
        if (bitmap.isRecycled) return null

        val stage1 = BanknoteColorGeometryStage.analyze(bitmap)
        val colorCandidates = stage1.candidates.map { it.denomination }
        val ocrHit = ocrStage.recognizeBlocking(bitmap, colorCandidates)

        if (stage1.top != null && stage1.passesColorGate) {
            fuseColorAndOcr(
                topColor = stage1.top,
                secondScore = stage1.second?.score ?: 0f,
                ocrHit = ocrHit,
                stage1 = stage1,
                manual = true
            )?.let { return it }
        }

        // OCR egyedül manuálisnál: ha van erős szám, és van legalább gyenge szín-jelölt.
        if (ocrHit != null && stage1.top != null) {
            return BanknoteClassificationResult(
                denomination = ocrHit.denomination,
                confidence = ocrHit.confidence,
                secondBestConfidence = 0f,
                colorVerdict = BanknoteColorVerifier.verify(bitmap, ocrHit.denomination),
                pipelineMode = BanknotePipelineMode.CASCADE_OCR,
                yoloDominant = false
            )
        }

        if (yoloFallbackEnabled && yoloEngine != null) {
            return yoloEngine.classifyForManualCheck(bitmap)?.copy(
                pipelineMode = BanknotePipelineMode.CASCADE_YOLO_FALLBACK
            )
        }
        return null
    }

    private fun fuseColorAndOcr(
        topColor: BanknoteColorGeometryStage.Candidate,
        secondScore: Float,
        ocrHit: BanknoteOcrStage.OcrHit?,
        stage1: BanknoteColorGeometryStage.Result,
        manual: Boolean = false
    ): BanknoteClassificationResult? {
        val colorVerdict = if (stage1.strongMatch) {
            BanknoteColorVerifier.Verdict.AGREE
        } else {
            BanknoteColorVerifier.Verdict.NEUTRAL
        }

        // A) Szín + OCR egyezik → legmagasabb bizalom
        if (ocrHit != null && ocrHit.denomination == topColor.denomination) {
            val conf = maxOf(
                topColor.score,
                ocrHit.confidence,
                BanknoteCascadeConfig.OCR_WITH_COLOR_AGREE_CONFIDENCE
            )
            android.util.Log.i(
                "SDL_CASH",
                "FUSE color+OCR AGREE ${topColor.denomination.valueHuf} conf=${"%.2f".format(conf)}"
            )
            return BanknoteClassificationResult(
                denomination = topColor.denomination,
                confidence = conf.coerceIn(0f, 1f),
                secondBestConfidence = secondScore,
                colorVerdict = BanknoteColorVerifier.Verdict.AGREE,
                pipelineMode = BanknotePipelineMode.CASCADE_COLOR_OCR,
                yoloDominant = false
            )
        }

        // B) OCR más címlet, de a szín-jelöltek között van → OCR nyer
        //    (látható szám a legmegbízhatóbb, ha a szín nem tiltja)
        if (ocrHit != null &&
            stage1.candidates.any { it.denomination == ocrHit.denomination }
        ) {
            android.util.Log.i(
                "SDL_CASH",
                "FUSE OCR wins (in color cands) ${ocrHit.denomination.valueHuf} " +
                    "vs color ${topColor.denomination.valueHuf}"
            )
            return BanknoteClassificationResult(
                denomination = ocrHit.denomination,
                confidence = ocrHit.confidence.coerceIn(0f, 1f),
                secondBestConfidence = topColor.score * 0.5f,
                colorVerdict = BanknoteColorVerifier.Verdict.NEUTRAL,
                pipelineMode = BanknotePipelineMode.CASCADE_OCR,
                yoloDominant = false
            )
        }

        // C) Csak erős szín, OCR üres / más (kívül a jelölteken) → szín dönt,
        //    de csak strongMatch-nél (weak inkább vár OCR-re, kivéve manuális).
        val acceptColorOnly = stage1.strongMatch || (manual && stage1.weakMatch)
        if (acceptColorOnly && ocrHit == null) {
            return BanknoteClassificationResult(
                denomination = topColor.denomination,
                confidence = topColor.score.coerceIn(0f, 1f),
                secondBestConfidence = secondScore,
                colorVerdict = colorVerdict,
                pipelineMode = BanknotePipelineMode.CASCADE_COLOR,
                yoloDominant = false
            )
        }

        // D) Weak color, OCR még nincs → várunk (null), a temporal filter sem szólal.
        // E) OCR teljesen más, nem a jelöltek között → absztinencia (hallgatunk).
        if (ocrHit != null && ocrHit.denomination != topColor.denomination) {
            android.util.Log.i(
                "SDL_CASH",
                "FUSE absztinencia: OCR=${ocrHit.denomination.valueHuf} " +
                    "color=${topColor.denomination.valueHuf}"
            )
        }
        return null
    }

    fun resetSession() {
        ocrStage.reset()
    }

    override fun close() {
        ocrStage.close()
    }
}
