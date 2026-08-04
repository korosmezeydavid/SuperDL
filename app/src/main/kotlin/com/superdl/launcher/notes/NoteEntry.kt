package com.superdl.launcher.notes

data class NoteEntry(
    val id: Int,
    val title: String,
    val body: String,
    val sourceUrl: String?,
    val createdAt: Long
) {
    fun speakPreview(): String {
        val source = sourceUrl?.let { " Forrás: internet." }.orEmpty()
        val preview = body.replace(Regex("\\s+"), " ").trim().take(80)
        return "$title. $preview$source"
    }

    fun speakListItem(index: Int, total: Int): String =
        "$index / $total. $title"
}