package com.superdl.launcher.currency

import android.graphics.Bitmap
import android.graphics.Color
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * Különbség üres járat és gyenge fény között.
 * Üres járat → ne szóljon hamis címletet. Gyenge fény → vaku kérés.
 */
object BanknoteFrameGate {

    data class Metrics(
        val meanLuminance: Float,
        val luminanceVariance: Float,
        val colorSpread: Float,
        val edgeEnergy: Float,
        val meanSaturation: Float
    )

    data class Decision(
        val isEmptySlot: Boolean,
        val needsMoreLight: Boolean,
        val hasBanknoteLikeContent: Boolean,
        val metrics: Metrics
    )

    fun evaluate(bitmap: Bitmap): Decision {
        val metrics = computeMetrics(bitmap)
        val empty = isEmptySlot(metrics)
        val lowLight = metrics.meanLuminance < LOW_LIGHT_LUMINANCE
        val contentSignals = listOf(
            metrics.luminanceVariance >= MIN_LUMINANCE_VARIANCE,
            metrics.colorSpread >= MIN_COLOR_SPREAD,
            metrics.edgeEnergy >= MIN_EDGE_ENERGY,
            metrics.meanSaturation >= MIN_SATURATION
        ).count { it }

        val hasContent = !empty && contentSignals >= 1
        return Decision(
            isEmptySlot = empty,
            needsMoreLight = lowLight && !empty,
            hasBanknoteLikeContent = hasContent,
            metrics = metrics
        )
    }

    private fun isEmptySlot(metrics: Metrics): Boolean =
        metrics.luminanceVariance < EMPTY_VARIANCE_MAX &&
            metrics.colorSpread < EMPTY_COLOR_SPREAD_MAX &&
            metrics.edgeEnergy < EMPTY_EDGE_MAX &&
            metrics.meanSaturation < EMPTY_SATURATION_MAX

    private fun computeMetrics(bitmap: Bitmap): Metrics {
        val width = bitmap.width
        val height = bitmap.height
        if (width < 8 || height < 8) {
            return Metrics(0f, 0f, 0f, 0f, 0f)
        }

        val left = (width * 0.18f).toInt()
        val right = (width * 0.82f).toInt()
        val top = (height * 0.20f).toInt()
        val bottom = (height * 0.80f).toInt()

        var luminanceSum = 0.0
        var luminanceSqSum = 0.0
        var saturationSum = 0.0
        var edgeSum = 0.0
        var channelSpreadSum = 0.0
        var count = 0

        val stepX = max(1, (right - left) / SAMPLE_GRID)
        val stepY = max(1, (bottom - top) / SAMPLE_GRID)

        for (y in top until bottom step stepY) {
            for (x in left until right step stepX) {
                val pixel = bitmap.getPixel(x, y)
                val r = Color.red(pixel) / 255f
                val g = Color.green(pixel) / 255f
                val b = Color.blue(pixel) / 255f
                val maxC = max(r, max(g, b))
                val minC = min(r, min(g, b))
                val luminance = 0.299f * r + 0.587f * g + 0.114f * b
                val saturation = if (maxC <= 0.001f) 0f else (maxC - minC) / maxC

                luminanceSum += luminance
                luminanceSqSum += luminance * luminance
                saturationSum += saturation
                channelSpreadSum += maxC - minC
                count++

                if (x + stepX < right && y + stepY < bottom) {
                    val lumRight = luminanceOf(bitmap.getPixel(x + stepX, y))
                    val lumDown = luminanceOf(bitmap.getPixel(x, y + stepY))
                    edgeSum += abs(luminance - lumRight) + abs(luminance - lumDown)
                }
            }
        }

        if (count == 0) return Metrics(0f, 0f, 0f, 0f, 0f)

        val meanLum = (luminanceSum / count).toFloat()
        val variance = ((luminanceSqSum / count) - (meanLum * meanLum).toDouble())
            .toFloat()
            .coerceAtLeast(0f)
        return Metrics(
            meanLuminance = meanLum,
            luminanceVariance = variance,
            colorSpread = (channelSpreadSum / count).toFloat(),
            edgeEnergy = (edgeSum / count).toFloat(),
            meanSaturation = (saturationSum / count).toFloat()
        )
    }

    private fun luminanceOf(pixel: Int): Float {
        val r = Color.red(pixel) / 255f
        val g = Color.green(pixel) / 255f
        val b = Color.blue(pixel) / 255f
        return 0.299f * r + 0.587f * g + 0.114f * b
    }

    private const val SAMPLE_GRID = 16
    private const val LOW_LIGHT_LUMINANCE = 0.24f

    private const val MIN_LUMINANCE_VARIANCE = 0.0004f
    private const val MIN_COLOR_SPREAD = 0.015f
    private const val MIN_EDGE_ENERGY = 0.005f
    private const val MIN_SATURATION = 0.02f

    private const val EMPTY_VARIANCE_MAX = 0.00025f
    private const val EMPTY_COLOR_SPREAD_MAX = 0.012f
    private const val EMPTY_EDGE_MAX = 0.004f
    private const val EMPTY_SATURATION_MAX = 0.018f
}