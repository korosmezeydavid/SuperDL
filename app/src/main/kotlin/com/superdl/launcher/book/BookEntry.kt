package com.superdl.launcher.book

import java.io.File
import java.util.Locale

data class BookEntry(
    val path: String,
    val title: String,
    val format: String,
    val sizeBytes: Long
) {
    fun speakPreview(): String {
        val sizeHint = when {
            sizeBytes < 1024 -> "egy kilobájtnál kisebb"
            sizeBytes < 1024 * 1024 -> "${sizeBytes / 1024} kilobájt"
            else -> String.format(Locale.getDefault(), "%.1f megabájt", sizeBytes / (1024.0 * 1024.0))
        }
        return "$title. Formátum: ${format.uppercase()}. Méret: $sizeHint."
    }

    fun file(): File = File(path)

    fun stableId(): String = path
}