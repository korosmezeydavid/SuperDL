package com.superdl.launcher.textreader

/**
 * Észleli, ha az OCR által felismert szöveg érdemben megváltozott
 * (pl. a kamera más részre mutat), nem csak kisebb zajt ad.
 */
class TextChangeDetector(
    private val minChangeRatio: Float = 0.28f
) {
    private var lastSnapshot: String? = null

    fun isMeaningfulChange(text: String): Boolean {
        val normalized = normalize(text)
        if (normalized.length < 4) return false
        val previous = lastSnapshot
        if (previous == null) {
            lastSnapshot = normalized
            return true
        }
        if (normalized == previous) return false
        val changeRatio = tokenChangeRatio(previous, normalized)
        if (changeRatio >= minChangeRatio) {
            lastSnapshot = normalized
            return true
        }
        return false
    }

    fun markAsAnnounced(text: String) {
        lastSnapshot = normalize(text)
    }

    fun reset() {
        lastSnapshot = null
    }

    private fun normalize(text: String): String =
        text.lowercase()
            .replace(Regex("[^a-záéíóöőúüű0-9\\s]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

    private fun tokenChangeRatio(a: String, b: String): Float {
        val tokensA = a.split(' ').filter { it.length >= 2 }.toSet()
        val tokensB = b.split(' ').filter { it.length >= 2 }.toSet()
        if (tokensA.isEmpty() && tokensB.isEmpty()) return 0f
        if (tokensA.isEmpty() || tokensB.isEmpty()) return 1f
        val intersection = tokensA.intersect(tokensB).size
        val union = tokensA.union(tokensB).size
        return 1f - (intersection.toFloat() / union.toFloat())
    }
}