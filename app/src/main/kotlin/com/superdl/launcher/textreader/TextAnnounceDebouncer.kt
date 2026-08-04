package com.superdl.launcher.textreader

class TextAnnounceDebouncer(
    private val cooldownMs: Long = 5000L
) {
    private var lastAnnouncedText: String? = null
    private var lastAnnouncedAt: Long = 0L

    fun shouldAutoAnnounce(text: String, now: Long = System.currentTimeMillis()): Boolean {
        if (text.isBlank()) return false
        val normalized = normalize(text)
        if (normalized == lastAnnouncedText && now - lastAnnouncedAt < cooldownMs) {
            return false
        }
        lastAnnouncedText = normalized
        lastAnnouncedAt = now
        return true
    }

    fun markAnnounced(text: String, now: Long = System.currentTimeMillis()) {
        lastAnnouncedText = normalize(text)
        lastAnnouncedAt = now
    }

    fun reset() {
        lastAnnouncedText = null
        lastAnnouncedAt = 0L
    }

    private fun normalize(text: String): String =
        text.lowercase().replace(Regex("\\s+"), " ").trim()
}