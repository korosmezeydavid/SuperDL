package com.superdl.launcher.voice

object VoiceTimeParser {

    private val hourWords = mapOf(
        "nulla" to 0, "egy" to 1, "kettő" to 2, "ketto" to 2, "három" to 3, "harom" to 3,
        "négy" to 4, "negy" to 4, "öt" to 5, "ot" to 5, "hat" to 6, "hét" to 7, "het" to 7,
        "nyolc" to 8, "kilenc" to 9, "tíz" to 10, "tiz" to 10, "tizenegy" to 11,
        "tizenkettő" to 12, "tizenketto" to 12, "tizenhárom" to 13, "tizenharom" to 13,
        "tizennégy" to 14, "tizennegy" to 14, "tizenöt" to 15, "tizenot" to 15,
        "tizenhat" to 16, "tizenhét" to 17, "tizenhet" to 17, "tizennyolc" to 18,
        "tizenkilenc" to 19, "húsz" to 20, "husz" to 20, "huszonegy" to 21,
        "huszonkettő" to 22, "huszonketto" to 22, "huszonhárom" to 23, "huszonharom" to 23
    )

    private val minuteWords = mapOf(
        "nulla" to 0, "öt" to 5, "ot" to 5, "tíz" to 10, "tiz" to 10, "tizenöt" to 15,
        "tizenot" to 15, "húsz" to 20, "husz" to 20, "huszonöt" to 25, "huszonot" to 25,
        "harminc" to 30, "harmincöt" to 35, "negyven" to 40, "negyvenöt" to 45,
        "ötven" to 50, "ötvenöt" to 55
    )

    fun parse(spoken: String): Pair<Int, Int>? {
        val normalized = spoken.trim().lowercase()
            .replace("óra", " ")
            .replace("ora", " ")
            .replace("perc", " ")
            .replace(":", " ")
            .replace(".", " ")
            .replace(",", " ")
            .replace(Regex("\\s+"), " ")
            .trim()

        if (normalized.isBlank()) return null

        val digits = Regex("\\d+").findAll(normalized).map { it.value.toInt() }.toList()
        if (digits.size >= 2) {
            return digits[0].coerceIn(0, 23) to digits[1].coerceIn(0, 59)
        }
        if (digits.size == 1) {
            val hour = digits[0].coerceIn(0, 23)
            return hour to 0
        }

        val words = normalized.split(" ").filter { it.isNotBlank() }
        if (words.isEmpty()) return null

        val hour = hourWords[words[0]] ?: return null
        val minute = when {
            words.size >= 2 -> minuteWords[words[1]] ?: words[1].toIntOrNull()?.coerceIn(0, 59) ?: 0
            else -> 0
        }
        return hour to minute
    }
}