package com.superdl.launcher.podcast

/**
 * Egy podcast-műsor (nem egyetlen adás, hanem a sorozat).
 */
data class Podcast(
    val id: String,          // iTunes collectionId
    val title: String,
    val author: String,
    val feedUrl: String,
    val description: String = ""
) {
    fun speakPreview(): String = if (author.isNotBlank() && author != title) {
        "$title, $author"
    } else {
        title
    }
}

/**
 * Egy podcast-epizód (egy adás).
 */
data class PodcastEpisode(
    val title: String,
    val audioUrl: String,
    val durationSeconds: Int,
    val publishedText: String = "",
    val description: String = "",
    val podcastTitle: String = ""
) {
    /** "45 perc" vagy "1 óra 12 perc" alakban. */
    fun speakDuration(): String {
        if (durationSeconds <= 0) return ""
        val hours = durationSeconds / 3600
        val mins = (durationSeconds % 3600) / 60
        return when {
            hours > 0 && mins > 0 -> "$hours óra $mins perc"
            hours > 0 -> "$hours óra"
            else -> "$mins perc"
        }
    }

    fun speakPreview(): String {
        val parts = mutableListOf(title)
        val dur = speakDuration()
        if (dur.isNotBlank()) parts.add(dur)
        if (publishedText.isNotBlank()) parts.add(publishedText)
        return parts.joinToString(", ")
    }

    /** Egyedi azonosító a pozíció-memóriához (a hang URL-je alapján). */
    fun positionKey(): String = audioUrl
}
