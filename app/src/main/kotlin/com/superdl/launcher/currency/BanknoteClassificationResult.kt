package com.superdl.launcher.currency

import android.graphics.RectF

enum class BanknotePipelineMode {
    TWO_STAGE,
    ROI_FALLBACK,
    FULL_FRAME_FALLBACK,
    /** Régi szín/hibrid útvonal (kompatibilitás). */
    HYBRID_COLOR,
    /** Kaszkád 1: erős szín + geometria. */
    CASCADE_COLOR,
    /** Kaszkád 2: OCR (szín-szűkített jelöltek). */
    CASCADE_OCR,
    /** Kaszkád 1+2 fúzió: szín és OCR egyetért. */
    CASCADE_COLOR_OCR,
    /** Kaszkád 3: opcionális YOLO fallback (alapból kikapcsolva). */
    CASCADE_YOLO_FALLBACK
}

data class BanknoteClassificationResult(
    val denomination: BanknoteDenomination,
    val confidence: Float,
    val secondBestConfidence: Float = 0f,
    val noneConfidence: Float = 0f,
    val colorVerdict: BanknoteColorVerifier.Verdict = BanknoteColorVerifier.Verdict.NEUTRAL,
    val detectionConfidence: Float = 0f,
    val pipelineMode: BanknotePipelineMode = BanknotePipelineMode.FULL_FRAME_FALLBACK,
    val detectionBox: RectF? = null,
    /**
     * Ha true, a YOLO magabiztos címlete felülírta a classifierét —
     * a megbízhatóság a detekcióra épül, nem a classifier marginra.
     */
    val yoloDominant: Boolean = false
) {
    val fusedConfidence: Float
        get() = when (pipelineMode) {
            BanknotePipelineMode.TWO_STAGE,
            BanknotePipelineMode.CASCADE_YOLO_FALLBACK ->
                if (yoloDominant) {
                    detectionConfidence.coerceAtLeast(confidence)
                } else {
                    (confidence * 0.72f) + (detectionConfidence.coerceAtLeast(0f) * 0.28f)
                }
            BanknotePipelineMode.HYBRID_COLOR,
            BanknotePipelineMode.CASCADE_COLOR,
            BanknotePipelineMode.CASCADE_OCR,
            BanknotePipelineMode.CASCADE_COLOR_OCR -> confidence
            else -> confidence
        }

    fun isReliable(
        threshold: Float = CONFIDENCE_THRESHOLD,
        margin: Float = MIN_TOP_MARGIN,
        strictColor: Boolean = true
    ): Boolean {
        val score = fusedConfidence
        if (score < threshold) return false

        // YOLO-domináns two-stage: a detektor döntött — ne büntessük a
        // classifier second-best marginjával (az a crop-on fut, és gyakran
        // bizonytalanabb, mint a jól tanított YOLO címlet-fej).
        if (pipelineMode == BanknotePipelineMode.TWO_STAGE && yoloDominant) {
            if (detectionConfidence < DETECTION_THRESHOLD) return false
            if (strictColor && colorVerdict == BanknoteColorVerifier.Verdict.DISAGREE) return false
            return true
        }

        if (pipelineMode == BanknotePipelineMode.TWO_STAGE &&
            detectionConfidence < DETECTION_THRESHOLD
        ) {
            return false
        }

        // Kaszkád / hybrid szín-útvonal: szigorúbb küszöb + margin.
        if (pipelineMode == BanknotePipelineMode.HYBRID_COLOR ||
            pipelineMode == BanknotePipelineMode.CASCADE_COLOR ||
            pipelineMode == BanknotePipelineMode.CASCADE_OCR ||
            pipelineMode == BanknotePipelineMode.CASCADE_COLOR_OCR
        ) {
            val thr = when (pipelineMode) {
                BanknotePipelineMode.CASCADE_COLOR_OCR -> CASCADE_AGREE_THRESHOLD
                BanknotePipelineMode.CASCADE_OCR -> CASCADE_OCR_THRESHOLD
                else -> HYBRID_CONFIDENCE_THRESHOLD
            }
            if (score < thr) return false
            if (pipelineMode == BanknotePipelineMode.CASCADE_COLOR ||
                pipelineMode == BanknotePipelineMode.HYBRID_COLOR
            ) {
                if (confidence - secondBestConfidence < HYBRID_TOP_MARGIN) return false
            }
            if (strictColor && colorVerdict == BanknoteColorVerifier.Verdict.DISAGREE) return false
            return true
        }

        if (confidence - secondBestConfidence < margin) return false
        if (noneConfidence >= confidence - NONE_COMPETE_MARGIN) return false
        if (strictColor && colorVerdict == BanknoteColorVerifier.Verdict.DISAGREE) return false
        return true
    }

    fun isReliableForManualCheck(): Boolean =
        isReliable(
            threshold = if (yoloDominant) MANUAL_DETECTION_THRESHOLD else MANUAL_CONFIDENCE_THRESHOLD,
            margin = MANUAL_TOP_MARGIN,
            strictColor = false
        )

    companion object {
        const val CONFIDENCE_THRESHOLD = 0.52f
        const val DETECTION_THRESHOLD = 0.55f
        const val MIN_TOP_MARGIN = 0.10f
        const val NONE_COMPETE_MARGIN = 0.06f
        const val MANUAL_CONFIDENCE_THRESHOLD = 0.45f
        const val MANUAL_DETECTION_THRESHOLD = 0.48f
        const val MANUAL_TOP_MARGIN = 0.08f
        const val HYBRID_CONFIDENCE_THRESHOLD = 0.58f
        const val HYBRID_TOP_MARGIN = 0.14f
        const val CASCADE_AGREE_THRESHOLD = 0.55f
        const val CASCADE_OCR_THRESHOLD = 0.60f
    }
}
