package com.superdl.launcher.currency.trainer

import android.graphics.Bitmap
import android.graphics.Color

/**
 * Fény-tűrő szín-ujjlenyomat magyar bankjegyekhez.
 *
 * A kulcs a HSV színtér: a Hue (színárnyalat) csatorna a megvilágítástól
 * FÜGGETLEN — egy barna bankjegy sötétben és napfényben is közel ugyanazt a
 * Hue-t adja, csak a Value (fényesség) változik. Ezért a Hue-hisztogramot
 * használjuk ujjlenyomatként, nem a nyers RGB-átlagot (amit az árnyék tönkretesz).
 *
 * A magyar forint-sorozat címletei erősen eltérő alapszínűek (500 barnás,
 * 1000 kékes, 2000 barnás-drapp, 5000 zöld, 10000 rózsaszín-lila, 20000 zöldes),
 * ezért a domináns Hue szinte önmagában azonosítja a címletet — gyűrötten,
 * ferdén, részben takarva is.
 *
 * Semmilyen külső könyvtár (OpenCV) nem kell: az Android beépített
 * Color.colorToHSV-jét használjuk.
 */
object BanknoteColorFingerprint {

    // A Hue-t (0..360°) ennyi vödörre osztjuk. 24 vödör = 15°/vödör, elég finom
    // a címletek elkülönítéséhez, de elég durva, hogy a zaj ne bontsa szét.
    const val HUE_BINS = 24

    // Csak a "színes" pixeleket számoljuk (a bankjegy), a fakó hátteret nem.
    private const val MIN_SATURATION = 0.18f
    private const val MIN_VALUE = 0.12f
    private const val MAX_VALUE = 0.97f  // a fehér csúcsfény (tükröződés) kizárása

    // Ekkora négyzetre skálázunk a hisztogram-számításhoz.
    private const val SAMPLE_SIZE = 64

    /**
     * Normalizált Hue-hisztogram (az elemek összege 1.0, ha volt elég színes
     * pixel; különben mind 0).
     */
    fun compute(bitmap: Bitmap): FloatArray {
        val hist = FloatArray(HUE_BINS)
        if (bitmap.isRecycled) return hist
        val scaled = Bitmap.createScaledBitmap(bitmap, SAMPLE_SIZE, SAMPLE_SIZE, true)
        try {
            val pixels = IntArray(SAMPLE_SIZE * SAMPLE_SIZE)
            scaled.getPixels(pixels, 0, SAMPLE_SIZE, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
            val hsv = FloatArray(3)
            var colorfulCount = 0
            for (pixel in pixels) {
                Color.colorToHSV(pixel, hsv)
                val h = hsv[0]; val s = hsv[1]; val v = hsv[2]
                if (s < MIN_SATURATION || v < MIN_VALUE || v > MAX_VALUE) continue
                val bin = ((h / 360f) * HUE_BINS).toInt().coerceIn(0, HUE_BINS - 1)
                hist[bin] += 1f
                colorfulCount++
            }
            if (colorfulCount > 0) {
                val total = colorfulCount.toFloat()
                for (i in hist.indices) hist[i] = hist[i] / total
            }
        } finally {
            if (scaled !== bitmap) scaled.recycle()
        }
        return hist
    }

    /**
     * Két Hue-hisztogram hasonlósága (0..1) hisztogram-metszettel.
     * 1.0 = azonos szín-eloszlás.
     */
    fun similarity(a: FloatArray, b: FloatArray): Float {
        if (a.size != b.size || a.isEmpty()) return 0f
        var intersection = 0f
        for (i in a.indices) intersection += minOf(a[i], b[i])
        return intersection.coerceIn(0f, 1f)
    }

    fun bestSimilarity(references: List<FloatArray>, candidate: FloatArray): Float {
        if (references.isEmpty()) return 0f
        return references.maxOf { similarity(it, candidate) }
    }

    /**
     * A "színes" pixelek aránya — a HALLUCINÁCIÓ-KAPU. Ha a kép fakó (üres
     * asztal, kéz, fal), nincs bankjegy, és a felismerő HALLGAT.
     */
    fun colorfulFraction(bitmap: Bitmap): Float {
        if (bitmap.isRecycled) return 0f
        val scaled = Bitmap.createScaledBitmap(bitmap, SAMPLE_SIZE, SAMPLE_SIZE, true)
        return try {
            val pixels = IntArray(SAMPLE_SIZE * SAMPLE_SIZE)
            scaled.getPixels(pixels, 0, SAMPLE_SIZE, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
            val hsv = FloatArray(3)
            var colorful = 0
            for (pixel in pixels) {
                Color.colorToHSV(pixel, hsv)
                if (hsv[1] >= MIN_SATURATION && hsv[2] in MIN_VALUE..MAX_VALUE) colorful++
            }
            colorful.toFloat() / pixels.size.toFloat()
        } catch (_: Exception) {
            0f
        } finally {
            if (scaled !== bitmap) scaled.recycle()
        }
    }

    fun encode(hist: FloatArray): String =
        hist.joinToString(",") { "%.5f".format(it) }

    fun decode(text: String): FloatArray {
        if (text.isBlank()) return FloatArray(HUE_BINS)
        return try {
            val parts = text.split(",")
            FloatArray(HUE_BINS) { i -> parts.getOrNull(i)?.toFloatOrNull() ?: 0f }
        } catch (_: Exception) {
            FloatArray(HUE_BINS)
        }
    }
}
