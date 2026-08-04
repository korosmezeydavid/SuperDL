package com.superdl.launcher.currency

import android.graphics.Bitmap
import android.graphics.Color
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.max
import kotlin.math.min

/**
 * A domináns szín összevetése a magyar bankjegyek jellegzetes tónusaival.
 * Segít kiszűrni a címletek összekeverését (pl. 500 vs 1000).
 */
object BanknoteColorVerifier {

    enum class Verdict {
        AGREE,
        NEUTRAL,
        DISAGREE
    }

    fun verify(bitmap: Bitmap, denomination: BanknoteDenomination): Verdict {
        val hue = dominantHue(bitmap) ?: return Verdict.NEUTRAL
        val expected = expectedHueRange(denomination)
        if (hueDistance(hue, expected.center) <= expected.tolerance) {
            return Verdict.AGREE
        }
        val nearestOther = BanknoteDenomination.entries
            .filter { it != denomination }
            .minByOrNull { hueDistance(hue, expectedHueRange(it).center) }
            ?: return Verdict.NEUTRAL
        val otherRange = expectedHueRange(nearestOther)
        val distPredicted = hueDistance(hue, expected.center)
        val distOther = hueDistance(hue, otherRange.center)
        return if (distOther + 8f < distPredicted) Verdict.DISAGREE else Verdict.NEUTRAL
    }

    private data class HueRange(val center: Float, val tolerance: Float)

    /**
     * A tartományok a [com.superdl.launcher.currency.trainer.BanknoteBuiltinColorReference]
     * mért Hue-középpontjaival egyeznek. Eltérés esetén a classifier AGREE/DISAGREE
     * ellentmondott a hybrid szín-útvonalnak → téves elutasítás vagy hamis egyetértés.
     *
     * 500 barnás-vörös ~12°, 1000 kék ~200°, 2000 drapp ~36°,
     * 5000 zöld ~108°, 10000 lila ~318°, 20000 zöldes-drapp ~75°.
     */
    private fun expectedHueRange(denomination: BanknoteDenomination): HueRange = when (denomination) {
        // Összhangban a BanknoteBuiltinColorReference / Stage1 HUF HSV tartományaival.
        BanknoteDenomination.HUF_500 -> HueRange(12f, 18f)
        BanknoteDenomination.HUF_1000 -> HueRange(200f, 32f)
        BanknoteDenomination.HUF_2000 -> HueRange(36f, 22f)
        BanknoteDenomination.HUF_5000 -> HueRange(108f, 32f)
        BanknoteDenomination.HUF_10000 -> HueRange(318f, 40f)
        BanknoteDenomination.HUF_20000 -> HueRange(75f, 24f)
    }

    private fun dominantHue(bitmap: Bitmap): Float? {
        val width = bitmap.width
        val height = bitmap.height
        if (width < 8 || height < 8) return null

        val left = (width * 0.22f).toInt()
        val right = (width * 0.78f).toInt()
        val top = (height * 0.25f).toInt()
        val bottom = (height * 0.75f).toInt()

        var sinSum = 0.0
        var cosSum = 0.0
        var weightSum = 0.0
        val stepX = max(1, (right - left) / 14)
        val stepY = max(1, (bottom - top) / 14)

        for (y in top until bottom step stepY) {
            for (x in left until right step stepX) {
                val pixel = bitmap.getPixel(x, y)
                val hsv = FloatArray(3)
                Color.colorToHSV(pixel, hsv)
                val saturation = hsv[1]
                val value = hsv[2]
                if (saturation < 0.12f || value < 0.12f) continue
                val weight = saturation * value
                val radians = Math.toRadians(hsv[0].toDouble())
                sinSum += kotlin.math.sin(radians) * weight
                cosSum += kotlin.math.cos(radians) * weight
                weightSum += weight
            }
        }

        if (weightSum < 0.5) return null
        val hue = Math.toDegrees(atan2(sinSum, cosSum)).toFloat()
        return if (hue < 0f) hue + 360f else hue
    }

    private fun hueDistance(a: Float, b: Float): Float {
        val diff = abs(a - b)
        return min(diff, 360f - diff)
    }
}