package com.superdl.launcher.timer

object TimerSpeech {

    fun speakMinutes(minutes: Int): String = when {
        minutes <= 0 -> "nulla perc"
        minutes == 1 -> "1 perc"
        minutes < 60 -> "$minutes perc"
        minutes % 60 == 0 -> {
            val hours = minutes / 60
            if (hours == 1) "1 óra" else "$hours óra"
        }
        else -> {
            val hours = minutes / 60
            val rest = minutes % 60
            "$hours óra $rest perc"
        }
    }

    fun speakProgress(label: String, elapsedMinutes: Int, remainingMinutes: Int): String {
        val name = label.ifBlank { "Időzítő" }
        return "$name. Eltelt: ${speakMinutes(elapsedMinutes)}. Hátra van: ${speakMinutes(remainingMinutes)}."
    }

    fun speakStarted(label: String, durationMinutes: Int, intervalMinutes: Int): String {
        val name = label.ifBlank { "Időzítő" }
        return "$name elindult. Összesen ${speakMinutes(durationMinutes)}. " +
            "Jelzés ${speakMinutes(intervalMinutes)}enként."
    }

    fun speakFinished(label: String): String {
        val name = label.ifBlank { "Időzítő" }
        return "$name véget ért."
    }
}