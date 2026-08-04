package com.superdl.launcher.dictaphone

import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class DictaphoneRecordingEntry(
    val file: File,
    val createdAtMillis: Long,
    val format: DictaphoneFormat
) {
    fun displayName(): String {
        val stamp = SimpleDateFormat("yyyy.MM.dd HH:mm", Locale("hu", "HU")).format(Date(createdAtMillis))
        return "Felvétel $stamp"
    }

    fun speakSummary(): String {
        val sizeKb = (file.length() / 1024).coerceAtLeast(1)
        return "${displayName()}, ${format.label}, $sizeKb kilobájt."
    }
}