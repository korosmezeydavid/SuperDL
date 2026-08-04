package com.superdl.launcher.train

data class TrainDeparture(
    val trainNumber: String,
    val trainName: String?,
    val trainType: String?,
    val destination: String,
    val platform: String?,
    val scheduledEpochSec: Long,
    val actualEpochSec: Long?,
    val delayMinutes: Int?,
    val approachText: String? = null
) {
    fun speakLine(): String = buildString {
        if (!trainType.isNullOrBlank()) append("$trainType ")
        append("vonat")
        if (trainNumber.isNotBlank()) append(" $trainNumber")
        if (!trainName.isNullOrBlank()) append(", $trainName")
        if (destination.isNotBlank()) append(", $destination irány")
        append(", ${TrainStation.formatDepartureTime(actualEpochSec ?: scheduledEpochSec)}")
        platform?.let { append(", $it. vágány") }
        delayMinutes?.takeIf { it > 0 }?.let { append(", $it perces késés") }
        approachText?.let { append(". $it") }
    }
}

data class TrainStation(
    val name: String,
    val address: String,
    val distanceMeters: Int?,
    val nextDepartures: List<TrainDeparture> = emptyList(),
    val latitude: Double? = null,
    val longitude: Double? = null,
    val stationId: String? = null,
    val clockDirection: String? = null,
    val delayWarning: String? = null,
    val isFavorite: Boolean = false
) {
    fun speakPreview(): String = buildString {
        if (isFavorite) append("Kedvenc. ")
        append(name)
        if (!address.isBlank() && address != name) append(". $address")
        distanceMeters?.let { append(". ${formatDistance(it)}") }
        clockDirection?.let { append(". $it irányában") }
        delayWarning?.let { append(". $it") }
        if (nextDepartures.isNotEmpty()) {
            append(". Következő indulás: ${nextDepartures.first().speakLine()}")
        }
    }

    fun speakFull(): String = buildString {
        append(speakPreview())
        if (nextDepartures.size > 1) {
            append(". További indulások: ")
            append(nextDepartures.drop(1).take(4).joinToString(", ") { it.speakLine() })
        }
    }

    companion object {
        fun formatDistance(meters: Int): String = when {
            meters < 1000 -> "$meters méter"
            else -> {
                val km = meters / 1000.0
                val rounded = (km * 10).toInt() / 10.0
                if (rounded == rounded.toLong().toDouble()) "${rounded.toLong()} kilométer"
                else "$rounded kilométer"
            }
        }

        fun formatDepartureTime(epochSec: Long): String {
            if (epochSec <= 0L) return "hamarosan"
            val now = System.currentTimeMillis()
            val target = epochSec * 1000L
            val diffMin = ((target - now) / 60000L).toInt()
            return when {
                diffMin <= 0 -> "most"
                diffMin == 1 -> "1 perc múlva"
                diffMin < 60 -> "$diffMin perc múlva"
                else -> {
                    val fmt = java.text.SimpleDateFormat("HH:mm", java.util.Locale("hu", "HU")).apply {
                        timeZone = java.util.TimeZone.getTimeZone("Europe/Budapest")
                    }
                    fmt.format(java.util.Date(target))
                }
            }
        }
    }
}