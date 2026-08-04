package com.superdl.launcher.battery

object BatteryPatrolLogic {

    val THRESHOLDS = listOf(20, 18, 16, 14, 12, 10, 8, 6, 4, 2)

    fun thresholdToAlert(level: Int, lastAlerted: Int): Int? {
        for (threshold in THRESHOLDS) {
            if (level <= threshold && lastAlerted > threshold) return threshold
        }
        return null
    }

    fun shouldReset(level: Int, isCharging: Boolean): Boolean =
        isCharging || level > 22

    fun speakMessage(threshold: Int): String {
        val urgency = when {
            threshold <= 4 -> "Kritikus! "
            threshold <= 10 -> "Sürgős figyelmeztetés! "
            else -> "Figyelem! "
        }
        return "$urgency Az akkumulátor töltöttsége $threshold százalék. Csatlakoztasd a töltőt!"
    }
}