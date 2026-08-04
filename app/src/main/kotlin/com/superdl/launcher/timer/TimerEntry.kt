package com.superdl.launcher.timer

data class TimerEntry(
    val id: Int,
    val label: String,
    val durationMinutes: Int,
    val announceIntervalMinutes: Int
) {
    fun speakDuration(): String = TimerSpeech.speakMinutes(durationMinutes)

    fun speakInterval(): String = TimerSpeech.speakMinutes(announceIntervalMinutes)

    fun speakSummary(): String {
        val name = label.ifBlank { "Időzítő" }
        return "$name, ${speakDuration()}, jelzés ${speakInterval()}enként"
    }
}