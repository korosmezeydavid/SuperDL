package com.superdl.launcher.locationwatch

class LocationAnnounceDebouncer(
    private val cooldownMs: Long = 30_000L
) {
    private var lastTargetKey: String? = null
    private var lastAnnouncedAt: Long = 0L

    fun shouldAnnounce(targetKey: String, now: Long = System.currentTimeMillis()): Boolean {
        if (targetKey.isBlank()) return false
        if (lastTargetKey == targetKey && now - lastAnnouncedAt < cooldownMs) {
            return false
        }
        lastTargetKey = targetKey
        lastAnnouncedAt = now
        return true
    }

    fun reset() {
        lastTargetKey = null
        lastAnnouncedAt = 0L
    }
}