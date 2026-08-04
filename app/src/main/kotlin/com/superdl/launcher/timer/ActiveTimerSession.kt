package com.superdl.launcher.timer

data class ActiveTimerSession(
    val timerId: Int,
    val label: String,
    val durationMinutes: Int,
    val announceIntervalMinutes: Int,
    val startedAtMillis: Long,
    val lastAnnouncedElapsedMinutes: Int = 0
) {
    fun elapsedMinutes(nowMillis: Long = System.currentTimeMillis()): Int =
        ((nowMillis - startedAtMillis).coerceAtLeast(0L) / 60_000L).toInt()

    fun remainingMinutes(nowMillis: Long = System.currentTimeMillis()): Int =
        (durationMinutes - elapsedMinutes(nowMillis)).coerceAtLeast(0)

    fun isFinished(nowMillis: Long = System.currentTimeMillis()): Boolean =
        elapsedMinutes(nowMillis) >= durationMinutes
}