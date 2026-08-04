package com.superdl.launcher.book

data class BookBookmark(
    val id: Int,
    val bookPath: String,
    val bookTitle: String,
    val charOffset: Int,
    val preview: String,
    val createdAt: Long
) {
    fun speakPreview(): String {
        val pct = if (charOffset > 0) "pozíció $charOffset" else "elején"
        val snippet = preview.take(80).trim()
        return if (snippet.isNotBlank()) {
            "$bookTitle. Könyvjelző: $pct. $snippet"
        } else {
            "$bookTitle. Könyvjelző: $pct."
        }
    }
}