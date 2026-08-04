package com.superdl.launcher.book

import java.text.Normalizer
import java.util.Locale

object BookSearchHelper {

    fun search(books: List<BookEntry>, query: String): List<BookEntry> {
        val tokens = normalize(query).split(' ').filter { it.length >= 2 }
        if (tokens.isEmpty()) return emptyList()
        return books.filter { book ->
            val hay = normalize("${book.title} ${book.format}")
            tokens.all { token -> hay.contains(token) }
        }
    }

    private fun normalize(text: String): String {
        val lower = text.lowercase(Locale("hu", "HU"))
        val stripped = Normalizer.normalize(lower, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
        return stripped
            .replace(Regex("[^a-z0-9áéíóöőúüű\\s]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
    }
}