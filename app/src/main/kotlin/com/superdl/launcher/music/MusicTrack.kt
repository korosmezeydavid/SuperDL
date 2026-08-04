package com.superdl.launcher.music

import android.net.Uri

data class MusicTrack(
    val id: Long,
    val title: String,
    val artist: String,
    val durationMs: Long,
    val contentUri: Uri
) {
    fun speakPreview(): String {
        val artistPart = if (artist.isNotBlank()) "$artist. " else ""
        val titleShort = if (title.length > 60) title.take(60) + "…" else title
        return "$artistPart$titleShort. Hossz: ${formatDuration(durationMs)}."
    }

    fun speakFull(): String {
        val artistPart = if (artist.isNotBlank()) "Előadó: $artist. " else ""
        return "$artistPart$title. Hossz: ${formatDuration(durationMs)}."
    }

    private fun formatDuration(ms: Long): String {
        if (ms <= 0) return "ismeretlen"
        val totalSec = (ms / 1000).toInt()
        val mins = totalSec / 60
        val secs = totalSec % 60
        return if (mins > 0) "$mins perc $secs másodperc" else "$secs másodperc"
    }
}