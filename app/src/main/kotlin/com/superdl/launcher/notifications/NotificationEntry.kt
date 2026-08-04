package com.superdl.launcher.notifications

data class NotificationEntry(
    val key: String,
    val appLabel: String,
    val title: String,
    val text: String,
    val postedAt: Long
) {
    fun speakPreview(): String {
        val body = text.ifBlank { title }.ifBlank { "Üres értesítés" }
        val preview = if (body.length > 80) body.take(80) + "…" else body
        return "$appLabel. $preview"
    }

    fun speakFull(): String {
        val parts = listOf(appLabel, title, text).filter { it.isNotBlank() }.distinct()
        return parts.joinToString(". ")
    }
}