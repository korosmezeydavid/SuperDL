package com.superdl.launcher.currency.cascade

import android.graphics.Bitmap
import android.graphics.Color
import com.superdl.launcher.currency.BanknoteDenomination
import com.superdl.launcher.currency.trainer.BanknoteBuiltinColorReference
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * Kaszkád 1. szint: magyar forint specifikus szín + geometria előszűrés.
 *
 * Gyors, szinkron, allokáció-takarékos. Cél: < 8 ms / frame low-end eszközön.
 * Csak erős szín-egyezés esetén ad tovább jelöltet a 2. szintnek (OCR).
 *
 * Edge case-ek:
 *  - kopott / részleges takarás: colorful fraction + tolerancia
 *  - erős árnyék: HSV Hue dominál (Value-tól független)
 *  - ferde tartás: aspect tartomány laza (1.15..3.4)
 *  - több bankjegy: a középső ROI domináns színe dönt (a fő tartott jegy)
 */
object BanknoteColorGeometryStage {

    data class Candidate(
        val denomination: BanknoteDenomination,
        val score: Float,
        val hueDistance: Float
    )

    data class Result(
        val top: Candidate?,
        val second: Candidate?,
        val candidates: List<Candidate>,
        val dominantHue: Float?,
        val colorfulFraction: Float,
        val aspectRatio: Float,
        val edgeDensity: Float,
        val aspectOk: Boolean,
        val edgeOk: Boolean,
        val strongMatch: Boolean,
        val weakMatch: Boolean,
        val elapsedMs: Long
    ) {
        /** Erős szín-egyezés: OCR-re továbbengedhető. */
        val passesColorGate: Boolean
            get() = strongMatch || weakMatch

        val topDenomination: BanknoteDenomination?
            get() = top?.denomination
    }

    private val hsvScratch = FloatArray(3)

    fun analyze(bitmap: Bitmap): Result {
        val t0 = System.nanoTime()
        if (bitmap.isRecycled || bitmap.width < 8 || bitmap.height < 8) {
            return emptyResult(0L)
        }

        val sample = BanknoteCascadeConfig.COLOR_SAMPLE_SIZE
        val scaled = try {
            Bitmap.createScaledBitmap(bitmap, sample, sample, true)
        } catch (_: OutOfMemoryError) {
            return emptyResult((System.nanoTime() - t0) / 1_000_000L)
        }

        return try {
            val pixels = IntArray(sample * sample)
            scaled.getPixels(pixels, 0, sample, 0, 0, sample, sample)

            var sumSin = 0.0
            var sumCos = 0.0
            var colorful = 0
            var minX = sample
            var minY = sample
            var maxX = -1
            var maxY = -1
            var edgeSum = 0.0
            var edgeCount = 0

            // Középső 70% ROI — a kéz/háttér szélein kevésbé zavar.
            val x0 = (sample * 0.15f).toInt()
            val x1 = (sample * 0.85f).toInt()
            val y0 = (sample * 0.18f).toInt()
            val y1 = (sample * 0.82f).toInt()

            for (y in y0 until y1) {
                val row = y * sample
                for (x in x0 until x1) {
                    val idx = row + x
                    val pixel = pixels[idx]
                    Color.colorToHSV(pixel, hsvScratch)
                    val h = hsvScratch[0]
                    val s = hsvScratch[1]
                    val v = hsvScratch[2]
                    // Színes pixel: bankjegy alapszín; fakó/csúcsfény kihagyva.
                    if (s < 0.16f || v < 0.10f || v > 0.98f) continue

                    val weight = (s * v).toDouble()
                    val rad = Math.toRadians(h.toDouble())
                    sumSin += kotlin.math.sin(rad) * weight
                    sumCos += kotlin.math.cos(rad) * weight
                    colorful++

                    if (x < minX) minX = x
                    if (x > maxX) maxX = x
                    if (y < minY) minY = y
                    if (y > maxY) maxY = y

                    // Egyszerű élsűrűség (luminancia-különbség jobbra/le).
                    if (x + 1 < x1 && y + 1 < y1) {
                        val lum = luminance(pixel)
                        val lumR = luminance(pixels[idx + 1])
                        val lumD = luminance(pixels[idx + sample])
                        edgeSum += abs(lum - lumR) + abs(lum - lumD)
                        edgeCount++
                    }
                }
            }

            val roiPixels = max(1, (x1 - x0) * (y1 - y0))
            val colorfulFraction = colorful.toFloat() / roiPixels.toFloat()
            val elapsedMs = (System.nanoTime() - t0) / 1_000_000L

            if (colorful < roiPixels * BanknoteCascadeConfig.COLOR_MIN_COLORFUL_FRACTION) {
                return Result(
                    top = null,
                    second = null,
                    candidates = emptyList(),
                    dominantHue = null,
                    colorfulFraction = colorfulFraction,
                    aspectRatio = 0f,
                    edgeDensity = 0f,
                    aspectOk = false,
                    edgeOk = false,
                    strongMatch = false,
                    weakMatch = false,
                    elapsedMs = elapsedMs
                )
            }

            var hue = Math.toDegrees(kotlin.math.atan2(sumSin, sumCos)).toFloat()
            if (hue < 0f) hue += 360f

            val boxW = (maxX - minX + 1).toFloat().coerceAtLeast(1f)
            val boxH = (maxY - minY + 1).toFloat().coerceAtLeast(1f)
            val aspect = max(boxW, boxH) / min(boxW, boxH)
            val aspectOk = aspect in BanknoteCascadeConfig.ASPECT_MIN..BanknoteCascadeConfig.ASPECT_MAX

            val edgeDensity = if (edgeCount > 0) (edgeSum / edgeCount).toFloat() else 0f
            val edgeOk = edgeDensity >= BanknoteCascadeConfig.EDGE_DENSITY_MIN

            val scored = scoreDenominations(hue)
            val top = scored.firstOrNull()
            val second = scored.getOrNull(1)
            val margin = (top?.score ?: 0f) - (second?.score ?: 0f)

            // Erős match: magas pont + margin + (aspect VAGY edge) — kopott jegyeknél
            // az aspect/edge egyikének elég, ha a szín nagyon tiszta.
            val strongColor = top != null &&
                top.score >= BanknoteCascadeConfig.COLOR_STRONG_SCORE &&
                margin >= BanknoteCascadeConfig.COLOR_MIN_MARGIN

            val mediumColor = top != null &&
                top.score >= BanknoteCascadeConfig.COLOR_MIN_SCORE &&
                margin >= BanknoteCascadeConfig.COLOR_MIN_MARGIN * 0.85f

            val geometrySoft = aspectOk || edgeOk
            val strongMatch = strongColor && geometrySoft
            val weakMatch = !strongMatch && mediumColor && geometrySoft

            // Csak a erős/közepes színpont feletti jelölteket adjuk OCR-nek.
            val candidates = scored.filter {
                it.score >= BanknoteCascadeConfig.COLOR_MIN_SCORE * 0.75f
            }

            if (elapsedMs > BanknoteCascadeConfig.COLOR_STAGE_BUDGET_MS) {
                android.util.Log.w(
                    "SDL_CASH",
                    "Stage1 lassú: ${elapsedMs}ms (cél < ${BanknoteCascadeConfig.COLOR_STAGE_BUDGET_MS}ms)"
                )
            }

            android.util.Log.i(
                "SDL_CASH",
                "S1 hue=${"%.0f".format(hue)}° top=${top?.denomination?.valueHuf} " +
                    "sc=${"%.2f".format(top?.score ?: 0f)} m=${"%.2f".format(margin)} " +
                    "asp=${"%.2f".format(aspect)} edge=${"%.3f".format(edgeDensity)} " +
                    "cf=${"%.2f".format(colorfulFraction)} strong=$strongMatch ${elapsedMs}ms"
            )

            Result(
                top = top,
                second = second,
                candidates = candidates,
                dominantHue = hue,
                colorfulFraction = colorfulFraction,
                aspectRatio = aspect,
                edgeDensity = edgeDensity,
                aspectOk = aspectOk,
                edgeOk = edgeOk,
                strongMatch = strongMatch,
                weakMatch = weakMatch,
                elapsedMs = elapsedMs
            )
        } catch (e: Exception) {
            android.util.Log.w("SDL_CASH", "Stage1 hiba: ${e.message}")
            emptyResult((System.nanoTime() - t0) / 1_000_000L)
        } finally {
            if (scaled !== bitmap && !scaled.isRecycled) scaled.recycle()
        }
    }

    private fun scoreDenominations(hue: Float): List<Candidate> {
        return BanknoteBuiltinColorReference.REFERENCES.mapNotNull { ref ->
            val denom = BanknoteDenomination.fromValue(ref.denomination) ?: return@mapNotNull null
            val dist = hueDistance(hue, ref.hueCenter)
            val score = (1f - dist / ref.hueTolerance).coerceAtLeast(0f)
            Candidate(denom, score, dist)
        }.sortedByDescending { it.score }
    }

    private fun hueDistance(a: Float, b: Float): Float {
        val d = abs(a - b) % 360f
        return if (d > 180f) 360f - d else d
    }

    private fun luminance(pixel: Int): Float {
        val r = Color.red(pixel) / 255f
        val g = Color.green(pixel) / 255f
        val b = Color.blue(pixel) / 255f
        return 0.299f * r + 0.587f * g + 0.114f * b
    }

    private fun emptyResult(elapsedMs: Long) = Result(
        top = null,
        second = null,
        candidates = emptyList(),
        dominantHue = null,
        colorfulFraction = 0f,
        aspectRatio = 0f,
        edgeDensity = 0f,
        aspectOk = false,
        edgeOk = false,
        strongMatch = false,
        weakMatch = false,
        elapsedMs = elapsedMs
    )
}
