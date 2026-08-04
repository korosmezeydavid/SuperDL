package com.superdl.launcher.assistant

import android.content.Context

object ElenaWakeHelper {

    const val ASSISTANT_NAME = "Elena"

    private val BUILT_IN_WAKE_PHRASES = listOf(
        "szia elena",
        "kerlek elena",
        "kérlek elena",
        "hello elena",
        "hallo elena",
        "figyelj elena",
        "he elena",
        "ej elena",
        "elena",
        "szia helena",
        "kerlek helena"
    )

    fun allWakePhrases(context: Context): List<String> {
        val merged = linkedSetOf<String>()
        merged.addAll(BUILT_IN_WAKE_PHRASES.map { VoiceAssistantHelper.normalize(it) })
        ElenaWakeStore.customPhrases(context).forEach { custom ->
            merged.add(VoiceAssistantHelper.normalize(custom.phrase))
        }
        return merged.filter { it.length >= 3 }.sortedByDescending { it.length }
    }

    fun wakeHints(context: Context): List<String> =
        allWakePhrases(context).map { phrase ->
            phrase.split(" ").joinToString(" ") { part ->
                part.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }
            }
        }

    fun isWakeOnly(text: String, context: Context): Boolean {
        val normalized = VoiceAssistantHelper.normalize(text)
        if (normalized.isBlank()) return false
        return allWakePhrases(context).any { phrase ->
            normalized == phrase || normalized == "hey $phrase" || normalized == "ok $phrase"
        }
    }

    fun containsWakePhrase(text: String, context: Context): Boolean {
        val normalized = VoiceAssistantHelper.normalize(text)
        if (normalized.isBlank()) return false
        return allWakePhrases(context).any { phrase -> normalized.contains(phrase) }
    }

    fun stripWakePrefix(text: String, context: Context): String? {
        val normalized = VoiceAssistantHelper.normalize(text)
        if (normalized.isBlank()) return null
        for (phrase in allWakePhrases(context)) {
            if (normalized == phrase) return ""
            if (normalized.startsWith("$phrase ")) {
                return normalized.removePrefix("$phrase ").trim()
            }
            if (normalized.startsWith("hey $phrase ")) {
                return normalized.removePrefix("hey $phrase ").trim()
            }
            if (normalized.startsWith("ok $phrase ")) {
                return normalized.removePrefix("ok $phrase ").trim()
            }
        }
        return null
    }

    fun wakeGreeting(): String = "Igen, itt $ASSISTANT_NAME. Hallgatlak."

    fun speakListenStatus(context: Context, enabled: Boolean): String =
        if (enabled) {
            "$ASSISTANT_NAME figyelő bekapcsolva. Mondd: Szia $ASSISTANT_NAME, vagy Kérlek $ASSISTANT_NAME."
        } else {
            "$ASSISTANT_NAME figyelő kikapcsolva."
        }

    fun speakCustomPhrases(context: Context): String {
        val custom = ElenaWakeStore.customPhrases(context)
        if (custom.isEmpty()) {
            return "Nincs saját felébresztő mondat. Mondd: Elena tanítás, vagy válaszd a menüben."
        }
        val listed = custom.joinToString(", ") { it.phrase }
        return "Saját felébresztő mondatok: $listed."
    }
}