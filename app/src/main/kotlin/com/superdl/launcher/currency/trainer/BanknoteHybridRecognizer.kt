package com.superdl.launcher.currency.trainer

import android.content.Context
import android.graphics.Bitmap

/**
 * RÉGI hibrid döntéshozó (tanított profil + beépített szín + OCR refine).
 *
 * A fő útvonal 1.55.0-tól a [com.superdl.launcher.currency.cascade.BanknoteCascadeUseCase]
 * prioritásos kaszkádja (szín+geometria → OCR → opcionális YOLO).
 * Ez az objektum a tanított profilokhoz és kompatibilitáshoz marad.
 */
object BanknoteHybridRecognizer {

    enum class Source { TRAINED, BUILTIN, OCR }

    data class Outcome(
        val denomination: String,
        val label: String,
        val confidence: Float,
        val source: Source,
        val ocrConfirmed: Boolean
    )

    /**
     * A szín-alapú felismerés (gyors, szinkron). Az OCR-t külön, aszinkron
     * hívja a hívó (mert az ML Kit callback-alapú), és a refineWithOcr-rel
     * pontosítja az eredményt.
     */
    fun recognizeByColor(context: Context, bitmap: Bitmap): Outcome? {
        // 1. Tanított profilok elsőbbsége.
        val profiles = BanknoteTrainerStore.getAll(context)
        if (profiles.isNotEmpty()) {
            BanknoteTrainedMatcher.recognize(profiles, bitmap)?.let {
                return Outcome(it.denomination, it.label, it.confidence, Source.TRAINED, false)
            }
        }
        // 2. Beépített szín-referencia (tanítás nélkül is).
        BanknoteBuiltinColorReference.recognize(bitmap)?.let {
            return Outcome(it.denomination, it.label, it.confidence, Source.BUILTIN, false)
        }
        return null
    }

    /**
     * Az OCR-eredmény beépítése. Ha az OCR olvasott érvényes címletet:
     *  - ha egyezik a szín-tippel → megerősítve (magasabb bizalom),
     *  - ha eltér → az OCR nyer (a látható szám a legmegbízhatóbb).
     * Ha az OCR nem olvasott számot, a szín-tipp marad változatlanul.
     */
    fun refineWithOcr(colorOutcome: Outcome?, ocrText: String): Outcome? {
        val ocrDenom = BanknoteOcrAnalyzer.extractDenomination(ocrText)
        if (ocrDenom == null) return colorOutcome  // OCR nem látott számot -> marad a szín

        val label = BanknoteTrainerStore.labelFor(ocrDenom)
        if (colorOutcome == null) {
            // Nem volt szín-tipp, de az OCR látott számot -> az OCR ad címletet.
            return Outcome(ocrDenom, label, 0.7f, Source.OCR, true)
        }
        return if (ocrDenom == colorOutcome.denomination) {
            // Szín + OCR egyetért -> megerősítve, magas bizalom.
            colorOutcome.copy(
                confidence = (colorOutcome.confidence + 0.3f).coerceAtMost(1f),
                ocrConfirmed = true
            )
        } else {
            // Eltérnek -> a látható szám nyer.
            Outcome(ocrDenom, label, 0.75f, Source.OCR, true)
        }
    }
}
