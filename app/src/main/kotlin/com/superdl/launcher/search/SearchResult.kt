package com.superdl.launcher.search

data class SearchResult(
    val title: String,
    val snippet: String,
    val url: String
) {
    fun speakPreview(index: Int, total: Int): String =
        "$index. $title. $snippet"

    fun speakFull(index: Int, total: Int): String =
        "Találat $index a $total közül. $title. $snippet"
}