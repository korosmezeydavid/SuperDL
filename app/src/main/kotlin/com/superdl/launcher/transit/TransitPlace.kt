package com.superdl.launcher.transit

data class TransitPlace(
    val name: String,
    val address: String,
    val distanceMeters: Int?,
    val nextDepartures: List<String> = emptyList(),
    val latitude: Double? = null,
    val longitude: Double? = null,
    val stopId: String? = null,
    val clockDirection: String? = null,
    val routeLines: List<String> = emptyList(),
    val vehicleApproach: String? = null,
    val wheelchairAccessible: Boolean? = null,
    val isFavorite: Boolean = false
) {
    fun speakPreview(): String = buildString {
        if (isFavorite) append("Kedvenc. ")
        append(name)
        if (!address.isBlank() && address != name) append(". $address")
        distanceMeters?.let { append(". ${formatDistance(it)}") }
        clockDirection?.let { append(". $it irányában") }
        if (routeLines.isNotEmpty()) {
            append(". Járatok: ${routeLines.take(5).joinToString(", ")}")
        }
        if (nextDepartures.isNotEmpty()) {
            append(". Következő indulás: ${nextDepartures.first()}")
        }
        vehicleApproach?.let { append(". $it") }
        wheelchairAccessible?.let { accessible ->
            append(if (accessible) ". Akadálymentes." else ". Nem akadálymentes.")
        }
    }

    fun speakFull(): String = buildString {
        append(speakPreview())
        if (nextDepartures.size > 1) {
            append(". További indulások: ")
            append(nextDepartures.drop(1).take(4).joinToString(", "))
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
    }
}

data class TransitRouteStep(
    val instruction: String
) {
    fun speakPreview(): String = instruction
}

data class TransitRoute(
    val summary: String,
    val duration: String,
    val steps: List<TransitRouteStep>
) {
    fun speakSummary(): String = "$summary. Becsült idő: $duration."
}