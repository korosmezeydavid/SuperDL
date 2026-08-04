package com.superdl.launcher.environment

import kotlin.math.abs
import kotlin.math.hypot

class AnnouncementDebouncer(
    private val cooldownMs: Long = 3000L,
    private val centerShiftThreshold: Float = 0.12f,
    private val areaShiftRatio: Float = 0.30f
) {
    private data class Entry(
        val spokenAt: Long,
        val centerX: Float,
        val centerY: Float,
        val area: Float
    )

    private val history = mutableMapOf<String, Entry>()

    fun shouldAnnounce(
        key: String,
        centerX: Float,
        centerY: Float,
        area: Float,
        now: Long = System.currentTimeMillis()
    ): Boolean {
        val previous = history[key]
        if (previous == null) {
            history[key] = Entry(now, centerX, centerY, area)
            return true
        }

        val elapsed = now - previous.spokenAt
        if (elapsed < cooldownMs) {
            val centerShift = hypot(
                (centerX - previous.centerX).toDouble(),
                (centerY - previous.centerY).toDouble()
            ).toFloat()
            val areaChange = if (previous.area > 0f) {
                abs(area - previous.area) / previous.area
            } else {
                1f
            }
            if (centerShift < centerShiftThreshold && areaChange < areaShiftRatio) {
                return false
            }
        }

        history[key] = Entry(now, centerX, centerY, area)
        return true
    }

    fun clear() {
        history.clear()
    }
}