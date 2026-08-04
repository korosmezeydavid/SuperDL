package com.superdl.launcher.dictaphone

object DictaphoneSpeech {

    fun speakElapsed(elapsedMs: Long, paused: Boolean): String {
        val totalSeconds = (elapsedMs / 1000).toInt()
        val minutes = totalSeconds / 60
        val seconds = totalSeconds % 60
        val time = when {
            minutes > 0 && seconds > 0 -> "$minutes perc $seconds másodperc"
            minutes > 0 -> "$minutes perc"
            else -> "$seconds másodperc"
        }
        return if (paused) "Felvétel szünetel. Eltelt idő: $time." else "Felvétel folyamatban. Eltelt idő: $time."
    }

    fun speakSaved(entry: DictaphoneRecordingEntry): String =
        "Felvétel mentve: ${entry.speakSummary()}"

    fun speakSettingsIntro(config: DictaphoneConfig): String =
        "Minőség és formátum beállítása. Aktuális: ${config.speakSummary()}. Söpörj fel-le választás, jobbra módosítás."
}