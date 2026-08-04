package com.superdl.launcher.gps

import com.superdl.launcher.transit.TransitPlace

data class GpsPoi(
    val id: String,
    val name: String,
    val category: String,
    val latitude: Double,
    val longitude: Double,
    val distanceMeters: Int,
    val bearingDegrees: Float,
    val clockDirection: String,
    val detailText: String? = null
) {
    fun speakRadar(): String = when (category) {
        "utca" -> detailText ?: "Jelenleg a $name utcán vagy."
        "kereszteződés" -> buildString {
            append("Kereszteződés, ")
            append(TransitPlace.formatDistance(distanceMeters))
            append("re, $clockDirection irányában.")
            detailText?.let { append(" $it.") }
        }
        else -> {
            val categoryHint = if (category.isNotBlank() && category != "létesítmény") " ($category)" else ""
            "$name$categoryHint, ${TransitPlace.formatDistance(distanceMeters)}re, $clockDirection irányában."
        }
    }

    fun speakGuidance(turnHint: String): String =
        "$name, ${TransitPlace.formatDistance(distanceMeters)}re. $turnHint."
}