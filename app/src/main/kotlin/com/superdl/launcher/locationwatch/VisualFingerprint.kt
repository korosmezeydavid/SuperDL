package com.superdl.launcher.locationwatch

import android.graphics.Bitmap
import android.graphics.Color
object VisualFingerprint {

    private const val HASH_SIZE = 8
    const val MATCH_THRESHOLD = 0.72f

    fun compute(bitmap: Bitmap): String {
        if (bitmap.isRecycled) return ""
        val scaled = Bitmap.createScaledBitmap(bitmap, HASH_SIZE, HASH_SIZE, true)
        return try {
            val pixels = IntArray(HASH_SIZE * HASH_SIZE)
            scaled.getPixels(pixels, 0, HASH_SIZE, 0, 0, HASH_SIZE, HASH_SIZE)
            val avg = pixels.map { pixel ->
                val r = Color.red(pixel)
                val g = Color.green(pixel)
                val b = Color.blue(pixel)
                (r + g + b) / 3
            }.average()
            buildString(HASH_SIZE * HASH_SIZE) {
                pixels.forEach { pixel ->
                    val r = Color.red(pixel)
                    val g = Color.green(pixel)
                    val b = Color.blue(pixel)
                    val lum = (r + g + b) / 3
                    append(if (lum >= avg) '1' else '0')
                }
            }
        } finally {
            if (scaled !== bitmap) {
                scaled.recycle()
            }
        }
    }

    fun similarity(hashA: String, hashB: String): Float {
        if (hashA.length != hashB.length || hashA.isEmpty()) return 0f
        val distance = hammingDistance(hashA, hashB)
        return 1f - (distance.toFloat() / hashA.length.toFloat())
    }

    fun bestSimilarity(referenceHashes: List<String>, candidate: String): Float {
        if (referenceHashes.isEmpty() || candidate.isBlank()) return 0f
        return referenceHashes.maxOf { similarity(it, candidate) }
    }

    private fun hammingDistance(a: String, b: String): Int {
        var distance = 0
        for (i in a.indices) {
            if (a[i] != b[i]) distance++
        }
        return distance
    }

    fun isVisualMatch(referenceHashes: List<String>, bitmap: Bitmap): Boolean {
        if (referenceHashes.isEmpty()) return false
        val candidate = compute(bitmap)
        return bestSimilarity(referenceHashes, candidate) >= MATCH_THRESHOLD
    }
}