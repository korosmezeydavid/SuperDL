package com.superdl.launcher.textreader

object TextFormatter {

    private const val MAX_SPEECH_CHARS = 420

    private val medicationKeywords = listOf(
        "mg", "ml", "tabletta", "kapszula", "drazsé", "oldat", "injekció",
        "hatóanyag", "adag", "napi", "bevétel", "gyógyszer", "recept",
        "otc", "rx", "komponens", "hatás", "ellenjavallat"
    )

    private val labelKeywords = listOf(
        "összetétel", "osszetetel", "tartalom", "allergén", "allergen",
        "glutén", "gluten", "laktóz", "laktoz", "cukor", "só", "so",
        "zsír", "zsir", "fehérje", "feherje", "származék", "szarmazek",
        "tápérték", "tapertek", "minőség", "minoseg", "szavatosság", "szavatossag",
        "gyártó", "gyarto", "forgalmazó", "forgalmazo", "eán", "ean"
    )

    fun formatForMode(raw: String, mode: TextReaderMode): String {
        val lines = raw.lines()
            .map { it.trim() }
            .filter { it.length >= 2 }
        if (lines.isEmpty()) return ""

        val ordered = when (mode) {
            TextReaderMode.MEDICATION_BOX -> prioritize(lines, medicationKeywords)
            TextReaderMode.PRODUCT_LABEL -> prioritize(lines, labelKeywords)
            TextReaderMode.GENERAL_TEXT, TextReaderMode.CONTINUOUS -> lines
        }

        return ordered
            .distinct()
            .take(10)
            .joinToString(". ")
            .replace(Regex("\\s+"), " ")
            .take(MAX_SPEECH_CHARS)
            .trim()
    }

    private fun prioritize(lines: List<String>, keywords: List<String>): List<String> {
        val scored = lines.map { line ->
            val lower = line.lowercase()
            val score = keywords.count { keyword -> lower.contains(keyword) }
            line to score
        }
        val hits = scored.filter { it.second > 0 }.sortedByDescending { it.second }.map { it.first }
        val rest = scored.filter { it.second == 0 }.map { it.first }
        return hits + rest
    }
}