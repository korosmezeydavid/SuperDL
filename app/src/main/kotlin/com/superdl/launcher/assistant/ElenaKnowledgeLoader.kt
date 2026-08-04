package com.superdl.launcher.assistant

import android.content.Context

/**
 * A SUPERDL.TXT (assets/elena_tudas_superdl.txt) szekcióinak betöltése és keresése.
 */
object ElenaKnowledgeLoader {

    private const val ASSET_FILE = "elena_tudas_superdl.txt"

    private data class Section(
        val id: String,
        val title: String,
        val body: String,
        val keywords: List<String>
    )

    @Volatile
    private var sections: List<Section>? = null

    fun ensureLoaded(context: Context): Unit {
        if (sections != null) return
        synchronized(this) {
            if (sections != null) return
            sections = parseAsset(context)
        }
    }

    fun findSectionAnswer(context: Context, raw: String): String? {
        ensureLoaded(context)
        val text = VoiceAssistantHelper.normalize(raw)
        if (text.length < 4) return null

        var best: Section? = null
        var bestScore = 0

        for (section in sections.orEmpty()) {
            val score = scoreSection(text, section)
            if (score > bestScore) {
                bestScore = score
                best = section
            }
        }

        return if (bestScore >= 5 && best != null) {
            "${best.title}. ${summarizeForTts(best.body)}"
        } else {
            null
        }
    }

    fun sectionTitles(context: Context): List<String> {
        ensureLoaded(context)
        return sections.orEmpty().map { it.title }
    }

    private fun parseAsset(context: Context): List<Section> {
        return try {
            val text = context.assets.open(ASSET_FILE).bufferedReader(Charsets.UTF_8).readText()
            parseSections(text)
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun parseSections(text: String): List<Section> {
        val result = mutableListOf<Section>()
        val lines = text.lines()
        var currentId = ""
        var currentTitle = ""
        val bodyLines = mutableListOf<String>()

        fun flush() {
            if (currentTitle.isBlank()) return
            val body = bodyLines.joinToString("\n").trim()
            if (body.isBlank()) return
            result.add(
                Section(
                    id = currentId,
                    title = currentTitle,
                    body = body,
                    keywords = buildKeywords(currentTitle, body)
                )
            )
        }

        val sectionHeader = Regex("""^(\d+(?:\.\d+)?)\s{2,}(.+)$""")
        val majorHeader = Regex("""^\s*(\d+)\.\s+(.+)$""")

        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.startsWith("====") || trimmed.startsWith("────")) continue

            val sectionMatch = sectionHeader.matchEntire(trimmed)
            if (sectionMatch != null) {
                flush()
                bodyLines.clear()
                currentId = sectionMatch.groupValues[1]
                currentTitle = sectionMatch.groupValues[2].trim()
                continue
            }

            val majorMatch = majorHeader.matchEntire(trimmed)
            if (majorMatch != null && !trimmed.contains("──")) {
                flush()
                bodyLines.clear()
                currentId = majorMatch.groupValues[1]
                currentTitle = majorMatch.groupValues[2].trim()
                continue
            }

            if (currentTitle.isNotBlank()) {
                bodyLines.add(line)
            }
        }
        flush()
        return result
    }

    private fun buildKeywords(title: String, body: String): List<String> {
        val titleNorm = VoiceAssistantHelper.normalize(title)
        val titleWords = titleNorm.split(" ").filter { it.length >= 4 }
        val extras = mutableListOf<String>()
        val lowerBody = VoiceAssistantHelper.normalize(body)
        val markers = listOf(
            "nevjegybol hivas", "hivasnaplo", "sms", "e-mail", "smtp", "ebreszto", "naptar",
            "youtube", "konyvtar", "konyvjelzo", "idojaras", "hirek", "rss", "bkk", "megallo",
            "qr", "zseblampa", "fenydetektor", "szamologep", "hangos asszisztens", "elena",
            "wifi", "bluetooth", "ertesites", "engedely", "korlat", "gesztus", "diktalas", "tts"
        )
        for (marker in markers) {
            if (lowerBody.contains(marker) || titleNorm.contains(marker)) {
                extras.add(marker)
            }
        }
        return (listOf(titleNorm) + titleWords + extras).distinct()
    }

    private fun scoreSection(text: String, section: Section): Int {
        var score = 0
        val titleNorm = VoiceAssistantHelper.normalize(section.title)
        if (text.contains(titleNorm)) score += titleNorm.length + 6
        if (titleNorm.length >= 6 && text.contains(titleNorm.take(titleNorm.length / 2))) {
            score += 4
        }
        for (keyword in section.keywords) {
            if (keyword.length < 3) continue
            when {
                text == keyword -> score += keyword.length + 5
                text.contains(keyword) -> score += keyword.length + 2
            }
        }
        return score
    }

    private fun summarizeForTts(body: String, maxLen: Int = 520): String {
        val bullets = body.lines()
            .map { it.trim() }
            .filter { line ->
                line.startsWith("•") ||
                    (line.startsWith("„") && line.endsWith("\"")) ||
                    line.matches(Regex("""^[A-ZÁÉÍÓÖŐÚÜŰ].{8,}"""))
            }
            .map { it.removePrefix("•").trim().trim('"', '„', '"') }
            .filter { it.length in 8..120 }
            .distinct()
            .take(5)

        val summary = when {
            bullets.isNotEmpty() -> bullets.joinToString(" ")
            else -> body.lines()
                .map { it.trim() }
                .filter { it.isNotBlank() && !it.startsWith("─") && !it.startsWith("=") }
                .take(3)
                .joinToString(" ")
        }

        return if (summary.length <= maxLen) {
            summary
        } else {
            summary.take(maxLen).substringBeforeLast(" ").trim() + "…"
        }
    }
}