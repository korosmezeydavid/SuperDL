package com.superdl.launcher.youtube

data class YoutubeSearchPage(
    val videos: List<YoutubeVideo>,
    val page: Int,
    val hasMore: Boolean
)

data class YoutubeVideo(
    val videoId: String,
    val title: String,
    val channel: String,
    val durationSeconds: Int
) {
    fun speakPreview(): String {
        val duration = formatDuration(durationSeconds)
        val channelPart = if (channel.isNotBlank()) "$channel. " else ""
        val titleShort = if (title.length > 70) title.take(70) + "…" else title
        return "$channelPart$titleShort. Hossz: $duration."
    }

    fun speakFull(): String {
        val duration = formatDuration(durationSeconds)
        val channelPart = if (channel.isNotBlank()) "Csatorna: $channel. " else ""
        return "$channelPart$title. Hossz: $duration."
    }

    companion object {
        fun formatDuration(seconds: Int): String {
            if (seconds <= 0) return "ismeretlen hossz"
            val hours = seconds / 3600
            val mins = (seconds % 3600) / 60
            val secs = seconds % 60
            return when {
                hours > 0 && mins > 0 -> "$hours óra $mins perc"
                hours > 0 -> "$hours óra"
                mins > 0 && secs > 0 -> "$mins perc $secs másodperc"
                mins > 0 -> "$mins perc"
                else -> "$secs másodperc"
            }
        }
    }
}