package com.superdl.launcher.timer

object VoiceDurationParser {

    private val numberWords = mapOf(
        "nulla" to 0, "egy" to 1, "kettő" to 2, "ketto" to 2, "három" to 3, "harom" to 3,
        "négy" to 4, "negy" to 4, "öt" to 5, "ot" to 5, "hat" to 6, "hét" to 7, "het" to 7,
        "nyolc" to 8, "kilenc" to 9, "tíz" to 10, "tiz" to 10, "tizenegy" to 11,
        "tizenkettő" to 12, "tizenketto" to 12, "tizenhárom" to 13, "tizenharom" to 13,
        "tizennégy" to 14, "tizennegy" to 14, "tizenöt" to 15, "tizenot" to 15,
        "tizenhat" to 16, "tizenhét" to 17, "tizenhet" to 17, "tizennyolc" to 18,
        "tizenkilenc" to 19, "húsz" to 20, "husz" to 20, "huszonegy" to 21,
        "huszonkettő" to 22, "huszonketto" to 22, "huszonhárom" to 23, "huszonharom" to 23,
        "huszonnégy" to 24, "huszonnegy" to 24, "huszonöt" to 25, "huszonot" to 25,
        "huszonhat" to 26, "huszonhét" to 27, "huszonhet" to 27, "huszonnyolc" to 28,
        "huszonkilenc" to 29, "harminc" to 30, "negyven" to 40, "ötven" to 50,
        "hatvan" to 60, "hetven" to 70, "nyolcvan" to 80, "kilencven" to 90,
        "száz" to 100, "szaz" to 100
    )

    fun parseAmount(spoken: String): Int? {
        val normalized = spoken.trim().lowercase()
            .replace("óra", " ")
            .replace("ora", " ")
            .replace("perc", " ")
            .replace("percek", " ")
            .replace(":", " ")
            .replace(".", " ")
            .replace(",", " ")
            .replace(Regex("\\s+"), " ")
            .trim()

        if (normalized.isBlank()) return null

        Regex("\\d+").find(normalized)?.value?.toIntOrNull()?.let { return it }

        val words = normalized.split(" ").filter { it.isNotBlank() }
        if (words.isEmpty()) return null

        var total = 0
        for (word in words) {
            val value = numberWords[word] ?: word.toIntOrNull() ?: return null
            total += value
        }
        return total.coerceAtLeast(1)
    }
}