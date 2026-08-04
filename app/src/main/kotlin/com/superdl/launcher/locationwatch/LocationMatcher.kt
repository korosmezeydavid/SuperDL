package com.superdl.launcher.locationwatch

import android.graphics.Bitmap

object LocationMatcher {

    const val PROFILE_MATCH_THRESHOLD = 0.55f
    const val MIN_TARGET_TEXT_LENGTH = 4

    fun normalize(text: String): String =
        text.lowercase()
            .replace(Regex("[^a-záéíóöőúüű0-9\\s]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

    fun tokenize(text: String): Set<String> =
        normalize(text)
            .split(' ')
            .filter { it.length >= 2 }
            .toSet()

    fun buildFingerprint(tokens: Set<String>): String =
        tokens.sorted().joinToString("|")

    /**
     * Jaccard-hasonlóság a profil OCR tokenjei és az aktuális OCR szöveg tokenjei között (0..1).
     */
    fun matchProfile(profile: LocationProfile, ocrText: String): Float {
        val profileTokens = profile.ocrTokens
        val ocrTokens = tokenize(ocrText)
        if (profileTokens.isEmpty() || ocrTokens.isEmpty()) return 0f
        val intersection = profileTokens.intersect(ocrTokens).size
        val union = profileTokens.union(ocrTokens).size
        if (union == 0) return 0f
        return intersection.toFloat() / union.toFloat()
    }

    fun matchVisual(profile: LocationProfile, bitmap: Bitmap): Float {
        if (bitmap.isRecycled || profile.visualHashes.isEmpty()) return 0f
        return runCatching {
            VisualFingerprint.bestSimilarity(profile.visualHashes, VisualFingerprint.compute(bitmap))
        }.getOrDefault(0f)
    }

    fun isProfileMatch(profile: LocationProfile, ocrText: String, bitmap: Bitmap? = null): Boolean {
        val ocrScore = matchProfile(profile, ocrText)
        if (ocrScore >= PROFILE_MATCH_THRESHOLD) return true
        val visualBitmap = bitmap ?: return false
        return matchVisual(profile, visualBitmap) >= VisualFingerprint.MATCH_THRESHOLD
    }

    fun matchTargetText(targetText: String, ocrText: String): Boolean {
        val normalizedTarget = normalize(targetText)
        if (normalizedTarget.length < MIN_TARGET_TEXT_LENGTH) return false
        val normalizedOcr = normalize(ocrText)
        return normalizedOcr.contains(normalizedTarget)
    }
}